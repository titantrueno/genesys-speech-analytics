"""Checks de cumplimiento editables y cumplimiento efectivo (FE005, criterio 9)."""
import time

import pytest

from app import ids
from app.data.catalog import COMPLIANCE_CHECKS
from app.data.store import get_dataset
from tests.flow_fixtures import days_ago
from tests.test_config_api import as_role, audit, field_errors

CHECKS = "/api/config/compliance-checks"
PERIOD = {"from": days_ago(89), "to": days_ago(1)}
NEW_CHECK = {"code": "oferta_encuesta", "name": "Ofrecimiento de encuesta", "description": "Invita a valorar la atención.",
             "phrases": ["valore la atención"], "channel": "ambos", "active": True}
# Réplica por frases del check «saludo» en voz: el saludo completo solo se genera cuando el análisis lo da por cumplido.
GREETING_COPY = {"code": "saludo_por_frases", "name": "Saludo por frases", "description": "",
                 "phrases": ["LE ATIENDE"], "channel": "voz", "active": True}


def checks(api) -> list[dict]:
    response = api.get(CHECKS)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def check(api, code: str) -> dict:
    return next(c for c in checks(api) if c["code"] == code)


def editable(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("id", "evaluation", "builtin")}


def create(api, payload=NEW_CHECK) -> dict:
    response = api.post(CHECKS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def summary(api) -> dict:
    return api.get("/api/metrics/summary", params=PERIOD).json()


def compliance_kpi(body: dict) -> float:
    return next(k for k in body["kpis"] if k["code"] == "compliance_rate")["value"]


def schema_keys(api) -> set[str]:
    return {f["key"] for f in api.get("/api/query/schema").json()["fields"]}


# --- Estado inicial ---

def test_initial_checks_are_the_six_of_fe001_evaluated_by_the_analysis(api):
    items = checks(api)
    assert [(c["code"], c["name"]) for c in items] == list(COMPLIANCE_CHECKS.items())
    for item in items:
        assert item["id"] == ids.stable_id(ids.CHECK, item["code"])
        assert item["evaluation"] == "analisis" and item["builtin"] is True
        assert item["channel"] == "ambos" and item["active"] is True
        assert 1 <= len(item["phrases"]) <= 20


def test_without_changes_every_result_matches_the_analysis(api):
    conv = next(c for c in get_dataset() if c.analysis.compliance.get("bloqueo_preventivo") is not None)
    assert api.get(f"/api/conversations/{conv.id}").json()["analysis"]["compliance"] == conv.analysis.compliance
    assert [c["code"] for c in api.get("/api/catalog").json()["compliance_checks"]] == list(COMPLIANCE_CHECKS)


def test_supervisor_reads_and_cannot_write(api):
    as_role(api, "supervisor")
    item = check(api, "saludo")
    assert api.post(CHECKS, json=NEW_CHECK).status_code == 403
    assert api.put(f"{CHECKS}/{item['id']}", json=editable(item)).status_code == 403
    assert api.delete(f"{CHECKS}/{item['id']}").status_code == 403
    as_role(api, "viewer")
    assert api.get(CHECKS).status_code == 403


# --- Validación ---

@pytest.mark.parametrize("payload,field", [
    ({**NEW_CHECK, "code": "saludo"}, "code"),
    ({**NEW_CHECK, "code": "Oferta Encuesta"}, "code"),
    ({**NEW_CHECK, "name": ""}, "name"),
    ({**NEW_CHECK, "name": "Saludo e IDENTIFICACION del agente"}, "name"),
    ({**NEW_CHECK, "phrases": []}, "phrases"),
    ({**NEW_CHECK, "phrases": ["x"] * 21}, "phrases"),
    ({**NEW_CHECK, "phrases": ["  "]}, 0),
    ({**NEW_CHECK, "channel": "email"}, "channel"),
])
def test_invalid_checks_return_field_errors(api, payload, field):
    assert field in field_errors(api.post(CHECKS, json=payload))
    assert audit(api) == []


def test_the_code_cannot_change(api):
    item = check(api, "saludo")
    assert "code" in field_errors(api.put(f"{CHECKS}/{item['id']}", json={**editable(item), "code": "hola"}))


# --- Evaluación por frases ---

def test_a_new_check_is_evaluated_by_phrases_in_agent_turns(api):
    create(api, GREETING_COPY)
    voice = [c for c in get_dataset() if c.channel == "voz"][:60]
    chat = next(c for c in get_dataset() if c.channel == "chat")
    for conv in voice:
        result = api.get(f"/api/conversations/{conv.id}").json()["analysis"]["compliance"]
        assert result["saludo_por_frases"] == conv.analysis.compliance["saludo"], conv.id
    assert api.get(f"/api/conversations/{chat.id}").json()["analysis"]["compliance"]["saludo_por_frases"] is None
    assert check(api, "saludo_por_frases")["evaluation"] == "frases"


def test_phrases_ignore_case_and_accents_but_only_count_agent_turns(api):
    create(api, {**NEW_CHECK, "code": "verificacion_por_frases", "name": "Verificación por frases",
                 "phrases": ["identidad verificada"]})
    create(api, {**NEW_CHECK, "code": "solo_cliente", "name": "Frase del cliente",
                 "phrases": ["Pensaba que eso no se pedia NUNCA"]})
    conv = next(c for c in get_dataset() if c.analysis.compliance["verificacion_identidad"]
                and not c.analysis.compliance["no_solicitar_pin"])
    result = api.get(f"/api/conversations/{conv.id}").json()["analysis"]["compliance"]
    assert result["verificacion_por_frases"] is True
    assert result["solo_cliente"] is False  # la frase la dice el cliente, no el agente


def test_a_new_check_changes_the_kpi_the_detail_the_catalog_and_the_explorer(api):
    before = compliance_kpi(summary(api))
    create(api)
    body = summary(api)
    assert compliance_kpi(body) < before  # nadie dice «valore la atención»: todas pasan a no cumplir
    assert compliance_kpi(body) == 0
    by_check = {c["code"]: c for c in body["compliance_by_check"]}
    assert by_check["oferta_encuesta"]["value"] == 0 and by_check["oferta_encuesta"]["label"] == "Ofrecimiento de encuesta"
    assert "oferta_encuesta" in {c["code"] for c in api.get("/api/catalog").json()["compliance_checks"]}
    assert "check:oferta_encuesta" in schema_keys(api)
    run = api.post("/api/query/run", json={**PERIOD, "root": {"op": "and", "conditions": [
        {"field": "check:oferta_encuesta", "operator": "fails"}]}})
    assert run.status_code == 200 and run.json()["total"] == body["kpis"][0]["value"]


def test_changing_the_channel_of_a_builtin_check_marks_the_other_channel_as_not_applicable(api):
    item = check(api, "saludo")
    assert api.put(f"{CHECKS}/{item['id']}", json={**editable(item), "channel": "chat"}).status_code == 200
    voice = next(c for c in get_dataset() if c.channel == "voz")
    chat = next(c for c in get_dataset() if c.channel == "chat")
    assert api.get(f"/api/conversations/{voice.id}").json()["analysis"]["compliance"]["saludo"] is None
    assert api.get(f"/api/conversations/{chat.id}").json()["analysis"]["compliance"]["saludo"] == \
        chat.analysis.compliance["saludo"]


def test_editing_phrases_of_a_builtin_check_keeps_the_analysis_result(api):
    before = summary(api)
    item = check(api, "saludo")
    assert api.put(f"{CHECKS}/{item['id']}", json={**editable(item), "phrases": ["frase inventada"]}).status_code == 200
    assert summary(api)["kpis"] == before["kpis"]


# --- Desactivar y borrar ---

def test_deactivating_removes_the_check_from_detail_kpi_catalog_and_explorer(api):
    item = check(api, "saludo")
    assert api.put(f"{CHECKS}/{item['id']}", json={**editable(item), "active": False}).status_code == 200
    conv = get_dataset()[0]
    assert "saludo" not in api.get(f"/api/conversations/{conv.id}").json()["analysis"]["compliance"]
    body = summary(api)
    assert "saludo" not in {c["code"] for c in body["compliance_by_check"]}
    assert "saludo" not in {c["code"] for c in api.get("/api/catalog").json()["compliance_checks"]}
    assert "check:saludo" not in schema_keys(api)
    # Una consulta guardada con ese check sigue siendo válida.
    run = api.post("/api/query/run", json={**PERIOD, "root": {"op": "and", "conditions": [
        {"field": "check:saludo", "operator": "fails"}]}})
    assert run.status_code == 200


def test_builtin_checks_cannot_be_deleted_but_new_ones_can(api):
    builtin = check(api, "saludo")
    response = api.delete(f"{CHECKS}/{builtin['id']}")
    assert response.status_code == 409 and "desactivar" in response.json()["detail"].lower()
    created = create(api)
    assert api.delete(f"{CHECKS}/{created['id']}").status_code == 204
    assert "oferta_encuesta" not in {c["code"] for c in checks(api)}
    entry = audit(api, "cumplimiento")[0]
    assert entry["element"] == "Check «Ofrecimiento de encuesta»" and entry["after"] is None


@pytest.mark.parametrize("check_id", [ids.stable_id(ids.CHECK, "no_existe"), "basura",
                                      ids.stable_id(ids.TOPIC, "saludo")])
def test_unknown_malformed_or_foreign_check_returns_404(api, check_id):
    assert api.put(f"{CHECKS}/{check_id}", json=NEW_CHECK).status_code == 404
    assert api.delete(f"{CHECKS}/{check_id}").status_code == 404


# --- Contrato de drill-down (FE001) ---

def drilldown_matches(api) -> None:
    body = summary(api)
    volume = body["kpis"][0]["value"]
    failing = api.get("/api/conversations", params={**PERIOD, "compliant": "false"}).json()["total"]
    passing = api.get("/api/conversations", params={**PERIOD, "compliant": "true"}).json()["total"]
    assert passing + failing == volume
    assert round(100 * passing / volume, 2) == compliance_kpi(body)


def test_compliance_drilldown_matches_the_kpi_after_every_kind_of_change(api):
    drilldown_matches(api)
    create(api, GREETING_COPY)
    drilldown_matches(api)
    item = check(api, "verificacion_identidad")
    api.put(f"{CHECKS}/{item['id']}", json={**editable(item), "active": False})
    drilldown_matches(api)
    item = check(api, "saludo_por_frases")
    api.put(f"{CHECKS}/{item['id']}", json={**editable(item), "phrases": ["buenos días"], "channel": "ambos"})
    drilldown_matches(api)


def test_the_interpreter_only_uses_active_checks(api):
    item = check(api, "saludo")
    api.put(f"{CHECKS}/{item['id']}", json={**editable(item), "active": False})
    body = api.post("/api/query/interpret", json={"text": "conversaciones que incumplen algún check"}).json()
    fields = {c["field"] for g in body["query"]["root"]["conditions"] for c in g.get("conditions", [g])}
    assert "check:saludo" not in fields and "check:despedida" in fields


# --- Rendimiento ---

def test_summary_with_two_phrase_checks_stays_under_500_ms(api):
    create(api, GREETING_COPY)
    create(api, {**NEW_CHECK, "phrases": ["valore la atención", "encuesta de satisfacción", "puntúe"]})
    start = time.perf_counter()
    summary(api)
    first = time.perf_counter() - start
    start = time.perf_counter()
    summary(api)
    second = time.perf_counter() - start
    assert first < 0.5 and second < 0.5


@pytest.mark.parametrize("method", ["put", "delete"])
def test_a_check_deleted_by_someone_else_meanwhile_gives_404_not_500(api, monkeypatch, method):
    from dataclasses import replace

    import app.routers.config as config_router

    created = create(api)
    ghost = replace(config_router._find_check(created["id"]), code="borrado_mientras_tanto")
    monkeypatch.setattr(config_router, "_find_check", lambda check_id: ghost)
    body = {**editable(created), "code": "borrado_mientras_tanto"}
    response = api.put(f"{CHECKS}/{created['id']}", json=body) if method == "put" else api.delete(f"{CHECKS}/{created['id']}")
    assert response.status_code == 404

"""Taxonomía editable y su propagación a catálogo, explorador, listado, KPIs, drill-down y flujos (FE005, criterio 7)."""
import pytest

from app import ids
from app.data.catalog import MAIN_TOPICS, SECONDARY_TOPICS
from app.data.store import get_dataset
from app.flows.prompting import render_template
from tests.flow_fixtures import days_ago
from tests.test_config_api import as_role, audit, field_errors

MAIN = "/api/config/taxonomy/main-topics"
SECONDARY = "/api/config/taxonomy/secondary-topics"
NEW_TOPIC = {"code": "criptoactivos", "name": "Criptoactivos", "description": "Compra y custodia de criptomonedas.",
             "keywords": ["bitcoin", "cripto"], "active": True}
PERIOD = {"from": days_ago(89), "to": days_ago(1)}


def taxonomy(api) -> dict:
    response = api.get("/api/config/taxonomy")
    assert response.status_code == 200, response.text
    return response.json()


def topic(api, code: str) -> dict:
    return next(t for t in taxonomy(api)["main_topics"] if t["code"] == code)


def editable(item: dict) -> dict:
    """Campos editables de un elemento leído (sin `id` ni `conversations`, que son de solo lectura)."""
    return {k: v for k, v in item.items() if k not in ("id", "conversations")}


def create(api, payload=NEW_TOPIC, url=MAIN) -> dict:
    response = api.post(url, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def schema_values(api, field: str) -> dict[str, str]:
    fields = {f["key"]: f for f in api.get("/api/query/schema").json()["fields"]}
    return {v["value"]: v["label"] for v in fields[field].get("values", [])}


def query(conditions: list[dict]) -> dict:
    return {**PERIOD, "root": {"op": "and", "conditions": conditions}}


# --- Estado inicial ---

def test_initial_taxonomy_is_the_fe001_catalog(api):
    body = taxonomy(api)
    assert [(t["code"], t["name"]) for t in body["main_topics"]] == [(c, t.name) for c, t in MAIN_TOPICS.items()]
    for item in body["main_topics"]:
        assert item["id"] == ids.stable_id(ids.TOPIC, item["code"])
        assert item["active"] is True
        assert item["description"] and item["keywords"] == MAIN_TOPICS[item["code"]].keywords
        assert item["conversations"] == sum(1 for c in get_dataset() if c.analysis.main_topic == item["code"])
    assert [t["code"] for t in body["secondary_topics"]] == SECONDARY_TOPICS
    assert all(ids.is_valid(t["id"], ids.SECONDARY_TOPIC) for t in body["secondary_topics"])


def test_supervisor_reads_but_cannot_write_and_analyst_cannot_read(api):
    as_role(api, "supervisor")
    assert api.get("/api/config/taxonomy").status_code == 200
    item = topic(api, "cajeros")
    assert api.post(MAIN, json=NEW_TOPIC).status_code == 403
    assert api.put(f"{MAIN}/{item['id']}", json={**editable(item), "name": "Cajeros"}).status_code == 403
    assert api.delete(f"{MAIN}/{item['id']}").status_code == 403
    as_role(api, "analista")
    assert api.get("/api/config/taxonomy").status_code == 403


# --- Crear y propagar ---

def test_new_main_topic_appears_in_catalog_explorer_and_sampling(api):
    created = create(api)
    assert created["id"] == ids.stable_id(ids.TOPIC, "criptoactivos")
    assert created["conversations"] == 0
    catalog = {t["code"]: t for t in api.get("/api/catalog").json()["main_topics"]}
    assert catalog["criptoactivos"] == {"code": "criptoactivos", "name": "Criptoactivos", "active": True}
    assert schema_values(api, "main_topic")["criptoactivos"] == "Criptoactivos"  # explorador y nodo Sampling
    run = api.post("/api/query/run", json=query([{"field": "main_topic", "operator": "is", "value": "criptoactivos"}]))
    assert run.status_code == 200, run.text
    assert run.json()["total"] == 0
    estimate = api.post("/api/flows/sampling/estimate", json={"query": query(
        [{"field": "main_topic", "operator": "is", "value": "criptoactivos"}]), "size": 10})
    assert estimate.status_code == 200 and estimate.json()["available"] == 0
    listing = api.get("/api/conversations", params={**PERIOD, "main_topic": "criptoactivos"})
    assert listing.json()["total"] == 0


@pytest.mark.parametrize("payload,field", [
    ({**NEW_TOPIC, "code": "cajeros"}, "code"),
    ({**NEW_TOPIC, "code": "Cripto Activos"}, "code"),
    ({**NEW_TOPIC, "code": ""}, "code"),
    ({**NEW_TOPIC, "name": "  "}, "name"),
    ({**NEW_TOPIC, "name": "x" * 81}, "name"),
    ({**NEW_TOPIC, "description": "x" * 301}, "description"),
    ({**NEW_TOPIC, "keywords": [""]}, 0),
    ({**NEW_TOPIC, "keywords": ["k"] * 31}, "keywords"),
])
def test_invalid_main_topic_returns_field_errors(api, payload, field):
    assert field in field_errors(api.post(MAIN, json=payload))
    assert audit(api) == []


def test_name_must_be_unique_among_main_topics(api):
    assert "name" in field_errors(api.post(MAIN, json={**NEW_TOPIC, "name": "incidencia EN cajero"}))


# --- Editar ---

def test_renaming_changes_the_label_everywhere_but_not_the_code(api):
    item = topic(api, "cajeros")
    response = api.put(f"{MAIN}/{item['id']}", json={**editable(item), "name": "Cajeros automáticos"})
    assert response.status_code == 200, response.text
    conv = next(c for c in get_dataset() if c.analysis.main_topic == "cajeros")
    day = conv.started_at.date().isoformat()
    assert api.get(f"/api/conversations/{conv.id}").json()["main_topic_label"] == "Cajeros automáticos"
    items = api.get("/api/conversations", params={"from": day, "to": day, "main_topic": "cajeros"}).json()["items"]
    assert {i["main_topic_label"] for i in items} == {"Cajeros automáticos"}
    breakdown = api.get("/api/metrics/breakdown", params={**PERIOD, "dimension": "main_topic"}).json()["items"]
    assert next(i for i in breakdown if i["key"] == "cajeros")["label"] == "Cajeros automáticos"
    assert schema_values(api, "main_topic")["cajeros"] == "Cajeros automáticos"
    assert "Cajeros automáticos" in render_template("{{main_topic}}", conv)


def test_the_code_cannot_change(api):
    item = topic(api, "cajeros")
    assert "code" in field_errors(api.put(f"{MAIN}/{item['id']}", json={**editable(item), "code": "atm"}))


def test_edit_is_audited_with_before_and_after(api):
    item = topic(api, "cajeros")
    api.put(f"{MAIN}/{item['id']}", json={**editable(item), "keywords": ["cajero", "atm"]})
    entry = audit(api, "taxonomia")[0]
    assert entry["element"] == "Main topic «Incidencia en cajero»"
    assert entry["before"]["keywords"] == ["cajero"]
    assert entry["after"]["keywords"] == ["cajero", "atm"]


# --- Desactivar y borrar ---

def test_a_topic_in_use_cannot_be_deleted(api):
    item = topic(api, "cajeros")
    assert item["conversations"] > 0
    response = api.delete(f"{MAIN}/{item['id']}")
    assert response.status_code == 409
    assert "desactivar" in response.json()["detail"].lower()
    assert topic(api, "cajeros")
    assert audit(api) == []


def test_an_unused_topic_can_be_deleted_and_disappears_everywhere(api):
    created = create(api)
    assert api.delete(f"{MAIN}/{created['id']}").status_code == 204
    assert "criptoactivos" not in {t["code"] for t in taxonomy(api)["main_topics"]}
    assert "criptoactivos" not in {t["code"] for t in api.get("/api/catalog").json()["main_topics"]}
    assert "criptoactivos" not in schema_values(api, "main_topic")
    entry = audit(api, "taxonomia")[0]
    assert entry["before"]["code"] == "criptoactivos" and entry["after"] is None


def test_deactivating_hides_it_from_selectors_but_keeps_data_kpis_and_drilldown(api):
    before = api.get("/api/metrics/summary", params=PERIOD).json()
    breakdown = api.get("/api/metrics/breakdown", params={**PERIOD, "dimension": "main_topic"}).json()["items"]
    volume = next(i for i in breakdown if i["key"] == "cajeros")["kpis"]["volume"]
    item = topic(api, "cajeros")
    assert api.put(f"{MAIN}/{item['id']}", json={**editable(item), "active": False}).status_code == 200

    assert {t["code"]: t["active"] for t in api.get("/api/catalog").json()["main_topics"]}["cajeros"] is False
    assert "cajeros" not in schema_values(api, "main_topic")
    assert api.get("/api/metrics/summary", params=PERIOD).json() == before
    listing = api.get("/api/conversations", params={**PERIOD, "main_topic": "cajeros"}).json()
    assert listing["total"] == volume  # el drill-down sigue cuadrando
    assert {i["main_topic_label"] for i in listing["items"]} == {"Incidencia en cajero"}
    # Una consulta guardada o un flujo con ese código siguen siendo válidos.
    run = api.post("/api/query/run", json=query([{"field": "main_topic", "operator": "is", "value": "cajeros"}]))
    assert run.status_code == 200 and run.json()["total"] == volume


@pytest.mark.parametrize("topic_id", [ids.stable_id(ids.TOPIC, "no_existe"), "basura",
                                      ids.stable_id(ids.CHECK, "cajeros")])
def test_unknown_malformed_or_foreign_topic_returns_404(api, topic_id):
    assert api.put(f"{MAIN}/{topic_id}", json=NEW_TOPIC).status_code == 404
    assert api.delete(f"{MAIN}/{topic_id}").status_code == 404


# --- Temas secundarios ---

def test_secondary_topics_crud_and_propagation(api):
    created = create(api, {"code": "criptomonedas", "name": "Criptomonedas", "description": "",
                           "keywords": [], "active": True}, SECONDARY)
    assert ids.is_valid(created["id"], ids.SECONDARY_TOPIC)
    assert schema_values(api, "secondary_topic")["criptomonedas"] == "Criptomonedas"

    used = next(t for t in taxonomy(api)["secondary_topics"] if t["code"] == "fraude")
    assert used["conversations"] > 0
    assert api.delete(f"{SECONDARY}/{used['id']}").status_code == 409
    assert api.put(f"{SECONDARY}/{used['id']}", json={**editable(used), "active": False}).status_code == 200
    assert "fraude" not in schema_values(api, "secondary_topic")
    run = api.post("/api/query/run", json=query([{"field": "secondary_topic", "operator": "is", "value": "fraude"}]))
    assert run.status_code == 200 and run.json()["total"] > 0

    assert api.delete(f"{SECONDARY}/{created['id']}").status_code == 204
    assert "criptomonedas" not in schema_values(api, "secondary_topic")


def test_existing_secondary_codes_keep_their_spaces(api):
    item = next(t for t in taxonomy(api)["secondary_topics"] if t["code"] == "compras online")
    assert item["name"] == "compras online"
    assert "code" in field_errors(api.post(SECONDARY, json={**editable(item), "code": "Mayúsculas"}))


# --- Cachés ---

def test_explorer_fields_follow_the_config_version(api):
    assert "criptoactivos" not in schema_values(api, "main_topic")
    create(api)
    assert "criptoactivos" in schema_values(api, "main_topic")


def test_no_module_reads_the_fixed_catalog_outside_data_and_config():
    """El catálogo de FE001 es solo el estado inicial: el resto de módulos lee la configuración vigente."""
    import pathlib
    import re

    app_dir = pathlib.Path(__file__).parents[1] / "app"
    offenders = [str(path.relative_to(app_dir)) for path in app_dir.rglob("*.py")
                 if path.parent.name not in ("data", "config")
                 and re.search(r"\b(MAIN_TOPICS|SECONDARY_TOPICS)\b", path.read_text())]
    assert offenders == []


def test_the_interpreter_does_not_propose_a_deactivated_topic(api):
    def topics_for(text: str) -> list:
        body = api.post("/api/query/interpret", json={"text": text}).json()
        return [c for c in body["query"]["root"]["conditions"] if c["field"] == "main_topic"]

    assert topics_for("cargos no reconocidos")
    item = topic(api, "cargo_no_reconocido")
    assert api.put(f"{MAIN}/{item['id']}", json={**editable(item), "active": False}).status_code == 200
    assert topics_for("cargos no reconocidos") == []

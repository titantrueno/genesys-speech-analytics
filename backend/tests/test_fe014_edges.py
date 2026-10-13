"""Casos límite de FE014 añadidos en /test: valores no finitos, checks desactivados a mitad de ejecución, canal frente a
resultado guardado, periodos vacíos, límites de la plantilla y escrituras simultáneas."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone

import psycopg
import pytest

from app.config.compliance import evaluate
from app.config.store import get_config
from app.data.real import _entities
from app.data.store import get_dataset
from app.flows import catalog
from app.flows.fields import ValueRejected, coerce
from app.flows.llm_runner import validate_answer
from app.flows.model import PromptConfig
from app.services.kpis import kpi_pending
from tests.test_config_compliance import NEW_CHECK, create
from tests.test_flow_fields import BOTH_PROMPT
from tests.test_flow_fields_pg import RUN_ID, _ids, service  # noqa: F401  (fixture)


def _active_check():
    return next(c for c in get_config().checks.values() if c.active)


# --- Valores ---

def test_a_non_finite_number_passes_the_format_but_is_rejected_by_its_target():
    # `json.loads` acepta NaN e Infinity; el formato del Prompt los deja pasar como número y el destino los rechaza.
    config = PromptConfig.model_validate({**BOTH_PROMPT, "output": {"type": "json", "fields": [
        {"name": "csat", "type": "numero"}]}})
    for raw in ("NaN", "Infinity", "-Infinity"):
        value = validate_answer(config, f'{{"csat": {raw}}}')["csat"]
        with pytest.raises(ValueRejected, match="número"):
            coerce("csat", value)


def test_a_check_deactivated_during_the_run_is_rejected(monkeypatch):
    check = _active_check()
    monkeypatch.setitem(get_config().checks, check.code, replace(check, active=False))
    with pytest.raises(ValueRejected, match="desactivado"):
        coerce(f"compliance:{check.code}", "cumple")


def test_exactly_ten_keywords_are_kept_and_an_answer_in_capitals_is_normalized():
    assert coerce("keywords", [f"p{i}" for i in range(10)]) == [f"p{i}" for i in range(10)]
    assert coerce("churn_risk", "MEDIO") == "medio"
    assert coerce("resolution", "No Resuelta") == "no_resuelta"


# --- Lectura ---

def test_a_check_that_does_not_apply_to_the_channel_is_not_applicable_even_with_a_stored_result(monkeypatch):
    conv = next(c for c in get_dataset() if c.channel == "chat")
    check = _active_check()
    voice_only = replace(check, channel="voz")
    stored = conv.model_copy(update={"analysis": conv.analysis.model_copy(
        update={"compliance": {**conv.analysis.compliance, check.code: True}})})
    assert evaluate(voice_only, stored) is None


def test_entities_are_read_from_the_stored_object_or_the_old_list():
    assert [e.model_dump() for e in _entities({"importe": "3 €", "fecha": "hoy"})] == [
        {"type": "importe", "value": "3 €"}, {"type": "fecha", "value": "hoy"}]
    assert [e.model_dump() for e in _entities([{"type": "comercio", "value": "Amazon"}])] == [
        {"type": "comercio", "value": "Amazon"}]
    assert _entities(None) == []


def test_an_empty_period_is_not_pending():
    assert kpi_pending("csat_avg", []) is False
    synthetic = get_dataset()[:5]
    assert all(kpi_pending(code, synthetic) is False for code in ("csat_avg", "compliance_rate", "fcr_rate"))


def test_the_synthetic_detail_has_no_pending_checks(api):
    conv = get_dataset()[0]
    analysis = api.get(f"/api/conversations/{conv.id}").json()["analysis"]
    assert analysis["compliance_pending"] == [] and analysis["pending"] is False


# --- Plantilla ---

def test_the_full_template_fits_exactly_the_maximum_number_of_checks(api):
    fixed = len(catalog.ANALYSIS_TARGETS) + len(catalog.ENTITY_TYPES)
    active = sum(1 for c in get_config().checks.values() if c.active)
    for i in range(catalog.MAX_FIELDS - fixed - active):
        create(api, {**NEW_CHECK, "code": f"check_limite_{i}", "name": f"Check límite {i}", "description": ""})
    response = api.post("/api/flows", json={"name": "x", "template": "analisis_completo"})
    assert response.status_code == 201, response.text
    prompt = next(n for n in response.json()["graph"]["nodes"] if n["type"] == "prompt")["config"]
    assert len(prompt["output"]["fields"]) == catalog.MAX_FIELDS


# --- Escritura simultánea (PostgreSQL) ---

def _write(pg_url, cid, values, overwrite=False):
    from ingestion.analysis import FieldsIn, write_fields
    body = FieldsIn(run_id=RUN_ID, provider="gemini", model="m", overwrite=overwrite,
                    items=[{"conversation_id": cid, "values": values}])
    return write_fields(pg_url, body, datetime.now(timezone.utc))[0]["outcomes"]


@pytest.mark.pg
def test_simultaneous_writes_of_different_checks_keep_all_of_them(service, pg_url):
    cid = _ids(pg_url, 1)[0]
    codes = [f"check_{i}" for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda code: _write(pg_url, cid, {f"compliance:{code}": True}), codes))
    assert all(o == {f"compliance:{c}": "escrito"} for o, c in zip(outcomes, codes))
    with psycopg.connect(pg_url) as conn:
        compliance, meta = conn.execute("SELECT compliance, llm_meta FROM analysis WHERE conversation_id = %s",
                                        (cid,)).fetchone()
    # `FOR UPDATE` serializa las escrituras y `||` combina clave a clave: ninguna pisa a otra.
    assert compliance == {code: True for code in codes}
    assert set(meta) == {f"compliance:{code}" for code in codes}


@pytest.mark.pg
def test_overwrite_can_turn_a_result_into_not_applicable(service, pg_url):
    cid = _ids(pg_url, 1)[0]
    _write(pg_url, cid, {"compliance:saludo": True, "entity:importe": "1 €"})
    assert _write(pg_url, cid, {"compliance:saludo": None}, overwrite=True) == {"compliance:saludo": "escrito"}
    with psycopg.connect(pg_url) as conn:
        row = conn.execute("SELECT compliance, entities FROM analysis WHERE conversation_id = %s", (cid,)).fetchone()
    assert row == ({"saludo": None}, {"importe": "1 €"})


@pytest.mark.pg
def test_an_unknown_conversation_reports_every_new_field(service, pg_url):
    values = {"csat": 3, "keywords": ["x"], "compliance:saludo": False, "entity:fecha": "hoy"}
    assert _write(pg_url, "1CO-00000000-0000-4000-8000-000000000000", values) == {t: "no_encontrada" for t in values}



def test_a_conversation_whose_checks_do_not_apply_does_not_count_for_compliance(monkeypatch):
    # Sin resultado y con todos los checks de otro canal, no hay nada que contar: ni cumple ni incumple.
    from app.config.compliance import has_compliance
    checks = get_config().checks
    for code, check in list(checks.items()):
        monkeypatch.setitem(checks, code, replace(check, channel="voz"))
    chat = next(c for c in get_dataset() if c.channel == "chat")
    unanalysed = chat.model_copy(update={"analysis": chat.analysis.model_copy(update={"compliance": {}, "pending": True})})
    assert has_compliance(unanalysed) is False


# --- Hallazgos de /review ---

def test_free_text_from_the_llm_has_a_maximum_length():
    assert coerce("keywords", ["a" * 80]) == ["a" * 80]
    with pytest.raises(ValueRejected, match="80"):
        coerce("keywords", ["a" * 81])
    assert coerce("entity:producto", "p" * 200) == "p" * 200
    with pytest.raises(ValueRejected, match="200"):
        coerce("entity:producto", "p" * 201)


@pytest.mark.pg
def test_the_ingestion_service_refuses_oversized_values(service, pg_url):
    from tests.test_analysis_fields_pg import _post
    cid = _ids(pg_url, 1)[0]
    for values in ({"summary": "x" * 4001}, {"keywords": ["k"] * 101}, {"entity:importe": "€" * 4001}):
        assert _post(service, [{"conversation_id": cid, "values": values}]).status_code == 422, values


def test_a_taxonomy_too_large_for_the_template_is_explained(api, monkeypatch):
    topics = get_config().secondary_topics
    model = next(iter(topics.values()))
    for i in range(catalog.MAX_OPTIONS + 1):
        monkeypatch.setitem(topics, f"tema_{i}", replace(model, code=f"tema_{i}", name=f"Tema {i}", active=True))
    response = api.post("/api/flows", json={"name": "x", "template": "analisis_completo"})
    assert response.status_code == 422
    assert "temas" in response.json()["detail"]

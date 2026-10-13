"""Plantilla «Generar análisis completo» (FE014, T5; criterio 13)."""
import json

import psycopg
import pytest

from app.config.store import get_config
from app.flows import catalog
from tests.real_helpers import QS, real_api  # noqa: F401  (fixture)
from tests.test_config_compliance import NEW_CHECK, create
from tests.test_flow_fields_pg import wired  # noqa: F401  (fixture)
from tests.test_flow_runs import run
from tests.test_flow_templates import _by_type, _create
from tests.test_llm_flows import _finished, llm  # noqa: F401  (fixture)

TEMPLATE = "analisis_completo"


def _targets(api) -> list[str]:
    return [t["value"] for t in api.get("/api/flows/catalog").json()["target_fields"]]


def _active(kind: str) -> list:
    return [t for t in getattr(get_config(), kind).values() if t.active]


def test_the_catalog_offers_the_template(api):
    assert {"value": TEMPLATE, "label": "Generar análisis completo"} in api.get("/api/flows/catalog").json()["templates"]


def test_the_template_has_one_field_and_one_mapping_per_target(api):
    nodes = _by_type(_create(api, TEMPLATE))
    fields = {f["name"]: f for f in nodes["prompt"]["output"]["fields"]}
    mappings = nodes["output"]["mappings"]
    assert [m["target"] for m in mappings] == _targets(api)
    assert all(m["source"] in fields for m in mappings)
    assert len(fields) == len(mappings)
    source = {m["target"]: fields[m["source"]] for m in mappings}
    assert source["main_topic"]["options"] == [t.name for t in _active("main_topics")]
    assert source["secondary_topics"] == {"name": source["secondary_topics"]["name"], "type": "lista",
                                          "options": [t.name for t in _active("secondary_topics")]}
    assert source["keywords"]["type"] == "lista" and "options" not in source["keywords"]
    assert source["resolution"]["options"] == ["resuelta", "no_resuelta", "escalada"]
    assert source["churn_risk"]["options"] == ["bajo", "medio", "alto"]
    assert {source[t]["type"] for t in ("csat", "effort", "sentiment")} == {"numero"}
    assert source["summary"] == {"name": "summary", "type": "texto"}
    for check in _active("checks"):
        assert source[f"compliance:{check.code}"]["options"] == ["cumple", "no_cumple", "no_aplica"]
    assert {source[f"entity:{t}"]["type"] for t in catalog.ENTITY_TYPES} == {"texto"}
    assert nodes["output"]["kind"] == "campo" and nodes["output"]["overwrite"] is False


def test_the_prompt_explains_every_field(api):
    nodes = _by_type(_create(api, TEMPLATE))
    template = nodes["prompt"]["template"]
    assert "{{transcripcion}}" in template and len(template) <= catalog.MAX_TEMPLATE
    for field in nodes["prompt"]["output"]["fields"]:
        assert f"- {field['name']}:" in template, field["name"]
    for check in _active("checks"):
        assert check.name in template


def test_the_sampling_takes_conversations_with_any_empty_field(api):
    root = _by_type(_create(api, TEMPLATE))["sampling"]["query"]["root"]
    assert root["op"] == "or"
    assert all(c["operator"] == "is_empty" for c in root["conditions"])
    expected = {"summary", "main_topic", "resolution", "csat", "effort", "churn_risk",
                *(f"check:{c.code}" for c in _active("checks"))}
    assert {c["field"] for c in root["conditions"]} == expected


def test_a_new_custom_check_is_included(api):
    create(api)
    nodes = _by_type(_create(api, TEMPLATE))
    assert f"compliance:{NEW_CHECK['code']}" in [m["target"] for m in nodes["output"]["mappings"]]
    assert {"field": f"check:{NEW_CHECK['code']}", "operator": "is_empty"} in nodes["sampling"]["query"]["root"]["conditions"]


def test_too_many_checks_for_one_call_are_explained(api):
    fixed = len(catalog.ANALYSIS_TARGETS) + len(catalog.ENTITY_TYPES)
    for i in range(catalog.MAX_FIELDS - fixed - len(_active("checks")) + 1):
        create(api, {**NEW_CHECK, "code": f"check_extra_{i}", "name": f"Check extra {i}"})
    response = api.post("/api/flows", json={"name": "x", "template": TEMPLATE})
    assert response.status_code == 422
    assert "checks" in response.json()["detail"]


# --- Con datos reales (criterio 13) ---

def _valid_answer(body) -> str:
    """Una respuesta válida para cualquier esquema de la plantilla, como la daría el LLM."""
    answer = {}
    for name, prop in body["output"]["schema"]["properties"].items():
        if prop["type"] == "array":
            answer[name] = prop["items"].get("enum", ["cajero", "tarjeta"])[:1] or ["tarjeta"]
        elif prop["type"] == "number":
            answer[name] = 0.25 if name == "sentiment" else 4
        else:
            answer[name] = prop["enum"][0] if "enum" in prop else f"Valor de {name}"
    return json.dumps(answer, ensure_ascii=False)


@pytest.mark.pg
def test_the_template_validates_and_writes_every_field(real_api, llm, pg_url):
    flow = _create(real_api, TEMPLATE)
    response = real_api.post("/api/flows/validate", json=flow["graph"])
    assert response.json() == {"valid": True, "issues": []}, response.json()


@pytest.mark.pg
def test_a_template_run_writes_every_field(wired, llm, pg_url):
    api = wired
    llm.answer = _valid_answer
    flow = _create(api, TEMPLATE)
    graph = flow["graph"]
    sampling = next(n for n in graph["nodes"] if n["type"] == "sampling")
    sampling["config"]["query"] |= {"from": QS["from"], "to": QS["to"]}
    sampling["config"]["size"] = 3
    assert api.put(f"/api/flows/{flow['id']}/graph", json=graph).status_code == 200
    snapshot = _finished(api, flow, run(api, flow)["id"])
    assert snapshot["status"] == "ok", snapshot["nodes"]
    rows = next(iter(snapshot["outputs"].values()))["result"]["rows"]
    written = [r for r in rows if r["states"].get("resolution") == "escrito"]
    assert written, rows
    states = written[0]["states"]
    assert all(states[t] in ("escrito", "omitido") for t in _targets(api)), states
    with psycopg.connect(pg_url) as conn:
        row = conn.execute("SELECT resolution, csat, keywords, compliance, entities, llm_meta FROM analysis "
                           "WHERE conversation_id = %s", (written[0]["conversation"]["id"],)).fetchone()
    resolution, csat, keywords, compliance, entities, meta = row
    assert (resolution, csat, keywords) == ("resuelta", 4.0, ["cajero"])
    assert set(compliance) == {c.code for c in _active("checks")}
    assert set(entities) == set(catalog.ENTITY_TYPES)
    assert {t for t, s in states.items() if s == "escrito"} <= set(meta)


"""Plantillas de flujo para generar summary y main topic (FE013, T8; criterio 23)."""
import pytest

from app.config.store import get_config
from tests.real_helpers import real_api, seed_real  # noqa: F401  (fixture)
from tests.test_llm_flows import FakeLlm, llm  # noqa: F401  (fixture)


def _create(api, template: str | None, name: str = "Desde plantilla") -> dict:
    body = {"name": name} | ({"template": template} if template else {})
    response = api.post("/api/flows", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _by_type(flow: dict) -> dict:
    return {n["type"]: n["config"] for n in flow["graph"]["nodes"]}


def _active_topic_names() -> list[str]:
    return [t.name for t in get_config().main_topics.values() if t.active]


def test_the_catalog_lists_the_templates_and_the_data_origin(api):
    flows_catalog = api.get("/api/flows/catalog").json()
    assert flows_catalog["templates"] == [
        {"value": "summary", "label": "Generar summary"},
        {"value": "main_topic", "label": "Generar main topic"},
        {"value": "summary_main_topic", "label": "Generar summary y main topic"},
        {"value": "analisis_completo", "label": "Generar análisis completo"},  # FE014
    ]
    assert flows_catalog["origin"] == "sintetico"


def test_without_template_the_flow_is_empty(api):
    assert _create(api, None)["graph"]["nodes"] == []


def test_the_summary_template(api):
    flow = _create(api, "summary")
    nodes = _by_type(flow)
    assert [n["type"] for n in flow["graph"]["nodes"]] == ["sampling", "prompt", "output"]
    assert len(flow["graph"]["edges"]) == 2 and all(n["id"].startswith("1ND-") for n in flow["graph"]["nodes"])
    assert nodes["sampling"]["query"]["root"]["conditions"] == [{"field": "summary", "operator": "is_empty"}]
    prompt = nodes["prompt"]
    assert (prompt["provider"], prompt["model"]) == ("gemini", "gemini-3.5-flash-lite")
    assert prompt["output"] == {"type": "texto"} and "{{transcripcion}}" in prompt["template"]
    assert nodes["output"] == {"kind": "campo", "overwrite": False,
                               "mappings": [{"target": "summary"}]}


def test_the_main_topic_template_lists_the_active_topics(api):
    nodes = _by_type(_create(api, "main_topic"))
    assert nodes["sampling"]["query"]["root"]["conditions"] == [{"field": "main_topic", "operator": "is_empty"}]
    assert nodes["prompt"]["output"] == {"type": "etiqueta", "labels": _active_topic_names()}
    assert nodes["output"]["mappings"] == [{"target": "main_topic"}]


def test_the_one_call_template_asks_for_both_fields(api):
    nodes = _by_type(_create(api, "summary_main_topic"))
    root = nodes["sampling"]["query"]["root"]
    assert root["op"] == "or" and {c["field"] for c in root["conditions"]} == {"summary", "main_topic"}
    assert nodes["prompt"]["output"] == {"type": "json", "fields": [
        {"name": "summary", "type": "texto"},
        {"name": "main_topic", "type": "texto", "options": _active_topic_names()}]}
    assert nodes["output"]["mappings"] == [{"target": "summary", "source": "summary"},
                                           {"target": "main_topic", "source": "main_topic"}]


def test_templates_take_the_default_provider_and_skip_inactive_topics(api):
    assert api.put("/api/config/ai", json={"provider": "anthropic", "model": "claude-haiku-5-5"}).status_code == 200
    taxonomy = api.get("/api/config/taxonomy").json()["main_topics"]
    cajeros = next(t for t in taxonomy if t["code"] == "cajeros")
    body = {k: v for k, v in cajeros.items() if k not in ("id", "conversations")} | {"active": False}
    assert api.put(f"/api/config/taxonomy/main-topics/{cajeros['id']}", json=body).status_code == 200
    prompt = _by_type(_create(api, "main_topic"))["prompt"]
    assert (prompt["provider"], prompt["model"]) == ("anthropic", "claude-haiku-5-5")
    assert "Incidencia en cajero" not in prompt["output"]["labels"]


def test_an_unknown_template_is_refused(api):
    assert api.post("/api/flows", json={"name": "x", "template": "otra"}).status_code == 422


@pytest.mark.pg
@pytest.mark.parametrize("template", ["summary", "main_topic", "summary_main_topic"])
def test_a_template_validates_with_real_data_and_a_provider_with_key(real_api, llm, template):
    flow = _create(real_api, template)
    response = real_api.post("/api/flows/validate", json=flow["graph"])
    assert response.json() == {"valid": True, "issues": []}, response.json()

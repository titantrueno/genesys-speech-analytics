"""Catálogo de campos destino, tipo «lista» y límite de campos del esquema (FE014, T2; criterios 1, 2 y 3)."""
import json

import pytest

from app.config.store import get_config
from app.flows import catalog
from app.flows.llm_runner import LlmPromptRunner, json_schema, validate_answer
from app.flows.model import PromptConfig
from app.flows.prompting import MockPromptRunner, PromptRejected
from app.data.store import get_dataset
from ingestion import analysis as ingestion_analysis
from tests.test_config_compliance import CHECKS, NEW_CHECK, create
from tests.test_flow_fields import BOTH_OUTPUT, TEXT_PROMPT, _flow
from tests.test_flow_runs import flow_with
from tests.test_llm_flows import FakeLlm

FIXED = ["summary", "main_topic", "resolution", "csat", "effort", "churn_risk", "sentiment", "secondary_topics",
         "keywords"]
ENTITIES = ["entity:importe", "entity:producto", "entity:fecha", "entity:comercio"]
LIST_PROMPT = {**TEXT_PROMPT, "output": {"type": "json", "fields": [
    {"name": "temas", "type": "lista", "options": ["Fraude", "App móvil"]},
    {"name": "palabras", "type": "lista"}]}}


def _targets(api) -> list[dict]:
    response = api.get("/api/flows/catalog")
    assert response.status_code == 200, response.text
    return response.json()["target_fields"]


def _active_checks() -> list:
    return [c for c in get_config().checks.values() if c.active]


# --- Catálogo (criterio 1) ---

def test_the_catalog_offers_every_target_grouped(api):
    targets = _targets(api)
    values = [t["value"] for t in targets]
    checks = [f"compliance:{c.code}" for c in _active_checks()]
    assert values == FIXED + checks + ENTITIES
    groups = {t["value"]: t["group"] for t in targets}
    assert {groups[v] for v in FIXED} == {"analisis"}
    assert {groups[v] for v in checks} == {"cumplimiento"}
    assert {groups[v] for v in ENTITIES} == {"entidades"}
    labels = {t["value"]: t["label"] for t in targets}
    assert (labels["resolution"], labels["csat"], labels["sentiment"], labels["keywords"]) == (
        "Resolución", "CSAT predicho", "Sentimiento global", "Palabras clave")
    assert all(labels[f"compliance:{c.code}"] == c.name for c in _active_checks())
    assert labels["entity:importe"] == "Importe"


def test_a_new_check_is_offered_and_a_deactivated_one_is_not(api):
    create(api)
    assert f"compliance:{NEW_CHECK['code']}" in [t["value"] for t in _targets(api)]
    first = _active_checks()[0]
    current = api.get(CHECKS).json()["items"]
    item = next(c for c in current if c["code"] == first.code)
    payload = {k: v for k, v in item.items() if k not in ("id", "evaluation", "builtin")}
    response = api.put(f"{CHECKS}/{item['id']}", json={**payload, "active": False})
    assert response.status_code == 200, response.text
    assert f"compliance:{first.code}" not in [t["value"] for t in _targets(api)]


def test_the_ingestion_service_knows_the_same_entity_types():
    assert ingestion_analysis.ENTITY_TYPES == tuple(catalog.ENTITY_TYPES)


@pytest.mark.parametrize("target", ["resolution", "keywords", "entity:fecha", "compliance:saludo",
                                    "compliance:un_check_borrado"])
def test_any_well_formed_target_can_be_saved(api, target):
    # Un check que no existe se guarda (es un borrador) y lo marca la completitud (criterio 7, en T3).
    flow = flow_with(api, _flow(TEXT_PROMPT, {"kind": "campo", "mappings": [{"target": target, "source": None}]}))
    assert next(n for n in flow["graph"]["nodes"] if n["type"] == "output")["config"]["mappings"][0]["target"] == target


@pytest.mark.parametrize("target", ["otro", "entity:color", "compliance:", "compliance:Saludo", "check:saludo"])
def test_unknown_targets_are_refused_on_save(api, target):
    created = api.post("/api/flows", json={"name": "x"}).json()
    output = {"kind": "campo", "mappings": [{"target": target, "source": None}]}
    assert api.put(f"/api/flows/{created['id']}/graph", json=_flow(TEXT_PROMPT, output)).status_code == 422


# --- Tipo «lista» (criterio 2) y límite (criterio 3) ---

def test_a_list_field_round_trips(api):
    flow = flow_with(api, _flow(LIST_PROMPT, BOTH_OUTPUT))
    prompt = next(n for n in flow["graph"]["nodes"] if n["type"] == "prompt")["config"]
    assert prompt["output"] == LIST_PROMPT["output"]
    assert {"value": "lista", "label": "Lista"} in api.get("/api/flows/catalog").json()["field_types"]


def test_options_are_refused_on_numbers_and_booleans(api):
    created = api.post("/api/flows", json={"name": "x"}).json()
    prompt = {**TEXT_PROMPT, "output": {"type": "json", "fields": [{"name": "n", "type": "numero", "options": ["1"]}]}}
    assert api.put(f"/api/flows/{created['id']}/graph", json=_flow(prompt, BOTH_OUTPUT)).status_code == 422


def test_forty_fields_fit_and_forty_one_do_not(api):
    created = api.post("/api/flows", json={"name": "x"}).json()

    def put(n):
        fields = [{"name": f"campo_{i}", "type": "texto"} for i in range(n)]
        prompt = {**TEXT_PROMPT, "output": {"type": "json", "fields": fields}}
        return api.put(f"/api/flows/{created['id']}/graph", json=_flow(prompt, BOTH_OUTPUT)).status_code
    assert (catalog.MAX_FIELDS, put(40), put(41)) == (40, 200, 422)


def test_the_llm_receives_a_list_as_an_array_of_strings():
    schema = json_schema(PromptConfig.model_validate(LIST_PROMPT))
    assert schema["properties"]["temas"] == {"type": "array", "items": {"type": "string", "enum": ["Fraude", "App móvil"]}}
    assert schema["properties"]["palabras"] == {"type": "array", "items": {"type": "string"}}
    fake = FakeLlm(answer=lambda body: '{"temas": [], "palabras": []}')
    LlmPromptRunner(fake).run(PromptConfig.model_validate(LIST_PROMPT), get_dataset()[0], None)
    assert fake.requests[0]["output"]["schema"] == schema


def _answer(data) -> object:
    return validate_answer(PromptConfig.model_validate(LIST_PROMPT), json.dumps(data, ensure_ascii=False))


def test_a_valid_list_answer_is_normalized_to_the_allowed_values():
    assert _answer({"temas": ["fraude", " APP MOVIL "], "palabras": ["tarjeta", "cargo"]}) == {
        "temas": ["Fraude", "App móvil"], "palabras": ["tarjeta", "cargo"]}
    assert _answer({"temas": [], "palabras": []}) == {"temas": [], "palabras": []}


@pytest.mark.parametrize("data", [
    {"temas": "Fraude", "palabras": []},
    {"temas": ["Fraude", 3], "palabras": []},
    {"temas": ["Fraude"], "palabras": [None]},
    {"temas": ["Hipotecas"], "palabras": []},
], ids=str)
def test_a_wrong_list_answer_is_rejected(data):
    with pytest.raises(PromptRejected):
        _answer(data)


def test_the_simulated_runner_answers_a_list():
    result = MockPromptRunner().run(PromptConfig.model_validate({**LIST_PROMPT, "provider": "simulado",
                                                                 "model": "mock-rapido"}),
                                    get_dataset()[0], None)
    assert isinstance(result["temas"], list) and set(result["temas"]) <= {"Fraude", "App móvil"}
    assert isinstance(result["palabras"], list) and all(isinstance(w, str) and w for w in result["palabras"])

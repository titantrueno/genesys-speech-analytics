"""Explorador, sampling y prompts con el origen `real` (FE012, T4; criterios 7, 8 y 10)."""
import pytest

from app.data.store import get_dataset
from app.flows.model import OutputFormat, PromptConfig, SamplingConfig
from app.flows.prompting import MockPromptRunner, render_template
from app.flows.sampling import candidates, draw_sample
from tests.flow_fixtures import complete_graph
from tests.real_helpers import QS, real_api, real_id  # noqa: F401  (fixture)

pytestmark = pytest.mark.pg
GENESYS_FIELDS = {
    "gc_ani", "gc_dnis", "gc_external_tag", "gc_flow", "gc_wrapup", "gc_disconnect_by", "gc_contained", "gc_derived",
    "gc_abandoned", "gc_reconnected", "gc_undelivered", "gc_transcript_quality", "gc_topic", "gc_sentiment",
    "gc_silence_pct", "gc_handle_s", "gc_queue_wait_s", "gc_talk_s", "gc_hold_s", "gc_acw_s", "gc_bot_time_s",
}


def cond(field, operator, value=None, **extra):
    return {"field": field, "operator": operator, "value": value, **extra}


def run(api, *conditions) -> dict:
    response = api.post("/api/query/run", params={"page_size": 100},
                        json={**QS, "root": {"op": "and", "conditions": list(conditions)}})
    assert response.status_code == 200, response.text
    return response.json()


def schema(api) -> dict:
    return {f["key"]: f for f in api.get("/api/query/schema").json()["fields"]}


# --- Esquema ---

def test_the_synthetic_schema_has_no_genesys_fields_nor_empty_operators(api):
    fields = schema(api)
    assert not GENESYS_FIELDS & set(fields)
    assert all("is_empty" not in {o["key"] for o in f["operators"]} for f in fields.values())


def test_the_real_schema_offers_the_genesys_fields(real_api):
    fields = schema(real_api)
    assert GENESYS_FIELDS <= set(fields)
    assert fields["gc_derived"]["type"] == "boolean"
    assert {"completa", "parcial", "sin_transcripcion"} == {v["value"] for v in fields["gc_transcript_quality"]["values"]}
    assert "Saludos" in {v["value"] for v in fields["gc_topic"]["values"]}
    assert all("is_empty" in {o["key"] for o in f["operators"]} for f in fields.values())


def test_the_real_queue_and_agent_fields_list_the_real_ones(real_api):
    fields = schema(real_api)
    assert "AIT_Transcription" in {v["label"] for v in fields["queue"]["values"]}
    assert "Javier Del Olmo" in {v["label"] for v in fields["agent"]["values"]}


# --- Consultas ---

def test_filter_by_derived_to_agent(real_api):
    derived = {c.id for c in get_dataset() if c.genesys.derived_to_agent}
    body = run(real_api, cond("gc_derived", "is", True))
    assert derived and {i["id"] for i in body["items"]} == derived
    contained = {c.id for c in get_dataset() if c.genesys.contained_in_bot}
    assert {i["id"] for i in run(real_api, cond("gc_contained", "is", True))["items"]} == contained


def test_filter_by_genesys_text_numeric_and_categorical_fields(real_api):
    assert run(real_api, cond("gc_ani", "contains", "675075376"))["total"] > 0
    assert run(real_api, cond("gc_external_tag", "contains", "javier"))["total"] > 0
    assert run(real_api, cond("gc_topic", "is", "Saludos"))["total"] > 0
    assert run(real_api, cond("gc_handle_s", "gt", 1))["total"] > 0
    partial = {c.id for c in get_dataset() if c.genesys.transcript_quality == "parcial"}
    assert {i["id"] for i in run(real_api, cond("gc_transcript_quality", "is", "parcial"))["items"]} == partial
    assert run(real_api, cond("gc_undelivered", "gte", 1))["total"] == 2


def test_an_unanalysed_field_is_empty_and_matches_nothing_else(real_api):
    assert run(real_api, cond("main_topic", "is_empty"))["total"] == 10
    assert run(real_api, cond("summary", "is_empty"))["total"] == 10
    assert run(real_api, cond("main_topic", "is", "cajeros"))["total"] == 0
    assert run(real_api, cond("main_topic", "is_not", "cajeros"))["total"] == 0  # vacío: no cumple nada salvo «está vacío»
    assert run(real_api, cond("csat", "lt", 5))["total"] == 0
    assert run(real_api, cond("resolution", "not_in", ["resuelta"]))["total"] == 0
    assert run(real_api, cond("summary", "not_contains", "tarjeta"))["total"] == 0
    for operator in ("passes", "fails", "not_applicable"):
        assert run(real_api, cond("check:saludo", operator))["total"] == 0
    assert run(real_api, cond("check:saludo", "is_empty"))["total"] == 10
    assert run(real_api, cond("repeat_contact", "is", False))["total"] == 0


def test_a_field_with_a_value_is_not_empty(real_api):
    assert run(real_api, cond("gc_ani", "is_empty"))["total"] == sum(1 for c in get_dataset() if not c.genesys.ani)
    assert run(real_api, cond("gc_ani", "is_not_empty"))["total"] == sum(1 for c in get_dataset() if c.genesys.ani)


def test_the_transcript_search_covers_bot_turns(real_api):
    bot_text = next(t.text for c in get_dataset() for t in c.turns if t.speaker == "bot")
    found = run(real_api, cond("transcript", "contains", bot_text[:25], speaker="bot"))
    assert found["total"] > 0


def test_the_interpreter_knows_real_queues(real_api):
    body = real_api.post("/api/query/interpret", json={"text": "conversaciones de la cola AIT_Transcription"}).json()
    queues = [c for c in body["query"]["root"]["conditions"] if c["field"] == "queue"]
    assert queues and queues[0]["value"] == real_api.get("/api/catalog").json()["queues"][0]["id"]


# --- Sampling ---

def _sampling(method="aleatorio", size=5, *conditions, **extra) -> SamplingConfig:
    query = {**QS, "root": {"op": "and", "conditions": list(conditions)}}
    return SamplingConfig(query=query, method=method, size=size, **extra)


def test_sampling_draws_only_real_conversations(real_api):
    pool = candidates(_sampling())
    assert len(pool) == 10 and all(c.genesys for c in pool)
    assert len(draw_sample(pool, _sampling(size=4), seed=1)) == 4


@pytest.mark.parametrize("order_by", ["sentimiento", "csat", "duracion", "fecha"])
def test_first_n_orders_even_without_analysis(real_api, order_by):
    config = _sampling("primeros_n", 10, order_by=order_by, order="desc")
    assert len(draw_sample(candidates(config), config, seed=1)) == 10


def test_stratified_sampling_by_unanalysed_main_topic_is_one_group(real_api):
    config = _sampling("estratificado", 4, stratify_by="main_topic")
    assert len(draw_sample(candidates(config), config, seed=1)) == 4


def test_sampling_estimate_counts_real_conversations(real_api):
    body = real_api.post("/api/flows/sampling/estimate", json={"query": {**QS, "root": {"op": "and", "conditions": []}},
                                                                 "size": 3}).json()
    assert (body["available"], body["sample_size"]) == (10, 3)


# --- Variables de los prompts ---

def _conv(short_id):
    return next(c for c in get_dataset() if c.id == real_id(short_id))


def test_the_transcript_variable_includes_bot_turns_and_flags_undelivered_messages(real_api):
    assert "bot:" in render_template("{{transcripcion}}", _conv("f7e79502"))
    text = render_template("{{transcripcion}}", _conv("9e3ec75a"))
    assert "agente: lo estoy revisando, un segundo [no entregado]" in text
    assert text.count("[no entregado]") == 1


def test_the_metadata_variable_carries_the_genesys_analytics(real_api):
    text = render_template("{{metadatos}}", _conv("37dcbccf"))
    for fragment in ("+34675075376", "Javier Del Olmo", "Contenida en el bot", "pendiente de análisis"):
        assert fragment in text
    text = render_template("{{metadatos}}", _conv("7b94988a"))
    assert "Derivada a agente" in text and "Gestión:" in text and "Wrap-up: Default Wrap-up Code" in text


def test_summary_and_main_topic_are_empty_while_the_analysis_is_pending(real_api):
    assert render_template("[{{summary}}][{{main_topic}}]", _conv("7b94988a")) == "[][]"


@pytest.mark.parametrize("output", [
    {"type": "texto"}, {"type": "etiqueta", "labels": ["positivo", "negativo"]},
    {"type": "json", "fields": [{"name": "sentimiento", "type": "numero"}, {"name": "resolucion", "type": "texto"},
                                {"name": "main_topic", "type": "texto"}, {"name": "csat", "type": "numero"}]},
])
def test_the_mock_runner_copes_with_unanalysed_conversations(real_api, output):
    config = PromptConfig(template="{{transcripcion}}", model="mock-preciso", temperature=0.2,
                          output=OutputFormat(**output))
    for conv in get_dataset():
        assert MockPromptRunner().run(config, conv, None) is not None


def test_validation_warns_about_pending_variables_without_blocking_the_run(real_api):
    graph = complete_graph()
    for node in graph["nodes"]:
        if node["type"] == "prompt":
            node["config"]["template"] = "Resume {{summary}} sobre {{main_topic}}"
    body = real_api.post("/api/flows/validate", json=graph).json()
    pending = [i for i in body["issues"] if i["code"] == "analysis_pending"]
    assert len(pending) == 1 and pending[0]["severity"] == "warning"
    assert body["valid"] is True
    flow = real_api.post("/api/flows", json={"name": "Con datos reales"}).json()
    assert real_api.put(f"/api/flows/{flow['id']}/graph", json=graph).status_code == 200
    assert real_api.post(f"/api/flows/{flow['id']}/runs").status_code == 202


def test_validation_does_not_warn_with_synthetic_data(api):
    graph = complete_graph()
    for node in graph["nodes"]:
        if node["type"] == "prompt":
            node["config"]["template"] = "Resume {{summary}}"
    assert api.post("/api/flows/validate", json=graph).json()["issues"] == []


def test_suggestions_skip_empty_values_of_real_conversations(real_api):
    for field in ("queue", "agent", "main_topic", "gc_disconnect_by", "gc_topic", "gc_wrapup"):
        response = real_api.get("/api/query/suggest", params={**QS, "field": field})
        assert response.status_code == 200, (field, response.text)
        assert all(item["value"] is not None for item in response.json()["values"])
    assert real_api.get("/api/query/suggest", params={**QS, "field": "main_topic"}).json()["values"] == []

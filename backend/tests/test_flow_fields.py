"""Output «Guardar en campos» y valores permitidos (FE013, T6; criterios 15, 16, 17, 19 y 22).

Sin PostgreSQL: el origen `real` se simula sobre el dataset sintético (solo cambia la regla de completitud) y la
escritura va a un doble del servicio de ingesta (`FakeWriter`) con `dependency_overrides` sobre `get_analysis_writer`.
"""
import threading

import pytest

from app.config.store import get_config
from app.flows.analysis_writer import WriterUnavailable, get_analysis_writer
from app.flows.llm_runner import LlmPromptRunner
from app.flows.model import OutputConfig, PromptConfig, parse_graph
from app.flows.prompting import PromptRejected
from app.flows.rules import validate
from app.data.store import get_dataset
from app.main import app
from tests.flow_fixtures import SAMPLING, edge, graph, node
from tests.test_flow_runs import by_type, flow_with, run
from tests.test_llm_flows import FakeLlm, _finished, llm  # noqa: F401  (fixture)

BOTH_PROMPT = {
    "template": "Resume la conversación y di su main topic:\n{{transcripcion}}", "provider": "gemini",
    "model": "gemini-3.5-flash-lite", "temperature": 0.2,
    "output": {"type": "json", "fields": [
        {"name": "summary", "type": "texto"},
        {"name": "main_topic", "type": "texto", "options": ["Bloqueo de tarjeta", "Comisiones", "Cajeros"]}]},
}
BOTH_OUTPUT = {"kind": "campo", "overwrite": False, "mappings": [
    {"target": "summary", "source": "summary"}, {"target": "main_topic", "source": "main_topic"}]}
TEXT_PROMPT = {**BOTH_PROMPT, "output": {"type": "texto"}}
LABEL_PROMPT = {**BOTH_PROMPT, "output": {"type": "etiqueta", "labels": ["Bloqueo de tarjeta", "comisiones"]}}


class FakeWriter:
    """Doble del servicio de ingesta: guarda lo que se le pide y decide «escrito» u «omitido» como la base."""

    def __init__(self, existing: dict | None = None, down: bool = False):
        self.existing = existing or {}  # conversation_id → {campo: valor ya guardado}
        self.down = down
        self.calls: list[dict] = []
        self.lock = threading.Lock()

    def write(self, run_id, provider, model, overwrite, items):
        if self.down:
            raise WriterUnavailable("El servicio de ingesta no está disponible")
        with self.lock:
            self.calls.append({"run_id": run_id, "provider": provider, "model": model, "overwrite": overwrite,
                               "items": items})
        outcomes = {}
        for item in items:
            current = self.existing.get(item["conversation_id"], {})
            outcomes[item["conversation_id"]] = {
                target: "escrito" if overwrite or not current.get(target) else "omitido" for target in item["values"]}
        return outcomes


@pytest.fixture
def real_origin(monkeypatch):
    """El origen `real` para las reglas, sin PostgreSQL: los datos siguen siendo los sintéticos."""
    import app.flows.rules as rules
    monkeypatch.setattr(rules, "active_origin", lambda: "real")


@pytest.fixture
def writer():
    fake = FakeWriter()
    app.dependency_overrides[get_analysis_writer] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_analysis_writer, None)


def _flow(prompt: dict, output: dict, size: int = 6) -> dict:
    return graph([node("tmp-s", "sampling", {**SAMPLING, "size": size}), node("tmp-p", "prompt", prompt, x=300),
                  node("tmp-o", "output", output, x=600)], [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])


def _codes(api, payload: dict) -> set[str]:
    return {i["code"] for i in api.post("/api/flows/validate", json=payload).json()["issues"]}


def _both_answer(body):
    return '{"summary": "El cliente pide bloquear su tarjeta.", "main_topic": "Bloqueo de tarjeta"}'


# --- Modelo y catálogo (criterio 15) ---

def test_the_field_output_and_allowed_values_round_trip(api, llm, writer):
    flow = flow_with(api, _flow(BOTH_PROMPT, BOTH_OUTPUT))
    nodes = {n["type"]: n["config"] for n in flow["graph"]["nodes"]}
    assert nodes["output"] == BOTH_OUTPUT
    assert nodes["prompt"]["output"]["fields"][1]["options"] == ["Bloqueo de tarjeta", "Comisiones", "Cajeros"]


def test_the_catalog_offers_the_target_fields(api):
    flows_catalog = api.get("/api/flows/catalog").json()
    # FE014 amplía el catálogo (tests en `test_flow_targets.py`); summary y main topic siguen siendo los primeros.
    assert flows_catalog["target_fields"][:2] == [{"value": "summary", "label": "Summary", "group": "analisis"},
                                                  {"value": "main_topic", "label": "Main topic", "group": "analisis"}]
    assert {"value": "campo", "label": "Guardar en campos de la conversación"} in flows_catalog["output_kinds"]


@pytest.mark.parametrize("output", [
    {"kind": "campo", "mappings": [{"target": "otro", "source": None}]},
    {"kind": "campo", "mappings": [{"target": "summary", "source": None}] * 61},  # más de `MAX_MAPPINGS`
    {"kind": "campo", "overwrite": "sí"},
])
def test_impossible_field_outputs_are_refused_on_save(api, output):
    created = api.post("/api/flows", json={"name": "x"}).json()
    response = api.put(f"/api/flows/{created['id']}/graph", json=_flow(TEXT_PROMPT, output))
    assert response.status_code == 422


def test_allowed_values_only_fit_text_fields():
    with pytest.raises(ValueError):
        PromptConfig.model_validate({**BOTH_PROMPT, "output": {"type": "json", "fields": [
            {"name": "urgente", "type": "booleano", "options": ["sí"]}]}})


# --- Completitud (criterio 17) ---

def test_a_complete_one_call_flow_validates(api, llm, real_origin):
    assert not _codes(api, _flow(BOTH_PROMPT, BOTH_OUTPUT))


def test_with_synthetic_data_the_field_output_cannot_run(api, llm):
    assert get_config().sources.origin == "sintetico"
    assert "field_output_requires_real_data" in _codes(api, _flow(BOTH_PROMPT, BOTH_OUTPUT))


@pytest.mark.parametrize("prompt, output, code", [
    # Texto o etiqueta: una sola asignación, sin campo de origen.
    (TEXT_PROMPT, {"kind": "campo", "mappings": [{"target": "summary", "source": "summary"}]}, "invalid_mapping"),
    (TEXT_PROMPT, BOTH_OUTPUT, "invalid_mapping"),
    # JSON: el origen es un campo de texto del esquema.
    (BOTH_PROMPT, {"kind": "campo", "mappings": [{"target": "summary", "source": None}]}, "invalid_mapping"),
    (BOTH_PROMPT, {"kind": "campo", "mappings": [{"target": "summary", "source": "resumen"}]}, "invalid_mapping"),
    # summary necesita texto libre.
    (LABEL_PROMPT, {"kind": "campo", "mappings": [{"target": "summary", "source": None}]}, "summary_requires_text"),
    (BOTH_PROMPT, {"kind": "campo", "mappings": [{"target": "summary", "source": "main_topic"}]},
     "summary_requires_text"),
    # main_topic necesita etiquetas o valores permitidos de la taxonomía activa.
    (TEXT_PROMPT, {"kind": "campo", "mappings": [{"target": "main_topic", "source": None}]},
     "main_topic_requires_taxonomy"),
    (BOTH_PROMPT, {"kind": "campo", "mappings": [{"target": "main_topic", "source": "summary"}]},
     "main_topic_requires_taxonomy"),
    ({**LABEL_PROMPT, "output": {"type": "etiqueta", "labels": ["Bloqueo de tarjeta", "Inventado"]}},
     {"kind": "campo", "mappings": [{"target": "main_topic", "source": None}]}, "main_topic_requires_taxonomy"),
    # Destino repetido en el mismo Output.
    (BOTH_PROMPT, {"kind": "campo", "mappings": [{"target": "summary", "source": "summary"},
                                                 {"target": "summary", "source": "summary"}]},
     "duplicate_target"),
    # Sin asignaciones.
    (TEXT_PROMPT, {"kind": "campo", "mappings": []}, "node_unconfigured"),
])
def test_field_output_rules(api, llm, real_origin, prompt, output, code):
    assert code in _codes(api, _flow(prompt, output))


def test_a_target_repeated_in_two_field_outputs_is_an_error(api, llm, real_origin):
    payload = _flow(BOTH_PROMPT, BOTH_OUTPUT)
    payload["nodes"].append(node("tmp-o2", "output", {"kind": "campo", "mappings": [
        {"target": "main_topic", "source": "main_topic"}]}, x=600, y=200))
    payload["edges"].append(edge("tmp-p", "tmp-o2"))
    assert "duplicate_target" in _codes(api, payload)


def test_a_label_prompt_with_topic_codes_or_names_feeds_main_topic(api, llm, real_origin):
    output = {"kind": "campo", "mappings": [{"target": "main_topic", "source": None}]}
    assert not _codes(api, _flow(LABEL_PROMPT, output))  # «comisiones» es un código; «Bloqueo de tarjeta», un nombre


# --- Valores permitidos en el LLM (criterio 16) ---

def test_allowed_values_go_to_the_provider_as_an_enum_and_are_enforced(llm):
    config = PromptConfig.model_validate(BOTH_PROMPT)
    llm.answer = _both_answer
    assert LlmPromptRunner(llm).run(config, get_dataset()[0], None) == {
        "summary": "El cliente pide bloquear su tarjeta.", "main_topic": "Bloqueo de tarjeta"}
    schema = llm.requests[0]["output"]["schema"]
    assert schema["properties"]["main_topic"] == {"type": "string",
                                                  "enum": ["Bloqueo de tarjeta", "Comisiones", "Cajeros"]}
    assert "main_topic (texto: Bloqueo de tarjeta | Comisiones | Cajeros)" in llm.requests[0]["prompt"]
    llm.answer = lambda body: '{"summary": "x", "main_topic": "bloqueo de TARJETA"}'
    assert LlmPromptRunner(llm).run(config, get_dataset()[0], None)["main_topic"] == "Bloqueo de tarjeta"
    llm.answer = lambda body: '{"summary": "x", "main_topic": "Hipotecas"}'
    with pytest.raises(PromptRejected, match="main_topic"):
        LlmPromptRunner(llm).run(config, get_dataset()[0], None)


# --- Ejecución (criterios 16, 19 y 22) ---

def test_one_call_per_conversation_writes_both_fields_with_the_topic_code(api, llm, writer, real_origin):
    llm.answer = _both_answer
    flow = flow_with(api, _flow(BOTH_PROMPT, BOTH_OUTPUT))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    assert snapshot["status"] == "ok", snapshot["nodes"]
    assert len(llm.requests) == 6  # una llamada por conversación para los dos campos
    [call] = writer.calls
    assert (call["provider"], call["model"], call["overwrite"], call["run_id"]) == (
        "gemini", "gemini-3.5-flash-lite", False, snapshot["id"])
    assert {tuple(sorted(item["values"].items())) for item in call["items"]} == {
        (("main_topic", "bloqueo_tarjeta"), ("summary", "El cliente pide bloquear su tarjeta."))}
    result = next(iter(snapshot["outputs"].values()))
    assert result["kind"] == "campo" and result["destination"] == "Summary + Main topic"
    assert result["result"]["counts"] == {"summary": {"escrito": 6, "omitido": 0, "rechazado": 0, "error": 0},
                                          "main_topic": {"escrito": 6, "omitido": 0, "rechazado": 0, "error": 0}}


def test_existing_values_are_skipped_unless_overwrite(api, llm, writer, real_origin):
    llm.answer = _both_answer
    flow = flow_with(api, _flow(BOTH_PROMPT, BOTH_OUTPUT))
    first = _finished(api, flow, run(api, flow)["id"])
    some = [row["conversation"]["id"] for row in next(iter(first["outputs"].values()))["result"]["rows"]][:2]
    writer.existing = {cid: {"summary": "Resumen anterior"} for cid in some}
    writer.calls.clear()
    second = _finished(api, flow, run(api, flow)["id"])
    counts = next(iter(second["outputs"].values()))["result"]["counts"]
    assert counts["summary"]["omitido"] + counts["summary"]["escrito"] == 6
    assert counts["main_topic"]["escrito"] == 6


def test_rejected_and_failed_conversations_appear_with_their_state(api, llm, writer, real_origin):
    answers = iter(['{"summary": "Bien.", "main_topic": "Cajeros"}', '{"summary": "x", "main_topic": "Hipotecas"}',
                    '{"summary": "Bien.", "main_topic": "Comisiones"}'] * 2)
    lock = threading.Lock()

    def answer(body):
        with lock:
            return next(answers)
    llm.answer = answer
    flow = flow_with(api, _flow({**BOTH_PROMPT, "provider": "gemini"}, BOTH_OUTPUT))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    result = next(iter(snapshot["outputs"].values()))["result"]
    assert len(result["rows"]) == 6
    for target in ("summary", "main_topic"):
        assert result["counts"][target] == {"escrito": 4, "omitido": 0, "rechazado": 2, "error": 0}
        assert sum(result["counts"][target].values()) == 6
    rejected = [row for row in result["rows"] if row["states"]["summary"] == "rechazado"]
    assert all("Hipotecas" in row["reason"] and row["values"] == {} for row in rejected)
    assert sum(len(c["items"]) for c in writer.calls) == 4  # solo se escriben las válidas


def test_a_text_prompt_writes_the_whole_answer_to_summary(api, llm, writer, real_origin):
    llm.answer = lambda body: "  Resumen generado.  "
    output = {"kind": "campo", "overwrite": True, "mappings": [{"target": "summary", "source": None}]}
    flow = flow_with(api, _flow(TEXT_PROMPT, output))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    assert snapshot["status"] == "ok"
    assert writer.calls[0]["overwrite"] is True
    assert {item["values"]["summary"] for item in writer.calls[0]["items"]} == {"Resumen generado."}


def test_writes_go_in_batches_of_one_hundred(api, llm, writer, real_origin):
    llm.answer = lambda body: "Resumen."
    output = {"kind": "campo", "mappings": [{"target": "summary", "source": None}]}
    flow = flow_with(api, _flow(TEXT_PROMPT, output, size=230))
    snapshot = _finished(api, flow, run(api, flow)["id"], timeout=30)
    assert snapshot["status"] == "ok"
    assert [len(c["items"]) for c in writer.calls] == [100, 100, 30]


def test_if_the_ingestion_service_is_down_the_output_fails(api, llm, writer, real_origin):
    writer.down = True
    llm.answer = _both_answer
    flow = flow_with(api, _flow(BOTH_PROMPT, BOTH_OUTPUT))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    output = by_type(flow)["output"][0]
    assert snapshot["status"] == "error"
    assert snapshot["nodes"][output]["status"] == "error"
    assert "servicio de ingesta" in snapshot["nodes"][output]["message"]


def test_simulated_prompts_can_also_feed_field_outputs(api, llm, writer, real_origin):
    prompt = {**TEXT_PROMPT, "provider": "simulado", "model": "mock-rapido"}
    output = {"kind": "campo", "mappings": [{"target": "summary", "source": None}]}
    flow = flow_with(api, _flow(prompt, output))
    assert _finished(api, flow, run(api, flow)["id"])["status"] == "ok"
    assert llm.requests == [] and len(writer.calls[0]["items"]) == 6


def test_the_output_config_keeps_destination_optional_for_field_outputs():
    assert OutputConfig.model_validate(BOTH_OUTPUT).destination is None
    issues = {i.code for i in validate(
        parse_graph(_flow(TEXT_PROMPT, {"kind": "campo", "mappings": [{"target": "summary", "source": None}]})))}
    assert "node_unconfigured" not in issues

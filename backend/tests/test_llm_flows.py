"""Proveedores de LLM en Configuración y ejecución de los prompts con el LLM (FE013, T5; criterios 8 a 14).

El servicio de LLM se sustituye por un doble (`FakeLlm`) con `dependency_overrides` sobre `get_llm_client`.
"""
import threading
import time

import pytest

from app import auth
from app.data.store import get_dataset
from app.flows import catalog
from app.flows.llm_runner import LlmPromptRunner
from app.flows.model import PromptConfig
from app.flows.prompting import PromptFailed, PromptRejected, PromptUnavailable, render_template
from app.llm_client import LlmError, LlmUnavailable, get_llm_client
from app.main import app
from llm.providers import REGISTRY
from tests.flow_fixtures import OUTPUT_METRIC, OUTPUT_TABLE, SAMPLING, edge, graph, node
from tests.test_flow_runs import by_type, detail, flow_with, run

LABELS = ["Positivo", "Neutro", "Negativo"]
GEMINI_LABEL = {"template": "Clasifica: {{transcripcion}}", "provider": "gemini", "model": "gemini-3.5-flash-lite",
                "temperature": 0.3, "output": {"type": "etiqueta", "labels": LABELS}}


class FakeLlm:
    """Doble del servicio de LLM: `answer(body)` devuelve el texto o la excepción que «respondería» el servicio."""

    def __init__(self, keys=None, answer=None, down=False):
        self.keys = {"gemini": True, "openai": False, "anthropic": False, "simulado": True} if keys is None else keys
        self.answer = answer or (lambda body: body["output"].get("labels", ["respuesta"])[0])
        self.down = down
        self.requests: list[dict] = []
        self.lock = threading.Lock()
        self.active = self.peak = 0

    def health(self) -> dict:
        if self.down:
            raise LlmUnavailable("sin conexión")
        return {"status": "ok", "keys": self.keys}

    def complete(self, body: dict) -> dict:
        if self.down:
            raise LlmUnavailable("sin conexión")
        with self.lock:
            self.requests.append(body)
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(0.002)
            result = self.answer(body)
        finally:
            with self.lock:
                self.active -= 1
        if isinstance(result, Exception):
            raise result
        return {"text": result, "provider": body["provider"], "model": body["model"], "usage": None}

    def test_provider(self, name: str, model: str) -> dict:
        if self.down:
            raise LlmUnavailable("sin conexión")
        if not self.keys.get(name):
            raise LlmError(503, f"El proveedor {name} no tiene clave configurada", "missing_key")
        return {"ok": True, "provider": name, "model": model, "message": "El proveedor respondió correctamente"}


@pytest.fixture
def llm():
    fake = FakeLlm()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm_client, None)


def _flow(prompt: dict, output: dict = OUTPUT_TABLE) -> dict:
    return graph([node("tmp-s", "sampling", {**SAMPLING, "size": 12}), node("tmp-p", "prompt", prompt, x=300),
                  node("tmp-o", "output", output, x=600)], [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")])


def _finished(api, flow: dict, run_id: str, timeout: float = 10) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = detail(api, flow, run_id)
        if snapshot["status"] not in ("pendiente", "en_curso"):
            return snapshot
        time.sleep(0.02)
    raise AssertionError("la ejecución no terminó")


def _codes(api, payload: dict) -> set[str]:
    return {i["code"] for i in api.post("/api/flows/validate", json=payload).json()["issues"]}


# --- Catálogo y configuración (criterio 8) ---

def test_gemini_flash_lite_is_the_default_and_every_provider_has_its_models(api):
    assert api.get("/api/config").json()["ai"] == {"provider": "gemini", "model": "gemini-3.5-flash-lite",
                                                   "simulated": False}
    flows_catalog = api.get("/api/flows/catalog").json()
    assert (flows_catalog["default_provider"], flows_catalog["default_model"]) == ("gemini", "gemini-3.5-flash-lite")
    providers = {p["value"]: p for p in flows_catalog["providers"]}
    assert list(providers) == ["gemini", "openai", "anthropic", "simulado"]
    assert [m["value"] for m in providers["gemini"]["models"]][0] == "gemini-3.5-flash-lite"
    assert {m["value"] for m in providers["anthropic"]["models"]} == {"claude-opus-5-5", "claude-sonnet-5-5",
                                                                      "claude-haiku-5-5"}
    temperature = {m["value"]: m["temperature"] for p in providers.values() for m in p["models"]}
    assert temperature["gemini-3.5-flash-lite"] and not temperature["claude-opus-5-5"]
    assert not temperature["gpt-6.1-sol"]  # no confirmado en la documentación de OpenAI: no se envía


def test_changing_the_provider_changes_the_default_of_new_prompt_nodes(api):
    assert api.put("/api/config/ai", json={"provider": "anthropic", "model": "claude-sonnet-5-5"}).status_code == 200
    flows_catalog = api.get("/api/flows/catalog").json()
    assert (flows_catalog["default_provider"], flows_catalog["default_model"]) == ("anthropic", "claude-sonnet-5-5")


def test_the_llm_service_registry_matches_the_api_catalog():
    assert set(REGISTRY) == set(catalog.PROVIDERS)


# --- Estado y prueba de proveedores (criterio 9) ---

def test_the_ai_status_says_which_providers_have_a_key_never_the_key(api, llm):
    body = api.get("/api/config/ai/status").json()
    assert body["service"] == "disponible"
    assert {p["value"]: p["key_configured"] for p in body["providers"]} == llm.keys


def test_testing_a_provider_reports_success_or_the_service_message(api, llm):
    ok = api.post("/api/config/ai/test/gemini", json={"model": "gemini-3.5-flash-lite"})
    assert ok.status_code == 200 and ok.json()["ok"] is True
    missing = api.post("/api/config/ai/test/openai", json={"model": "gpt-6.1-sol"})
    assert missing.status_code == 200
    assert missing.json() == {"ok": False, "provider": "openai", "model": "gpt-6.1-sol",
                              "message": "El proveedor openai no tiene clave configurada"}
    assert api.post("/api/config/ai/test/gemini", json={"model": "gpt-6.1-sol"}).status_code == 422


def test_without_the_llm_service_status_and_test_answer_503(api, llm):
    llm.down = True
    assert api.get("/api/config/ai/status").status_code == 503
    assert api.post("/api/config/ai/test/gemini", json={"model": "gemini-3.5-flash-lite"}).status_code == 503


def test_testing_needs_config_edit_and_reading_the_status_config_view(api, llm):
    supervisor = auth.get_store().find_by_email("supervisor@bancohorizonte.demo")
    api.headers["Authorization"] = f"Bearer {auth.create_token(supervisor)}"
    assert api.get("/api/config/ai/status").status_code == 200
    assert api.post("/api/config/ai/test/gemini", json={"model": "gemini-3.5-flash-lite"}).status_code == 403


# --- Validación del nodo Prompt (criterio 10) ---

def test_a_prompt_with_a_provider_without_key_cannot_run(api, llm):
    llm.keys["gemini"] = False
    assert "provider_without_key" in _codes(api, _flow(GEMINI_LABEL))


def test_a_model_from_another_provider_is_an_error(api, llm):
    assert "model_not_in_provider" in _codes(api, _flow({**GEMINI_LABEL, "model": "gpt-6.1-sol"}))


def test_if_the_llm_service_is_down_a_real_provider_cannot_run(api, llm):
    llm.down = True
    assert "llm_unavailable" in _codes(api, _flow(GEMINI_LABEL))


def test_a_configured_provider_validates(api, llm):
    assert not _codes(api, _flow(GEMINI_LABEL)) & {"provider_without_key", "model_not_in_provider", "llm_unavailable"}


def test_a_node_without_provider_is_simulated_and_never_calls_the_service(api, llm):
    llm.down = True
    old = {k: v for k, v in GEMINI_LABEL.items() if k != "provider"} | {"model": "mock-rapido"}
    flow = flow_with(api, _flow(old, OUTPUT_METRIC))
    assert "provider" not in flow["graph"]["nodes"][1]["config"]  # el JSON guardado no cambia
    snapshot = _finished(api, flow, run(api, flow)["id"])
    assert snapshot["status"] == "ok" and llm.requests == []


# --- Ejecución con el LLM (criterios 11 a 14) ---

def test_a_gemini_prompt_runs_through_the_service_with_its_temperature(api, llm):
    flow = flow_with(api, _flow(GEMINI_LABEL, OUTPUT_METRIC))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    assert snapshot["status"] == "ok", snapshot
    assert len(llm.requests) == 12
    sent = llm.requests[0]
    assert (sent["provider"], sent["model"], sent["temperature"]) == ("gemini", "gemini-3.5-flash-lite", 0.3)
    assert sent["output"] == {"type": "etiqueta", "labels": LABELS}
    assert "Positivo | Neutro | Negativo" in sent["prompt"]  # instrucción añadida para el formato etiqueta
    output = next(iter(snapshot["outputs"].values()))["result"]
    assert output["total"] == 12 and output["items"][0] == {"label": "Positivo", "count": 12, "percent": 100.0}


def test_models_without_temperature_never_receive_it_and_json_sends_its_schema(llm):
    config = PromptConfig.model_validate({
        "template": "Extrae: {{transcripcion}}", "provider": "anthropic", "model": "claude-opus-5-5", "temperature": 0.7,
        "output": {"type": "json", "fields": [{"name": "motivo", "type": "texto"}, {"name": "urgente", "type": "booleano"},
                                              {"name": "importe", "type": "numero"}]}})
    llm.answer = lambda body: '{"motivo": "bloqueo", "urgente": true, "importe": 12.5}'
    assert LlmPromptRunner(llm).run(config, get_dataset()[0], None) == {"motivo": "bloqueo", "urgente": True,
                                                                         "importe": 12.5}
    sent = llm.requests[0]
    assert sent["temperature"] is None
    assert sent["output"] == {"type": "json", "schema": {
        "type": "object", "additionalProperties": False, "required": ["motivo", "urgente", "importe"],
        "properties": {"motivo": {"type": "string"}, "urgente": {"type": "boolean"}, "importe": {"type": "number"}}}}


def test_the_prompt_sent_to_the_llm_is_always_masked(llm):
    conv = get_dataset()[0]
    turn = conv.turns[0].model_copy(update={"text": "Mi DNI es 12345678Z y mi teléfono 612 345 678"})
    conv = conv.model_copy(update={"turns": [turn, *conv.turns[1:]]})
    config = PromptConfig.model_validate({**GEMINI_LABEL, "output": {"type": "texto"}})
    LlmPromptRunner(llm).run(config, conv, None)
    prompt = llm.requests[0]["prompt"]
    assert "12345678Z" not in prompt and "612 345 678" not in prompt
    assert "[DNI]" in prompt and "[TELÉFONO]" in prompt


def test_a_conversation_without_transcript_is_rejected_without_calling_the_llm(llm):
    # Comprobado en navegador (T9): con la transcripción vacía, el LLM inventa un summary distinto en cada llamada.
    conv = get_dataset()[0].model_copy(update={"turns": []})
    config = PromptConfig.model_validate({**GEMINI_LABEL, "output": {"type": "texto"}})
    with pytest.raises(PromptRejected, match="no tiene transcripción"):
        LlmPromptRunner(llm).run(config, conv, None)
    assert llm.requests == []
    blank = get_dataset()[0].model_copy(update={"turns": [t.model_copy(update={"text": "  "}) for t in get_dataset()[0].turns]})
    with pytest.raises(PromptRejected):
        LlmPromptRunner(llm).run(config, blank, None)
    # Sin {{transcripcion}} en la plantilla, la conversación se envía igual (puede bastar con los metadatos).
    LlmPromptRunner(llm).run(config.model_copy(update={"template": "Resume: {{metadatos}}"}), conv, None)
    assert len(llm.requests) == 1


@pytest.mark.parametrize("answer, expected", [("  El cliente bloquea su tarjeta.  ", "El cliente bloquea su tarjeta."),
                                              ("   ", PromptRejected)])
def test_text_answers_are_trimmed_and_cannot_be_empty(llm, answer, expected):
    llm.answer = lambda body: answer
    config = PromptConfig.model_validate({**GEMINI_LABEL, "output": {"type": "texto"}})
    _check(LlmPromptRunner(llm), config, expected)


@pytest.mark.parametrize("answer, expected", [("negativo", "Negativo"), (" NEUTRO\n", "Neutro"),
                                              ("Négativo", "Negativo"), ("Positivo.", PromptRejected),
                                              ("quizá", PromptRejected)])
def test_label_answers_must_be_one_of_the_labels(llm, answer, expected):
    llm.answer = lambda body: answer
    _check(LlmPromptRunner(llm), PromptConfig.model_validate(GEMINI_LABEL), expected)


@pytest.mark.parametrize("answer", ['{"motivo": "x"}', '{"motivo": 3, "urgente": false}', "no es json",
                                    '{"motivo": "x", "urgente": false, "otro": 1}', '["motivo"]',
                                    '{"motivo": "x", "urgente": 1}'])
def test_json_answers_must_match_the_schema(llm, answer):
    llm.answer = lambda body: answer
    config = PromptConfig.model_validate({**GEMINI_LABEL, "output": {"type": "json", "fields": [
        {"name": "motivo", "type": "texto"}, {"name": "urgente", "type": "booleano"}]}})
    _check(LlmPromptRunner(llm), config, PromptRejected)


def _check(runner, config, expected):
    if isinstance(expected, type):
        with pytest.raises(expected):
            runner.run(config, get_dataset()[0], None)
    else:
        assert runner.run(config, get_dataset()[0], None) == expected


@pytest.mark.parametrize("error, expected", [
    (LlmUnavailable("sin conexión"), PromptUnavailable),
    (LlmError(503, "El proveedor Gemini no tiene clave configurada", "missing_key"), PromptUnavailable),
    (LlmError(502, "El proveedor rechazó la clave", "key_rejected"), PromptUnavailable),
    (LlmError(502, "Gemini respondió 400", "provider_failure"), PromptFailed),
])
def test_service_errors_are_classified(llm, error, expected):
    llm.answer = lambda body: error
    with pytest.raises(expected):
        LlmPromptRunner(llm).run(PromptConfig.model_validate(GEMINI_LABEL), get_dataset()[0], None)


def test_rejected_answers_are_excluded_from_the_outputs_and_counted(api, llm):
    answers = iter(["Positivo", "no sé"] * 6)
    lock = threading.Lock()

    def answer(body):
        with lock:
            return next(answers)
    llm.answer = answer
    flow = flow_with(api, _flow(GEMINI_LABEL, OUTPUT_METRIC))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    prompt = by_type(flow)["prompt"][0]
    assert snapshot["status"] == "ok"
    state = snapshot["nodes"][prompt]
    assert (state["status"], state["processed"], state["rejected"], state["failed"]) == ("ok", 12, 6, 0)
    failures = snapshot["failures"][prompt]
    assert len(failures) == 6 and all(f["status"] == "rechazado" and "no sé" in f["reason"] for f in failures)
    output = next(iter(snapshot["outputs"].values()))["result"]
    assert output["total"] == 6  # solo las válidas


def test_other_provider_failures_count_per_conversation(api, llm):
    calls = iter(range(100))
    lock = threading.Lock()

    def answer(body):
        with lock:
            n = next(calls)
        return LlmError(502, "Gemini respondió 400", "provider_failure") if n % 4 == 0 else "Neutro"
    llm.answer = answer
    flow = flow_with(api, _flow(GEMINI_LABEL))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    prompt = by_type(flow)["prompt"][0]
    assert snapshot["status"] == "ok"
    assert (snapshot["nodes"][prompt]["failed"], snapshot["nodes"][prompt]["rejected"]) == (3, 0)
    assert {f["status"] for f in snapshot["failures"][prompt]} == {"error"}


@pytest.mark.parametrize("error, message", [
    (LlmUnavailable("sin conexión"), "El servicio de LLM no está disponible"),
    (LlmError(502, "El proveedor rechazó la clave", "key_rejected"), "El proveedor rechazó la clave"),
])
def test_an_unavailable_service_or_a_rejected_key_fails_the_node(api, llm, error, message):
    llm.answer = lambda body: error
    flow = flow_with(api, _flow(GEMINI_LABEL))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    types = by_type(flow)
    assert snapshot["status"] == "error"
    assert snapshot["nodes"][types["prompt"][0]]["status"] == "error"
    assert message in snapshot["nodes"][types["prompt"][0]]["message"]
    assert snapshot["nodes"][types["output"][0]]["status"] == "pendiente"


def test_if_every_answer_is_rejected_the_node_fails(api, llm):
    llm.answer = lambda body: "ninguna"
    flow = flow_with(api, _flow(GEMINI_LABEL))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    prompt = by_type(flow)["prompt"][0]
    assert snapshot["nodes"][prompt]["status"] == "error"
    assert "ninguna conversación" in snapshot["nodes"][prompt]["message"].lower()


def test_llm_prompts_run_in_parallel_and_each_row_keeps_its_own_answer(api, llm):
    template = "Resume: {{metadatos}}"
    llm.answer = lambda body: body["prompt"][-60:]
    flow = flow_with(api, _flow({**GEMINI_LABEL, "template": template, "output": {"type": "texto"}}))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    rows = next(iter(snapshot["outputs"].values()))["result"]["rows"]
    assert len(rows) == 12
    assert 1 < llm.peak <= LlmPromptRunner.parallelism
    index = {c.id: c for c in get_dataset()}
    for row in rows:
        conv = index[row["conversation"]["id"]]
        assert row["result"] == render_template(template, conv)[-60:].strip()  # el texto se recorta

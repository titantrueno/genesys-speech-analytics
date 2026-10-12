"""Casos límite de FE013 añadidos en `/test`: cliente del servicio de LLM, escritor de campos, lotes y plantillas."""
import httpx
import pytest

from app.flows.analysis_writer import IngestionAnalysisWriter, WriterUnavailable
from app.ingestion_client import IngestionClient
from app.llm_client import LlmClient, LlmError, LlmUnavailable
from tests.test_flow_fields import TEXT_PROMPT, FakeWriter, _flow, real_origin, writer  # noqa: F401  (fixtures)
from tests.test_flow_runs import by_type, flow_with, run
from tests.test_llm_flows import _finished, llm  # noqa: F401  (fixture)


def _client(handler, token="t") -> LlmClient:
    return LlmClient("http://llm", token, http=httpx.Client(transport=httpx.MockTransport(handler)))


# --- Cliente del servicio de LLM (app/llm_client.py) ---

def test_the_client_sends_its_token_and_returns_the_body():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"text": "ok"})
    assert _client(handler).complete({"provider": "gemini"}) == {"text": "ok"}
    assert seen[0].headers["authorization"] == "Bearer t" and str(seen[0].url) == "http://llm/complete"


@pytest.mark.parametrize("response", [
    httpx.Response(401, json={"detail": "Token interno no válido"}),  # tokens distintos en API y servicio
    httpx.Response(500, text="Internal Server Error"),                 # fallo del propio servicio, sin código
    httpx.Response(502, text="Bad Gateway"),                           # un proxy delante, sin cuerpo del servicio
])
def test_the_service_itself_failing_is_unavailable(response):
    with pytest.raises(LlmUnavailable):
        _client(lambda request: response).complete({})


def test_without_token_or_connection_the_service_is_unavailable():
    with pytest.raises(LlmUnavailable, match="LLM_TOKEN"):
        _client(lambda request: httpx.Response(200, json={}), token=None).health()

    def refuse(request):
        raise httpx.ConnectError("rechazada", request=request)
    with pytest.raises(LlmUnavailable):
        _client(refuse).health()


@pytest.mark.parametrize("status, code", [(503, "missing_key"), (502, "key_rejected"), (502, "provider_failure"),
                                          (404, "unknown_provider")])
def test_provider_errors_keep_their_status_detail_and_code(status, code):
    with pytest.raises(LlmError) as raised:
        _client(lambda request: httpx.Response(status, json={"detail": "Motivo", "code": code})).complete({})
    assert (raised.value.status, raised.value.detail, raised.value.code) == (status, "Motivo", code)


def test_a_validation_error_of_the_service_is_a_provider_failure_with_a_generic_detail():
    body = {"detail": [{"loc": ["body", "model"], "msg": "no válido"}]}
    with pytest.raises(LlmError) as raised:
        _client(lambda request: httpx.Response(422, json=body)).complete({})
    assert (raised.value.code, raised.value.detail) == ("provider_failure", "Error 422")


# --- Escritor de campos (app/flows/analysis_writer.py) ---

def _writer(handler, token="t") -> IngestionAnalysisWriter:
    return IngestionAnalysisWriter(IngestionClient("http://ingesta", token,
                                                   http=httpx.Client(transport=httpx.MockTransport(handler))))


def test_the_writer_posts_the_batch_and_maps_the_outcomes():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"results": [{"conversation_id": "1CO-A", "outcomes": {"summary": "escrito"}}]})
    items = [{"conversation_id": "1CO-A", "values": {"summary": "Resumen."}}]
    assert _writer(handler).write("1RN-X", "gemini", "gemini-3.5-flash-lite", True, items) == {
        "1CO-A": {"summary": "escrito"}}
    assert str(seen[0].url) == "http://ingesta/analysis/fields"
    assert seen[0].headers["authorization"] == "Bearer t"
    assert httpx.Response(200, content=seen[0].content).json() == {
        "run_id": "1RN-X", "provider": "gemini", "model": "gemini-3.5-flash-lite", "overwrite": True, "items": items}


@pytest.mark.parametrize("response", [httpx.Response(422, json={"detail": []}), httpx.Response(401),
                                      httpx.Response(503)])
def test_the_writer_turns_any_rejection_into_unavailable(response):
    with pytest.raises(WriterUnavailable):
        _writer(lambda request: response).write("1RN-X", "gemini", "m", False, [])


def test_the_writer_without_token_is_unavailable():
    with pytest.raises(WriterUnavailable):
        _writer(lambda request: httpx.Response(200, json={"results": []}), token=None).write("r", "p", "m", False, [])


# --- Lotes: un fallo a mitad conserva lo escrito y lo dice ---

class FailingSecondBatch(FakeWriter):
    def write(self, run_id, provider, model, overwrite, items):
        if self.calls:
            raise WriterUnavailable("El servicio de ingesta no está disponible")
        return super().write(run_id, provider, model, overwrite, items)


def test_a_writer_failure_after_the_first_batch_says_how_much_was_saved(api, llm, real_origin):
    from app.flows.analysis_writer import get_analysis_writer
    from app.main import app
    failing = FailingSecondBatch()
    app.dependency_overrides[get_analysis_writer] = lambda: failing
    try:
        llm.answer = lambda body: "Resumen."
        flow = flow_with(api, _flow(TEXT_PROMPT, {"kind": "campo", "mappings": [{"target": "summary"}]}, size=150))
        snapshot = _finished(api, flow, run(api, flow)["id"], timeout=30)
    finally:
        app.dependency_overrides.pop(get_analysis_writer, None)
    output = by_type(flow)["output"][0]
    assert snapshot["nodes"][output]["status"] == "error"
    assert snapshot["nodes"][output]["message"] == (
        "El servicio de ingesta no está disponible: se guardaron 100 de 150 conversaciones.")
    assert len(failing.calls) == 1


# --- Plantillas ---

def test_the_main_topic_template_refuses_more_topics_than_labels(api):
    from app.flows import catalog
    for i in range(catalog.MAX_LABELS):
        body = {"code": f"tema_extra_{i}", "name": f"Tema extra {i}", "description": "", "keywords": [], "active": True}
        assert api.post("/api/config/taxonomy/main-topics", json=body).status_code == 201
    response = api.post("/api/flows", json={"name": "x", "template": "main_topic"})
    assert response.status_code == 422
    assert "Generar summary y main topic" in response.json()["detail"]
    # La de una llamada no tiene ese límite: los valores permitidos admiten hasta 100.
    assert api.post("/api/flows", json={"name": "x", "template": "summary_main_topic"}).status_code == 201


# --- Hallazgos de /review ---

def test_the_api_waits_longer_than_the_service_worst_case():
    # Con 3 intentos de hasta 60 s al proveedor, la API no puede cortar antes y diagnosticar «servicio no disponible».
    from app.llm_client import COMPLETE_TIMEOUT_S
    from llm.main import TIMEOUT_S
    from llm.service import BACKOFF_S
    assert COMPLETE_TIMEOUT_S > (len(BACKOFF_S) + 1) * TIMEOUT_S + sum(BACKOFF_S)


def test_a_simulated_prompt_feeding_real_fields_warns_without_blocking(api, llm, real_origin):
    prompt = {**TEXT_PROMPT, "provider": "simulado", "model": "mock-rapido"}
    payload = _flow(prompt, {"kind": "campo", "mappings": [{"target": "summary"}]})
    body = api.post("/api/flows/validate", json=payload).json()
    warning = next(i for i in body["issues"] if i["code"] == "simulated_values_to_real_data")
    assert warning["severity"] == "warning" and body["valid"] is True
    assert "simulados" in warning["message"]
    # Con un proveedor real no hay aviso.
    real = api.post("/api/flows/validate", json=_flow(TEXT_PROMPT, {"kind": "campo", "mappings": [{"target": "summary"}]}))
    assert "simulated_values_to_real_data" not in {i["code"] for i in real.json()["issues"]}


def test_an_executor_without_writer_fails_the_output_with_a_clear_message():
    from app.flows.model import parse_graph
    from app.flows.prompting import MockPromptRunner
    from app.flows.runs import FlowExecutor, Run
    graph = parse_graph(_flow({**TEXT_PROMPT, "provider": "simulado", "model": "mock-rapido"},
                              {"kind": "campo", "mappings": [{"target": "summary"}]}))
    run_ = Run("1RN-00000000-0000-4000-8000-000000000009", "1FL-X", "1US-X", "X", graph, seed=1)
    FlowExecutor(MockPromptRunner(), 0).execute(run_)
    output = next(n.id for n in graph.nodes if n.type == "output")
    assert run_.nodes[output].status == "error"
    assert run_.nodes[output].message == "No hay dónde guardar los campos: falta el servicio de ingesta."

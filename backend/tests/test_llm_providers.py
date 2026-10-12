"""Adaptadores de los proveedores de LLM (FE013, T4; criterios 4 y 5).

Sin red: cada adaptador se prueba con `httpx.MockTransport`. Se comprueba la petición que envía (URL, cabeceras,
modelo, temperatura, prompt y modo JSON) y el texto que extrae de una respuesta con la forma de la documentación oficial
consultada el 2026-10-12:

- Gemini · https://ai.google.dev/api/generate-content y
  https://ai.google.dev/gemini-api/docs/generate-content/structured-output
- OpenAI · https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create
- Anthropic · Messages API (`POST /v1/messages`, `anthropic-version: 2023-06-01`)
"""
import json

import httpx
import pytest

from llm.providers import REGISTRY
from llm.providers.base import (Completion, CompletionRequest, KeyRejected, OutputSpec, ProviderFailure, Transient)

KEY = "clave-ficticia-de-prueba"
PROMPT = "Resume la conversación:\ncliente: quiero bloquear mi tarjeta"
SCHEMA = {"type": "object", "properties": {"motivo": {"type": "string"}}, "required": ["motivo"],
          "additionalProperties": False}

GEMINI_RESPONSE = {
    "candidates": [{"content": {"role": "model", "parts": [
        {"text": "Razonamiento interno", "thought": True}, {"text": "El cliente pide bloquear su tarjeta."}]},
        "finishReason": "STOP", "index": 0}],
    "usageMetadata": {"promptTokenCount": 21, "candidatesTokenCount": 9, "totalTokenCount": 30},
    "modelVersion": "gemini-3.8-flash", "responseId": "abc",
}
OPENAI_RESPONSE = {
    "id": "chatcmpl-1", "object": "chat.completion", "model": "gpt-6.1-sol",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "El cliente pide bloquear su tarjeta.",
                                         "refusal": None, "annotations": []}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 21, "completion_tokens": 9, "total_tokens": 30},
}
ANTHROPIC_RESPONSE = {
    "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
    "content": [{"type": "thinking", "thinking": "", "signature": "x"},
                {"type": "text", "text": "El cliente pide bloquear su tarjeta."}],
    "stop_reason": "end_turn", "usage": {"input_tokens": 21, "output_tokens": 9},
}


class Recorder:
    def __init__(self, body: dict, status: int = 200):
        self.body, self.status, self.requests = body, status, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)

    @property
    def sent(self) -> dict:
        return json.loads(self.requests[-1].content)


def _complete(name: str, recorder: Recorder, model: str, output=OutputSpec("texto"), temperature=0.2) -> Completion:
    with httpx.Client(transport=httpx.MockTransport(recorder)) as http:
        return REGISTRY[name].complete(CompletionRequest(model=model, prompt=PROMPT, output=output,
                                                         temperature=temperature), KEY, http)


# --- Gemini ---

def test_gemini_sends_generate_content_with_its_key_header():
    recorder = Recorder(GEMINI_RESPONSE)
    result = _complete("gemini", recorder, "gemini-3.8-flash")
    request = recorder.requests[0]
    assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
    assert request.headers["x-goog-api-key"] == KEY and KEY not in str(request.url)
    assert recorder.sent == {"contents": [{"role": "user", "parts": [{"text": PROMPT}]}],
                             "generationConfig": {"temperature": 0.2}}
    assert result == Completion(text="El cliente pide bloquear su tarjeta.", model="gemini-3.8-flash",
                                input_tokens=21, output_tokens=9)


def test_gemini_asks_for_json_with_the_schema_and_omits_an_unsupported_temperature():
    recorder = Recorder(GEMINI_RESPONSE)
    _complete("gemini", recorder, "gemini-3.8-flash", OutputSpec("json", schema=SCHEMA), temperature=None)
    assert recorder.sent["generationConfig"] == {
        "responseFormat": {"text": {"mimeType": "application/json", "schema": SCHEMA}}}


@pytest.mark.parametrize("body, message", [
    ({"promptFeedback": {"blockReason": "SAFETY"}}, "bloqueó el prompt"),
    ({"candidates": [{"content": {"parts": [{"text": "a medias"}]}, "finishReason": "MAX_TOKENS"}]}, "cortada"),
    ({"candidates": [{"finishReason": "SAFETY"}]}, "SAFETY"),
])
def test_gemini_blocked_or_cut_answers_are_failures(body, message):
    with pytest.raises(ProviderFailure, match=message):
        _complete("gemini", Recorder(body), "gemini-3.8-flash")


def test_gemini_reports_an_invalid_key_answered_with_400():
    body = {"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT",
                      "details": [{"reason": "API_KEY_INVALID"}]}}
    with pytest.raises(KeyRejected):
        _complete("gemini", Recorder(body, status=400), "gemini-3.8-flash")


# --- OpenAI ---

def test_openai_sends_chat_completions_with_a_bearer_key():
    recorder = Recorder(OPENAI_RESPONSE)
    result = _complete("openai", recorder, "gpt-6.1-sol")
    request = recorder.requests[0]
    assert str(request.url) == "https://api.openai.com/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert recorder.sent == {"model": "gpt-6.1-sol", "messages": [{"role": "user", "content": PROMPT}],
                             "temperature": 0.2}
    assert result == Completion(text="El cliente pide bloquear su tarjeta.", model="gpt-6.1-sol",
                                input_tokens=21, output_tokens=9)


def test_openai_asks_for_strict_json_schema_and_omits_an_unsupported_temperature():
    recorder = Recorder(OPENAI_RESPONSE)
    _complete("openai", recorder, "gpt-6.1-sol", OutputSpec("json", schema=SCHEMA), temperature=None)
    assert "temperature" not in recorder.sent
    assert recorder.sent["response_format"] == {"type": "json_schema", "json_schema": {
        "name": "resultado", "schema": SCHEMA, "strict": True}}


@pytest.mark.parametrize("change, message", [
    ({"message": {"role": "assistant", "content": None, "refusal": "No puedo ayudar con eso."}}, "declinó"),
    ({"finish_reason": "length"}, "cortada"),
])
def test_openai_refusals_and_cut_answers_are_failures(change, message):
    body = {**OPENAI_RESPONSE, "choices": [{**OPENAI_RESPONSE["choices"][0], **change}]}
    with pytest.raises(ProviderFailure, match=message):
        _complete("openai", Recorder(body), "gpt-6.1-sol")


# --- Anthropic ---

def test_anthropic_sends_messages_with_its_headers_and_server_side_fallback():
    recorder = Recorder(ANTHROPIC_RESPONSE)
    result = _complete("anthropic", recorder, "claude-opus-5-5", temperature=None)
    request = recorder.requests[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == KEY
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert request.headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
    assert recorder.sent == {"model": "claude-opus-5-5", "max_tokens": 16000, "fallbacks": "default",
                             "messages": [{"role": "user", "content": PROMPT}]}
    assert result == Completion(text="El cliente pide bloquear su tarjeta.", model="claude-opus-5-5",
                                input_tokens=21, output_tokens=9)


def test_anthropic_haiku_has_no_server_side_fallback_and_json_uses_output_config():
    recorder = Recorder({**ANTHROPIC_RESPONSE, "model": "claude-haiku-5-5"})
    _complete("anthropic", recorder, "claude-haiku-5-5", OutputSpec("json", schema=SCHEMA), temperature=None)
    assert "anthropic-beta" not in recorder.requests[0].headers
    assert "fallbacks" not in recorder.sent
    assert recorder.sent["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}}


@pytest.mark.parametrize("stop_reason, message", [("refusal", "declinó"), ("max_tokens", "cortada")])
def test_anthropic_refusals_and_cut_answers_are_failures(stop_reason, message):
    with pytest.raises(ProviderFailure, match=message):
        _complete("anthropic", Recorder({**ANTHROPIC_RESPONSE, "stop_reason": stop_reason}), "claude-opus-5-5")


# --- Comunes a los proveedores con red ---

@pytest.mark.parametrize("name, model", [("gemini", "gemini-3.8-flash"), ("openai", "gpt-6.1-sol"),
                                         ("anthropic", "claude-opus-5-5")])
@pytest.mark.parametrize("status, error", [(401, KeyRejected), (403, KeyRejected), (429, Transient),
                                           (500, Transient), (503, Transient), (400, ProviderFailure)])
def test_http_errors_are_classified(name, model, status, error):
    with pytest.raises(error) as raised:
        _complete(name, Recorder({"error": {"message": f"detalle con {KEY}"}}, status=status), model)
    assert KEY not in str(raised.value)  # el cuerpo de error del proveedor nunca se repite


def test_anthropic_overloaded_529_is_transient():
    with pytest.raises(Transient):
        _complete("anthropic", Recorder({"type": "error"}, status=529), "claude-opus-5-5")


@pytest.mark.parametrize("name, model", [("gemini", "gemini-3.8-flash"), ("openai", "gpt-6.1-sol"),
                                         ("anthropic", "claude-opus-5-5")])
def test_an_unexpected_body_is_a_failure(name, model):
    with pytest.raises(ProviderFailure, match="forma inesperada"):
        _complete(name, Recorder({"nada": "útil"}), model)


def test_a_network_error_is_transient():
    def fail(request):
        raise httpx.ConnectError("sin red", request=request)
    with httpx.Client(transport=httpx.MockTransport(fail)) as http, pytest.raises(Transient, match="contactar"):
        REGISTRY["openai"].complete(CompletionRequest("gpt-6.1-sol", PROMPT, OutputSpec("texto")), KEY, http)


# --- Simulado y contrato del registro ---

def test_the_simulated_provider_is_deterministic_and_respects_the_format():
    simulated = REGISTRY["simulado"]
    first = simulated.complete(CompletionRequest("mock-rapido", PROMPT, OutputSpec("texto")), None, None)
    assert first == simulated.complete(CompletionRequest("mock-rapido", PROMPT, OutputSpec("texto")), None, None)
    assert first.text.strip()
    label = simulated.complete(CompletionRequest("mock-rapido", PROMPT, OutputSpec("etiqueta", labels=["a", "b"])),
                               None, None)
    assert label.text in ("a", "b")
    schema = {"type": "object", "properties": {"motivo": {"type": "string"}, "urgente": {"type": "boolean"},
                                               "importe": {"type": "number"}}}
    data = json.loads(simulated.complete(CompletionRequest("mock-rapido", PROMPT, OutputSpec("json", schema=schema)),
                                         None, None).text)
    assert set(data) == {"motivo", "urgente", "importe"}
    assert (type(data["motivo"]), type(data["urgente"]), type(data["importe"])) == (str, bool, int)


def test_every_registered_provider_honours_the_contract():
    assert set(REGISTRY) == {"gemini", "openai", "anthropic", "simulado"}
    for name, provider in REGISTRY.items():
        assert provider.name == name and provider.label
        assert callable(provider.complete)
        assert provider.needs_key == (name != "simulado")
        if provider.needs_key:
            assert provider.key_env == f"{name.upper()}_API_KEY"

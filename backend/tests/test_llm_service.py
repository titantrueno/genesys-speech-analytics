"""Servicio de LLM: rutas, token interno, errores, reintentos, concurrencia y secretos (FE013, T4; criterios 1, 3, 6 y 7)."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient

from llm.main import create_app
from llm.providers.base import Completion, CompletionRequest, OutputSpec
from llm.service import Completer
from llm.settings import Settings
from tests.test_llm_providers import OPENAI_RESPONSE

TOKEN = "token-llm-de-prueba"
KEY = "clave-openai-ficticia-123"
REQUEST = {"provider": "openai", "model": "gpt-6.1-sol", "prompt": "Resume: el cliente pide bloquear su tarjeta",
           "temperature": 0.2, "output": {"type": "texto"}}


class Upstream:
    """Proveedor falso: responde, por orden, los estados indicados y luego 200."""

    def __init__(self, *statuses: int, body=OPENAI_RESPONSE):
        self.statuses, self.body, self.calls = list(statuses), body, 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        status = self.statuses.pop(0) if self.statuses else 200
        body = self.body if status == 200 else {"error": {"message": f"fallo con la clave {KEY}"}}
        return httpx.Response(status, json=body)


def _client(upstream=None, keys=None, sleeps=None, **settings) -> TestClient:
    keys = {"OPENAI_API_KEY": KEY} if keys is None else keys
    http = httpx.Client(transport=httpx.MockTransport(upstream or Upstream()))
    sleep = sleeps.append if sleeps is not None else (lambda _: None)
    app = create_app(Settings(token=TOKEN, api_keys=keys, **settings), http=http, sleep=sleep)
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    return client


def test_health_needs_no_token_and_says_which_keys_are_configured():
    client = _client(keys={"GEMINI_API_KEY": "x"})
    del client.headers["Authorization"]
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "keys": {"gemini": True, "openai": False, "anthropic": False,
                                                       "simulado": True}}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer otro"}, {"Authorization": "Bearer ñ".encode()}])
def test_every_other_route_needs_the_internal_token(headers):
    client = _client()
    client.headers.clear()
    assert client.post("/complete", json=REQUEST, headers=headers).status_code == 401
    assert client.post("/providers/simulado/test", json={"model": "mock-rapido"}, headers=headers).status_code == 401


def test_a_completion_returns_the_text_the_model_and_the_usage():
    upstream = Upstream()
    response = _client(upstream).post("/complete", json=REQUEST)
    assert response.status_code == 200, response.text
    assert response.json() == {"text": "El cliente pide bloquear su tarjeta.", "provider": "openai",
                               "model": "gpt-6.1-sol", "usage": {"input_tokens": 21, "output_tokens": 9}}
    assert upstream.calls == 1


def test_the_simulated_provider_needs_no_key():
    response = _client(keys={}).post("/complete", json={**REQUEST, "provider": "simulado", "model": "mock-rapido",
                                                        "output": {"type": "etiqueta", "labels": ["sí", "no"]}})
    assert response.status_code == 200 and response.json()["text"] in ("sí", "no")


def test_a_provider_without_key_is_503_and_nothing_is_called():
    upstream = Upstream()
    response = _client(upstream, keys={}).post("/complete", json=REQUEST)
    assert response.status_code == 503
    assert response.json() == {"detail": "El proveedor OpenAI no tiene clave configurada", "code": "missing_key"}
    assert upstream.calls == 0


def test_a_rejected_key_is_502_without_retries():
    upstream = Upstream(401)
    response = _client(upstream).post("/complete", json=REQUEST)
    assert response.status_code == 502
    assert response.json() == {"detail": "The provider rejected the key", "code": "key_rejected"}
    assert upstream.calls == 1


@pytest.mark.parametrize("statuses", [(429,), (429, 503), (500, 502)])
def test_rate_limits_and_server_errors_are_retried_up_to_twice(statuses):
    upstream, sleeps = Upstream(*statuses), []
    response = _client(upstream, sleeps=sleeps).post("/complete", json=REQUEST)
    assert response.status_code == 200
    assert upstream.calls == len(statuses) + 1
    assert sleeps == [0.5, 1.0][:len(statuses)]


def test_after_two_retries_the_failure_is_502_without_provider_details():
    upstream = Upstream(503, 503, 503, 503)
    response = _client(upstream).post("/complete", json=REQUEST)
    assert response.status_code == 502
    assert response.json()["detail"] == "OpenAI responded 503"
    assert upstream.calls == 3


def test_other_provider_errors_are_502_without_retries():
    upstream = Upstream(400)
    response = _client(upstream).post("/complete", json=REQUEST)
    assert (response.status_code, response.json()["detail"], upstream.calls) == (502, "OpenAI responded 400", 1)


def test_an_unknown_provider_is_404_and_an_odd_model_name_is_422():
    client = _client()
    assert client.post("/complete", json={**REQUEST, "provider": "otro"}).status_code == 404
    assert client.post("/complete", json={**REQUEST, "model": "../../v1/files"}).status_code == 422


def test_the_provider_test_route_makes_a_minimal_call():
    upstream = Upstream()
    response = _client(upstream).post("/providers/openai/test", json={"model": "gpt-6.1-sol"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "provider": "openai", "model": "gpt-6.1-sol",
                               "message": "The provider responded correctly"}
    assert upstream.calls == 1
    assert _client(keys={}).post("/providers/openai/test", json={"model": "gpt-6.1-sol"}).status_code == 503


def test_a_key_never_appears_in_responses_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    bodies = []
    for upstream in (Upstream(), Upstream(401), Upstream(400), Upstream(503, 503, 503)):
        bodies.append(_client(upstream).post("/complete", json=REQUEST).text)
    assert all(KEY not in body for body in bodies)
    assert KEY not in caplog.text
    assert REQUEST["prompt"] not in caplog.text  # tampoco el prompt ni la respuesta
    assert "El cliente pide bloquear su tarjeta." not in caplog.text
    assert "openai" in caplog.text and "gpt-6.1-sol" in caplog.text  # sí proveedor y modelo


class SlowProvider:
    name, label, needs_key, key_env = "lento", "Lento", False, None

    def __init__(self):
        self.lock, self.active, self.peak = threading.Lock(), 0, 0

    def complete(self, request, key, http):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.05)
        with self.lock:
            self.active -= 1
        return Completion(text="ok", model=request.model)


def test_never_more_than_the_configured_calls_run_at_once():
    provider = SlowProvider()
    completer = Completer(Settings(token=TOKEN, max_concurrency=3), {"lento": provider}, http=None)
    request = CompletionRequest("m", "p", OutputSpec("texto"))
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: completer.complete("lento", request), range(12)))
    assert [r.text for r in results] == ["ok"] * 12
    assert provider.peak == 3

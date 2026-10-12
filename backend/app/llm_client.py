"""Cliente del servicio de LLM (FE013, criterios 9 y 11).

La API es la única que habla con el servicio de LLM: lo usa el nodo Prompt de los flujos y Configuración → Modelos de
IA. Solo lee `LLM_URL` y `LLM_TOKEN` (`app/envfile.py`); las claves de los proveedores las tiene el servicio.

- `LlmUnavailable`: el servicio no responde, falta el token o lo rechaza, o falla él mismo (`5xx` sin código).
- `LlmError`: el servicio responde con un error del proveedor (`detail` y `code`: `missing_key`, `key_rejected`,
  `provider_failure`, `unknown_provider`).
"""
from functools import cache
from typing import Any

import httpx

from app.envfile import api_env

UNAVAILABLE = "El servicio de LLM no está disponible"
DEFAULT_URL = "http://localhost:8002"
HEALTH_TIMEOUT_S = 3.0
# Más que el peor caso del servicio (3 intentos de hasta 60 s más las esperas) y su cola por el límite de concurrencia:
# si la API cortara antes, diagnosticaría «servicio no disponible» ante un proveedor lento (hallazgo de /review).
COMPLETE_TIMEOUT_S = 240.0


class LlmUnavailable(Exception):
    pass


class LlmError(Exception):
    def __init__(self, status: int, detail: str, code: str):
        super().__init__(detail)
        self.status, self.detail, self.code = status, detail, code


class LlmClient:
    def __init__(self, base_url: str, token: str | None, http: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._http = http or httpx.Client()

    def _request(self, method: str, path: str, timeout: float, json: Any = None) -> dict:
        if not self.token:
            raise LlmUnavailable("Falta LLM_TOKEN")
        try:
            response = self._http.request(method, f"{self.base_url}{path}", json=json, timeout=timeout,
                                          headers={"Authorization": f"Bearer {self.token}"})
        except httpx.HTTPError as exc:
            raise LlmUnavailable(type(exc).__name__) from None
        try:
            body = response.json()
        except ValueError:
            body = {}
        code = body.get("code") if isinstance(body, dict) else None
        if response.status_code == 401 or (response.status_code >= 500 and not code):
            raise LlmUnavailable(f"El servicio de LLM respondió {response.status_code}")
        if response.status_code >= 400:
            detail = body.get("detail") if isinstance(body.get("detail"), str) else f"Error {response.status_code}"
            raise LlmError(response.status_code, detail, code or "provider_failure")
        return body

    def health(self) -> dict:
        return self._request("GET", "/health", HEALTH_TIMEOUT_S)

    def complete(self, body: dict) -> dict:
        return self._request("POST", "/complete", COMPLETE_TIMEOUT_S, body)

    def test_provider(self, name: str, model: str) -> dict:
        return self._request("POST", f"/providers/{name}/test", COMPLETE_TIMEOUT_S, {"model": model})


@cache
def _default_client() -> LlmClient:
    env = api_env()
    return LlmClient(env.get("LLM_URL", DEFAULT_URL), env.get("LLM_TOKEN"))


def get_llm_client() -> LlmClient:
    """Dependencia de FastAPI; los tests la sustituyen con `dependency_overrides`."""
    return _default_client()

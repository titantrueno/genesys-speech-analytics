"""Cliente del servicio de ingesta de Genesys (FE011, criterios 20–22).

La API es la única que habla con el servicio de ingesta (el navegador nunca lo hace): comprueba la sesión y los
permisos y le reenvía la petición con el token interno. Si el servicio no responde, rechaza el token (configuración
distinta en los dos procesos) o falla, la API lo trata como no disponible (`503`). Solo lee `INGESTION_URL` e
`INGESTION_TOKEN` (`app/envfile.py`); nunca las credenciales de Genesys.
"""
from functools import cache
from typing import Any

import httpx

from app.envfile import api_env

UNAVAILABLE = "El servicio de ingesta no está disponible"
DEFAULT_URL = "http://localhost:8001"
TIMEOUT_S = 5.0


class IngestionUnavailable(Exception):
    pass


class IngestionClient:
    def __init__(self, base_url: str, token: str | None, http: httpx.Client | None = None,
                 timeout: float = TIMEOUT_S):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._http = http or httpx.Client(timeout=timeout)

    def request(self, method: str, path: str, *, json: Any = None, params: dict | None = None,
                timeout: float | None = None) -> httpx.Response:
        if not self.token:
            raise IngestionUnavailable("Falta INGESTION_TOKEN")
        try:
            # Un tiempo de espera propio solo cuando la operación lo pide (la prueba de conexión llama a Genesys).
            extra = {"timeout": timeout} if timeout else {}
            response = self._http.request(method, f"{self.base_url}{path}", json=json, params=params,
                                          headers={"Authorization": f"Bearer {self.token}"}, **extra)
        except httpx.HTTPError as exc:
            raise IngestionUnavailable(type(exc).__name__) from None
        if response.status_code == 401 or response.status_code >= 500:
            raise IngestionUnavailable(f"El servicio de ingesta respondió {response.status_code}")
        return response


@cache
def _default_client() -> IngestionClient:
    env = api_env()
    return IngestionClient(env.get("INGESTION_URL", DEFAULT_URL), env.get("INGESTION_TOKEN"))


def get_ingestion_client() -> IngestionClient:
    """Dependencia de FastAPI; los tests la sustituyen con `dependency_overrides`."""
    return _default_client()

"""Cliente HTTP de Genesys Cloud (FE011, criterios 3, 4 y 6).

- OAuth *client credentials*; el token se reutiliza hasta 5 minutos antes de caducar.
- `429`: espera lo que diga `Retry-After`. `5xx` y fallos de red: hasta 3 reintentos con espera creciente (1, 2, 4 s).
- `401` de la API: renueva el token una vez; si vuelve a fallar, `GenesysAuthError`. `403`, `404` y el resto de `4xx`,
  sin reintentos.
- Ningún error lleva el secreto, el token ni una URL firmada (`redact`). El `transport`, el reloj y la espera son
  inyectables: los tests usan el Genesys falso de `fake.py` sin red ni esperas reales.
"""
import base64
import re
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.clock import now
from ingestion.genesys.regions import api_host

TOKEN_MARGIN = timedelta(minutes=5)
MAX_RETRIES = 3
MAX_RATE_LIMIT_WAITS = 5
REDACTED_URL = "[URL firmada]"
_URL = re.compile(r"https?://[^\s\"'<>]+")


class GenesysError(Exception):
    def __init__(self, message: str, status: int | None = None, path: str | None = None):
        super().__init__(message)
        self.status = status
        self.path = path


class GenesysAuthError(GenesysError):
    pass


class GenesysForbidden(GenesysError):
    pass


class GenesysNotFound(GenesysError):
    pass


class GenesysClient:
    def __init__(self, client_id: str, client_secret: str, region: str, *, transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], datetime] = now, sleep: Callable[[float], None] = time.sleep,
                 timeout: float = 30.0):
        host = api_host(region)
        self._login_url = f"https://login.{host}/oauth/token"
        self._api = f"https://api.{host}"
        self._client_id = client_id
        self._secret = client_secret
        self._clock = clock
        self._sleep = sleep
        self._http = httpx.Client(transport=transport, timeout=timeout)
        self._token: str | None = None
        self._token_expires: datetime | None = None

    # Redacción -------------------------------------------------------------------------------------------------------

    def redact(self, text: str) -> str:
        """Quita del texto el secreto, el token y cualquier URL que no sea de la propia API (las firmadas)."""
        for secret in (self._secret, self._token):
            if secret:
                text = text.replace(secret, "[oculto]")
        return _URL.sub(lambda m: m.group(0) if m.group(0).startswith(self._api) else REDACTED_URL, text)

    # Token -----------------------------------------------------------------------------------------------------------

    def _access_token(self) -> str:
        if self._token and self._clock() < self._token_expires - TOKEN_MARGIN:
            return self._token
        basic = base64.b64encode(f"{self._client_id}:{self._secret}".encode()).decode()
        response = self._send(lambda: self._http.post(
            self._login_url, data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {basic}"}), "POST", "/oauth/token", auth=True)
        body = response.json()
        self._token = body["access_token"]
        self._token_expires = self._clock() + timedelta(seconds=int(body.get("expires_in", 0)))
        return self._token

    def ensure_token(self) -> None:
        """Obtiene (o reutiliza) el token: comprueba las credenciales antes de empezar una descarga."""
        self._access_token()

    # Peticiones ------------------------------------------------------------------------------------------------------

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._api_call("GET", path, params=params)

    def post(self, path: str, json: Any = None, params: dict | None = None) -> Any:
        return self._api_call("POST", path, json=json, params=params)

    def get_signed(self, url: str) -> Any:
        """Descarga una URL firmada (por ejemplo, una transcripción): sin token y sin mostrar la URL en los errores."""
        return self._send(lambda: self._http.get(url), "GET", REDACTED_URL).json()

    def _api_call(self, method: str, path: str, **kwargs) -> Any:
        for attempt in range(2):
            token = self._access_token()
            try:
                response = self._send(lambda: self._http.request(
                    method, f"{self._api}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs), method, path)
            except GenesysAuthError:
                if attempt:
                    raise
                self._token = None  # token revocado o caducado antes de tiempo: se pide otro una vez
                continue
            return response.json() if response.content else None

    def _send(self, call: Callable[[], httpx.Response], method: str, path: str, auth: bool = False) -> httpx.Response:
        retries = rate_limited = 0
        while True:
            try:
                response = call()
            except httpx.TransportError as exc:
                if retries == MAX_RETRIES:
                    raise GenesysError(self.redact(f"Sin respuesta de Genesys en {method} {path}: {exc}"),
                                       path=path) from None
                self._sleep(float(2 ** retries))
                retries += 1
                continue
            status = response.status_code
            if status < 400:
                return response
            if status == 429 and rate_limited < MAX_RATE_LIMIT_WAITS:
                self._sleep(_retry_after(response, default=float(2 ** rate_limited)))
                rate_limited += 1
                continue
            if status >= 500 and retries < MAX_RETRIES:
                self._sleep(float(2 ** retries))
                retries += 1
                continue
            raise self._error(response, method, path, auth)

    def _error(self, response: httpx.Response, method: str, path: str, auth: bool) -> GenesysError:
        status = response.status_code
        if auth and status in (400, 401):
            return GenesysAuthError("Credenciales de Genesys no válidas", status, path)
        detail = _message(response)
        where = f"{method} {path}"
        if status == 401:
            return GenesysAuthError(self.redact(f"Genesys rechazó el token en {where}"), status, path)
        if status == 403:
            return GenesysForbidden(self.redact(f"Sin permiso en Genesys para {where}: {detail}"), status, path)
        if status == 404:
            return GenesysNotFound(self.redact(f"No existe en Genesys: {where}"), status, path)
        return GenesysError(self.redact(f"Genesys respondió {status} en {where}: {detail}"), status, path)


def _retry_after(response: httpx.Response, default: float) -> float:
    try:
        return max(0.0, float(response.headers.get("Retry-After", default)))
    except ValueError:
        return default


def _message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        return str(body.get("message") or body.get("error_description") or body.get("error") or "")[:300]
    return ""

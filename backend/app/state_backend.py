"""Persistencia del estado de la plataforma (FE015): flujos de insights y secciones de la configuración global.

La API mantiene ese estado en memoria y lo guarda al cambiarlo, para que sobreviva a un reinicio. No escribe en
PostgreSQL: lo hace el servicio de ingesta, único escritor de la base (ADR-008), con el token interno.

Sin `INGESTION_TOKEN` (p. ej. `./scripts/dev.sh --no-db` o los tests) no hay dónde guardar y todo vive en memoria, como
antes. Con token, si el servicio no responde, las lecturas y escrituras de ese estado fallan con `StateUnavailable`
(`503`) en vez de seguir en memoria y perder los cambios en silencio.
"""
from typing import Any, Protocol

from app.ingestion_client import UNAVAILABLE, IngestionClient, IngestionUnavailable, get_ingestion_client


class StateUnavailable(Exception):
    """El servicio de ingesta no puede leer o guardar el estado: la API responde `503`."""

    def __init__(self, detail: str = UNAVAILABLE):
        super().__init__(detail)
        self.detail = detail


class StateBackend(Protocol):
    def load_flows(self) -> list[dict]: ...

    def save_flow(self, record: dict) -> None: ...

    def delete_flow(self, flow_id: str) -> None: ...

    def load_settings(self) -> dict[str, dict]: ...

    def save_setting(self, key: str, value: dict) -> None: ...


class IngestionStateBackend:
    def __init__(self, client: IngestionClient):
        self.client = client

    def _call(self, method: str, path: str, expected: int, json: Any = None) -> Any:
        try:
            response = self.client.request(method, path, json=json)
        except IngestionUnavailable:
            raise StateUnavailable() from None
        if response.status_code != expected:
            raise StateUnavailable(f"The ingestion service rejected the operation ({response.status_code})")
        return response.json() if response.status_code != 204 else None

    def load_flows(self) -> list[dict]:
        return self._call("GET", "/insight-flows", 200)["items"]

    def save_flow(self, record: dict) -> None:
        self._call("PUT", f"/insight-flows/{record['id']}", 200, json=record)

    def delete_flow(self, flow_id: str) -> None:
        self._call("DELETE", f"/insight-flows/{flow_id}", 204)

    def load_settings(self) -> dict[str, dict]:
        return self._call("GET", "/settings", 200)["items"]

    def save_setting(self, key: str, value: dict) -> None:
        self._call("PUT", f"/settings/{key}", 200, json={"value": value})


def default_backend() -> StateBackend | None:
    client = get_ingestion_client()
    return IngestionStateBackend(client) if client.token else None

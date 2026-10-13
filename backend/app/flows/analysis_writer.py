"""Escritura de los campos del análisis en las conversaciones reales (FE013, criterio 20; FE014).

La API no escribe en PostgreSQL: se lo pide al servicio de ingesta, único escritor de la base (ADR-008), con su token
interno. Cada llamada lleva un lote de conversaciones (el ejecutor parte en lotes de 100) con los valores ya validados
y devuelve, por conversación, `outcomes` (por campo: `escrito`, `omitido` o `no_encontrada`) y `reasons` (por qué se
omitió un campo: ya tenía valor, o Genesys ya da el sentimiento).
"""
from typing import Protocol

from fastapi import Depends

from app.ingestion_client import UNAVAILABLE, IngestionClient, IngestionUnavailable, get_ingestion_client

BATCH_SIZE = 100
# Estado de cada campo de cada conversación en el resultado del Output: además de lo que dice la escritura, `rechazado`
# (valor no válido o Prompt rechazado), `sin_valor` (la respuesta dice que no hay nada) y `error`.
FIELD_STATES = ("escrito", "omitido", "rechazado", "sin_valor", "error")


class WriterUnavailable(Exception):
    pass


class AnalysisWriter(Protocol):
    def write(self, run_id: str, provider: str, model: str, overwrite: bool,
              items: list[dict]) -> dict[str, dict[str, dict[str, str]]]: ...


class IngestionAnalysisWriter:
    def __init__(self, client: IngestionClient):
        self.client = client

    def write(self, run_id: str, provider: str, model: str, overwrite: bool,
              items: list[dict]) -> dict[str, dict[str, dict[str, str]]]:
        try:
            response = self.client.request("POST", "/analysis/fields", timeout=60, json={
                "run_id": run_id, "provider": provider, "model": model, "overwrite": overwrite, "items": items})
        except IngestionUnavailable:
            raise WriterUnavailable(UNAVAILABLE) from None
        if response.status_code != 200:
            raise WriterUnavailable(f"El servicio de ingesta rechazó la escritura ({response.status_code})")
        return {r["conversation_id"]: {"outcomes": r["outcomes"], "reasons": r.get("reasons", {})}
                for r in response.json()["results"]}


def get_analysis_writer(client: IngestionClient = Depends(get_ingestion_client)) -> AnalysisWriter:
    """Dependencia de FastAPI; los tests la sustituyen con `dependency_overrides`."""
    return IngestionAnalysisWriter(client)

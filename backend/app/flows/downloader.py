"""Descargas de la caja «Genesys download» de un flujo de insights (FE017).

La API no habla con Genesys ni escribe en PostgreSQL (ADR-008): pide la descarga al servicio de ingesta con su token
interno, sigue su estado y lee su subconjunto (las conversaciones que insertó o actualizó). Los tests sustituyen
`get_downloader` con un descargador falso.
"""
from datetime import datetime
from typing import Protocol
from urllib.parse import quote

import httpx
from fastapi import Depends

from app.ingestion_client import UNAVAILABLE, IngestionClient, IngestionUnavailable, get_ingestion_client


class DownloaderUnavailable(Exception):
    pass


class DownloadRejected(Exception):
    """La ingesta no admite la descarga: ya hay otra en curso de la caja, o el flujo no está guardado en la base."""


class Downloader(Protocol):
    def available(self) -> bool: ...

    def start(self, *, insight_flow_id: str, interval_from: datetime, interval_to: datetime, channels: list[str],
              overwrite: bool, origin: str, timezone: str, user: dict) -> dict: ...

    def status(self, run_id: str) -> dict: ...

    def subset(self, run_id: str) -> list[str]: ...

    def log(self, run_id: str, params: dict) -> httpx.Response: ...


_REJECTIONS = {404: "The flow is not saved in the database: save it and try again",
               409: "This flow is already downloading"}


class IngestionDownloader:
    def __init__(self, client: IngestionClient):
        self.client = client

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            return self.client.request(method, path, **kwargs)
        except IngestionUnavailable:
            raise DownloaderUnavailable(UNAVAILABLE) from None

    def available(self) -> bool:
        try:
            return self.client.request("GET", "/health").status_code == 200
        except IngestionUnavailable:
            return False

    def start(self, *, insight_flow_id: str, interval_from: datetime, interval_to: datetime, channels: list[str],
              overwrite: bool, origin: str, timezone: str, user: dict) -> dict:
        response = self._request("POST", "/insight-downloads", json={
            "insight_flow_id": insight_flow_id, "from": interval_from.isoformat(), "to": interval_to.isoformat(),
            "channels": channels, "overwrite": overwrite, "origin": origin, "timezone": timezone, "user": user})
        if response.status_code in _REJECTIONS:
            raise DownloadRejected(_REJECTIONS[response.status_code])
        if response.status_code != 202:
            raise DownloadRejected(f"The ingestion service rejected the download ({response.status_code})")
        return response.json()

    def status(self, run_id: str) -> dict:
        response = self._request("GET", f"/insight-downloads/{quote(run_id, safe='')}")
        if response.status_code != 200:
            raise DownloaderUnavailable(f"The download {run_id} is not available ({response.status_code})")
        return response.json()

    def subset(self, run_id: str) -> list[str]:
        response = self._request("GET", f"/insight-downloads/{quote(run_id, safe='')}/conversations")
        if response.status_code != 200:
            raise DownloaderUnavailable(f"The download {run_id} is not available ({response.status_code})")
        return response.json()["items"]

    def log(self, run_id: str, params: dict) -> httpx.Response:
        return self._request("GET", f"/insight-downloads/{quote(run_id, safe='')}/log", params=params)


def get_downloader(client: IngestionClient = Depends(get_ingestion_client)) -> Downloader:
    """Dependencia de FastAPI; los tests la sustituyen con `dependency_overrides`."""
    return IngestionDownloader(client)

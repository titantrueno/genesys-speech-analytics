"""Servicio de ingesta simulado en memoria para los tests de la API (FE011, T6), sin PostgreSQL.

Responde como el servicio real (`ingestion/api.py`); `tests/test_downloads_integration.py` comprueba con el servicio
real que sus respuestas cumplen los mismos esquemas, para que este doble no se desvíe.
"""
import itertools
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from app.ingestion_client import IngestionClient, get_ingestion_client
from app.main import app as api_app

TOKEN = "token-interno-de-prueba"
_ids = itertools.count(1)


def _id(prefix: str) -> str:
    return f"{prefix}-00000000-0000-4000-8000-{next(_ids):012d}"


def _now() -> str:
    return datetime(2026, 10, 12, 21, 0, tzinfo=timezone.utc).isoformat()


COUNTERS = {"found": 2, "downloaded": 2, "inserted": 2, "updated": 0, "skipped": 0, "errors": 0,
            "skipped_in_progress": 0, "skipped_existing": 0, "skipped_other_channel": 0, "by_channel": {"voz": 1, "chat": 1},
            "by_quality": {"completa": 1, "parcial": 1, "sin_transcripcion": 0}, "undelivered_messages": 0}


class Stub:
    def __init__(self):
        self.flows: dict[str, dict] = {}
        self.runs: dict[str, dict] = {}
        self.received: list[tuple[str, str, object]] = []
        self.active = False  # con `True`, lanzar responde 409
        self.app = self._build()

    def _build(self) -> FastAPI:
        app = FastAPI()
        stub = self

        @app.middleware("http")
        async def token(request: Request, call_next):
            if request.headers.get("authorization") != f"Bearer {TOKEN}":
                return JSONResponse({"detail": "Token interno no válido"}, status_code=401)
            return await call_next(request)

        def flow_or_404(flow_id: str) -> dict:
            if flow_id not in stub.flows:
                raise HTTPException(404, detail="Flujo no encontrado")
            return stub.flows[flow_id]

        @app.get("/download-flows")
        def list_flows():
            return {"items": list(stub.flows.values())}

        @app.post("/download-flows", status_code=201)
        def create(body: dict = Body(...)):
            stub.received.append(("POST", "/download-flows", body))
            if not body.get("name", "").strip():
                return JSONResponse({"detail": [{"type": "value_error", "loc": ["body", "name"],
                                                 "msg": "El nombre no puede estar vacío", "input": body.get("name"),
                                                 "ctx": {"error": {}}}]}, status_code=422)
            flow = {"id": _id("1FL"), "name": body["name"], "interval": body["interval"], "channels": body["channels"],
                    "schedule": body.get("schedule", {"type": "desactivada"}), "active": body.get("active", True),
                    "overwrite": body.get("overwrite", False),
                    "timezone": body["timezone"], "author": body["author"], "created_at": _now(),
                    "updated_at": _now(), "next_run_at": None, "last_run": None}
            stub.flows[flow["id"]] = flow
            return flow

        @app.get("/download-flows/{flow_id}")
        def get(flow_id: str):
            return flow_or_404(flow_id)

        @app.put("/download-flows/{flow_id}")
        def update(flow_id: str, body: dict = Body(...)):
            stub.received.append(("PUT", f"/download-flows/{flow_id}", body))
            flow = flow_or_404(flow_id)
            flow.update({k: body[k] for k in ("name", "interval", "channels", "schedule", "active", "overwrite", "timezone")
                         if k in body})
            return flow

        @app.delete("/download-flows/{flow_id}", status_code=204)
        def delete(flow_id: str):
            flow_or_404(flow_id)
            del stub.flows[flow_id]
            return Response(status_code=204)

        @app.post("/download-flows/{flow_id}/runs", status_code=202)
        def start(flow_id: str, body: dict | None = Body(None)):
            stub.received.append(("POST", f"/download-flows/{flow_id}/runs", body))
            flow_or_404(flow_id)
            if stub.active:
                raise HTTPException(409, detail="Ya hay una ejecución en curso de este flujo")
            user = (body or {}).get("user")
            run = {"id": _id("1RN"), "flow_id": flow_id, "origin": "manual", "status": "pendiente",
                   "interval": {"from": "2026-10-11T22:00:00+00:00", "to": _now()}, "channels": ["voz", "chat"],
                   "overwrite": False, "counters": COUNTERS, "error": None, "started_by": user, "created_at": _now(), "started_at": None,
                   "finished_at": None, "duration_s": None}
            stub.runs[run["id"]] = run
            return run

        @app.get("/download-flows/{flow_id}/runs")
        def runs(flow_id: str):
            flow_or_404(flow_id)
            return {"items": [r for r in stub.runs.values() if r["flow_id"] == flow_id]}

        @app.get("/download-flows/{flow_id}/runs/{run_id}")
        def run(flow_id: str, run_id: str):
            if run_id not in stub.runs:
                raise HTTPException(404, detail="Run not found")
            return {**stub.runs[run_id], "status": "completada_con_avisos", "started_at": _now(),
                    "finished_at": _now(), "duration_s": 12.5}

        @app.get("/download-flows/{flow_id}/runs/{run_id}/log")
        def log(flow_id: str, run_id: str, after: int = 0, level: str | None = None, format: str = "json"):  # noqa: A002
            entries = [{"id": 1, "at": _now(), "level": "info", "stage": "search", "message": "2 found",
                        "genesys_id": None},
                       {"id": 2, "at": _now(), "level": "aviso", "stage": "normalization",
                        "message": "Partial transcript", "genesys_id": "687f2225-6f3b-4446-bfd3-f5d2b3416814"}]
            entries = [e for e in entries if e["id"] > after and (level is None or e["level"] == level)]
            if format == "text":
                return PlainTextResponse("".join(f"{e['at']} [{e['level']}] {e['message']}\n" for e in entries),
                                         headers={"Content-Disposition": f'attachment; filename="log-{run_id}.txt"'})
            return {"items": entries}

        @app.get("/status")
        def status_():
            return {"region": "eu-west-1", "credentials_configured": True, "database": "ok",
                    "last_test": None,
                    "last_download": {"run_id": _id("1RN"), "flow_id": _id("1FL"), "status": "completada",
                                      "finished_at": _now()},
                    "conversations": {"total": 13, "by_channel": {"voz": 7, "chat": 6},
                                      "by_quality": {"completa": 9, "parcial": 2, "sin_transcripcion": 2}}}

        @app.post("/status/test")
        def test():
            return {"ok": True, "at": _now(), "organization": "SGTO", "region": "eu-west-1",
                    "message": "Connection to Genesys Cloud successful"}

        return app

    def client(self) -> IngestionClient:
        return IngestionClient("http://testserver", TOKEN, http=TestClient(self.app))


@pytest.fixture
def ingestion_stub():
    stub = Stub()
    api_app.dependency_overrides[get_ingestion_client] = stub.client
    yield stub
    api_app.dependency_overrides.pop(get_ingestion_client, None)


@pytest.fixture
def ingestion_down():
    """Servicio de ingesta caído: la conexión se rechaza."""
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexión rechazada", request=request)

    api_app.dependency_overrides[get_ingestion_client] = lambda: IngestionClient(
        "http://ingesta:8001", TOKEN, http=httpx.Client(transport=httpx.MockTransport(refuse)))
    yield
    api_app.dependency_overrides.pop(get_ingestion_client, None)

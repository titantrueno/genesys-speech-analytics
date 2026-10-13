"""Rutas internas de los flujos de descarga (FE011, criterios 13, 15, 18 y 19). Solo las llama la API.

La API comprueba la sesión y los permisos y envía la persona que crea o lanza, y la zona horaria vigente.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Body, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse

from app import ids
from ingestion import db, flows
from ingestion.flows import FlowIn, Person
from ingestion.genesys.client import GenesysAuthError, GenesysClient, GenesysError
from ingestion.pipeline.analyze import Analyzer
from ingestion.runs import LEVELS, RunAlreadyActive, get_run, list_log, list_runs
from ingestion.scheduler import Job, launch


@dataclass
class Context:
    database_url: str
    clock: Callable[[], datetime]
    client_factory: Callable[[], GenesysClient]
    run_in_background: Callable[[Job], None]
    analyzer: Analyzer | None = None
    region: str | None = None
    credentials_configured: bool = False
    last_test: dict | None = None  # última «Probar conexión»; vive en memoria del proceso


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Flow not found")


def build_router(ctx: Context) -> APIRouter:
    router = APIRouter(prefix="/download-flows", tags=["download flows"])

    def flow_or_404(conn, flow_id: str) -> dict:
        flow = flows.get_flow(conn, flow_id)
        if flow is None:
            raise _not_found()
        return flow

    def validated(body: FlowIn) -> FlowIn:
        errors = flows.semantic_errors(body, ctx.clock())
        if errors:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=errors)
        return body

    def run_or_404(flow_id: str, run_id: str) -> dict:
        run_id = ids.normalize(run_id)
        run = get_run(ctx.database_url, run_id) if ids.is_valid(run_id, ids.RUN) else None
        if run is None or run["flow_id"] != flows.valid_flow_id(flow_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
        return run

    @router.get("", summary="Download flows with their last run and the next scheduled one")
    def list_download_flows():
        with db.connect(ctx.database_url) as conn:
            return {"items": flows.list_flows(conn)}

    @router.post("", status_code=status.HTTP_201_CREATED, summary="Creates a download flow")
    def create_download_flow(body: FlowIn):
        validated(body)
        if body.author is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=[{"type": "missing", "loc": ["body", "author"], "msg": "Missing author"}])
        with db.connect(ctx.database_url) as conn:
            return flows.create_flow(conn, body, body.author, ctx.clock())

    @router.get("/{flow_id}", summary="Download flow")
    def get_download_flow(flow_id: str):
        with db.connect(ctx.database_url) as conn:
            return flow_or_404(conn, flow_id)

    @router.put("/{flow_id}", summary="Saves a download flow (the author does not change)")
    def update_download_flow(flow_id: str, body: FlowIn):
        with db.connect(ctx.database_url) as conn:
            flow = flow_or_404(conn, flow_id)
            validated(body)
            return flows.update_flow(conn, flow["id"], body, ctx.clock())

    @router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Borra un flujo y sus ejecuciones")
    def delete_download_flow(flow_id: str):
        with db.connect(ctx.database_url) as conn:
            flow = flow_or_404(conn, flow_id)
            if flows.has_active_run(conn, flow["id"]):
                raise HTTPException(status.HTTP_409_CONFLICT, detail="The flow has a run in progress")
            flows.delete_flow(conn, flow["id"])
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{flow_id}/runs", status_code=status.HTTP_202_ACCEPTED, summary="Runs the flow now")
    def start_download_run(flow_id: str, user: Person | None = Body(None, embed=True)):
        with db.connect(ctx.database_url) as conn:
            flow = flow_or_404(conn, flow_id)
        try:
            run_id = launch(ctx.database_url, flow["id"], "manual", (user.id, user.name) if user else None,
                            ctx.clock(), ctx.client_factory, ctx.run_in_background, ctx.analyzer)
        except RunAlreadyActive:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="This flow is already running") from None
        return get_run(ctx.database_url, run_id)

    @router.get("/{flow_id}/runs", summary="Run history (most recent first)")
    def list_download_runs(flow_id: str):
        with db.connect(ctx.database_url) as conn:
            flow = flow_or_404(conn, flow_id)
        return {"items": list_runs(ctx.database_url, flow["id"])}

    @router.get("/{flow_id}/runs/{run_id}", summary="Status and counters of a run")
    def get_download_run(flow_id: str, run_id: str):
        return run_or_404(flow_id, run_id)

    @router.get("/{flow_id}/runs/{run_id}/log", summary="Log of a run, paginated by `after` and filterable")
    def get_download_run_log(flow_id: str, run_id: str, after: int = Query(0, ge=0),
                             level: str | None = Query(None, pattern=f"^({'|'.join(LEVELS)})$"),
                             format: str = Query("json", pattern="^(json|text)$")):  # noqa: A002
        run = run_or_404(flow_id, run_id)
        entries = list_log(ctx.database_url, run["id"], after, level)
        if format == "json":
            return {"items": entries}
        lines = [f"{e['at']} [{e['level']}] {e['stage']}: {e['message']}"
                 + (f" ({e['genesys_id']})" if e["genesys_id"] else "") for e in entries]
        return PlainTextResponse("\n".join(lines) + "\n", headers={
            "Content-Disposition": f'attachment; filename="log-{run["id"]}.txt"'})

    return router


def build_status_router(ctx: Context) -> APIRouter:
    router = APIRouter(prefix="/status", tags=["estado"])

    @router.get("", summary="Connector status: region, credentials, last test and download, and counts")
    def connector_status():
        reachable = db.ping(ctx.database_url)
        last_download, conversations = None, None
        if reachable:
            with db.connect(ctx.database_url) as conn:
                row = conn.execute("SELECT id, flow_id, status, finished_at FROM download_run "
                                   "WHERE finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1").fetchone()
                if row:
                    last_download = {"run_id": row[0], "flow_id": row[1], "status": row[2],
                                     "finished_at": row[3].isoformat()}
                by_channel = dict(conn.execute("SELECT channel, count(*) FROM conversation GROUP BY channel"))
                by_quality = dict(conn.execute(
                    "SELECT transcript_quality, count(*) FROM conversation GROUP BY transcript_quality"))
            conversations = {"total": sum(by_channel.values()),
                             "by_channel": {channel: by_channel.get(channel, 0) for channel in ("voz", "chat")},
                             "by_quality": {quality: by_quality.get(quality, 0)
                                            for quality in ("completa", "parcial", "sin_transcripcion")}}
        return {"region": ctx.region, "credentials_configured": ctx.credentials_configured,
                "database": "ok" if reachable else "unavailable", "last_test": ctx.last_test,
                "last_download": last_download, "conversations": conversations}

    @router.post("/test", summary="Tests the Genesys credentials and reads the organization")
    def test_connection():
        organization, ok = None, False
        try:
            client = ctx.client_factory()
            client.ensure_token()
            organization = (client.get("/api/v2/organizations/me") or {}).get("name")
            ok, message = True, "Connection to Genesys Cloud successful"
        except GenesysAuthError as exc:
            message = str(exc)
        except GenesysError as exc:
            message = str(exc)  # ya redactado por el cliente
        ctx.last_test = {"ok": ok, "at": ctx.clock().isoformat(), "organization": organization, "region": ctx.region,
                         "message": message}
        return ctx.last_test

    return router

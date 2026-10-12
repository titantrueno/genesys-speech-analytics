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
from ingestion.genesys.client import GenesysClient
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


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Flujo no encontrado")


def build_router(ctx: Context) -> APIRouter:
    router = APIRouter(prefix="/download-flows", tags=["flujos de descarga"])

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
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ejecución no encontrada")
        return run

    @router.get("", summary="Flujos de descarga con su última ejecución y la próxima programada")
    def list_download_flows():
        with db.connect(ctx.database_url) as conn:
            return {"items": flows.list_flows(conn)}

    @router.post("", status_code=status.HTTP_201_CREATED, summary="Crea un flujo de descarga")
    def create_download_flow(body: FlowIn):
        validated(body)
        if body.author is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=[{"type": "missing", "loc": ["body", "author"], "msg": "Falta la autoría"}])
        with db.connect(ctx.database_url) as conn:
            return flows.create_flow(conn, body, body.author, ctx.clock())

    @router.get("/{flow_id}", summary="Flujo de descarga")
    def get_download_flow(flow_id: str):
        with db.connect(ctx.database_url) as conn:
            return flow_or_404(conn, flow_id)

    @router.put("/{flow_id}", summary="Guarda un flujo de descarga (la autoría no cambia)")
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
                raise HTTPException(status.HTTP_409_CONFLICT, detail="El flujo tiene una ejecución en curso")
            flows.delete_flow(conn, flow["id"])
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{flow_id}/runs", status_code=status.HTTP_202_ACCEPTED, summary="Ejecuta el flujo ahora")
    def start_download_run(flow_id: str, user: Person | None = Body(None, embed=True)):
        with db.connect(ctx.database_url) as conn:
            flow = flow_or_404(conn, flow_id)
        try:
            run_id = launch(ctx.database_url, flow["id"], "manual", (user.id, user.name) if user else None,
                            ctx.clock(), ctx.client_factory, ctx.run_in_background, ctx.analyzer)
        except RunAlreadyActive:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Ya hay una ejecución en curso de este flujo") from None
        return get_run(ctx.database_url, run_id)

    @router.get("/{flow_id}/runs", summary="Historial de ejecuciones (la más reciente primero)")
    def list_download_runs(flow_id: str):
        with db.connect(ctx.database_url) as conn:
            flow = flow_or_404(conn, flow_id)
        return {"items": list_runs(ctx.database_url, flow["id"])}

    @router.get("/{flow_id}/runs/{run_id}", summary="Estado y contadores de una ejecución")
    def get_download_run(flow_id: str, run_id: str):
        return run_or_404(flow_id, run_id)

    @router.get("/{flow_id}/runs/{run_id}/log", summary="Log de una ejecución, paginado por `after` y filtrable")
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

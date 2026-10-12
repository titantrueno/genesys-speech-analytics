"""Flujos de descarga de Genesys Cloud (FE011). Lecturas con `flows:view`; escrituras y ejecuciones con `flows:edit`.

La API no guarda nada: comprueba permisos, añade la autoría (al crear), la zona horaria vigente (al guardar) y quién
lanza una ejecución, y delega en el servicio de ingesta. Si el servicio no está disponible, `503`.
"""
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from app.auth import User, require_permission
from app.config.store import get_config
from app.ingestion_client import UNAVAILABLE, IngestionClient, IngestionUnavailable, get_ingestion_client

router = APIRouter(prefix="/api/download-flows", tags=["downloads"])

VIEW = require_permission("flows:view")
EDIT = require_permission("flows:edit")
EDITABLE = ("name", "interval", "channels", "schedule", "active")


def call(client: IngestionClient, method: str, path: str, **kwargs) -> httpx.Response:
    try:
        return client.request(method, path, **kwargs)
    except IngestionUnavailable:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE) from None


def relay(response: httpx.Response) -> Response:
    """Devuelve la respuesta del servicio de ingesta; los `422` solo con la ruta, el mensaje y el tipo de cada error."""
    if response.status_code == status.HTTP_204_NO_CONTENT:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    body = response.json()
    if response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT and isinstance(body.get("detail"), list):
        body = {"detail": [{"loc": issue["loc"], "msg": issue["msg"], "type": issue["type"]}
                           for issue in body["detail"]]}
    return JSONResponse(body, status_code=response.status_code)


def _path(flow_id: str, *rest: str) -> str:
    return "/".join(["/download-flows", quote(flow_id, safe=""), *(quote(part, safe="") for part in rest)])


def _editable(body: dict[str, Any]) -> dict[str, Any]:
    # La zona horaria es la de la plataforma en el momento de guardar: «hoy», «ayer» y la programación se calculan en ella.
    return {**{key: body[key] for key in EDITABLE if key in body}, "timezone": get_config().general.timezone}


@router.get("", dependencies=[Depends(VIEW)])
def list_download_flows(client: IngestionClient = Depends(get_ingestion_client)):
    return relay(call(client, "GET", "/download-flows"))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_download_flow(body: dict[str, Any] = Body(...), user: User = Depends(EDIT),
                         client: IngestionClient = Depends(get_ingestion_client)):
    payload = {**_editable(body), "author": {"id": user.id, "name": user.name}}
    return relay(call(client, "POST", "/download-flows", json=payload))


@router.get("/{flow_id}", dependencies=[Depends(VIEW)])
def get_download_flow(flow_id: str, client: IngestionClient = Depends(get_ingestion_client)):
    return relay(call(client, "GET", _path(flow_id)))


@router.put("/{flow_id}", dependencies=[Depends(EDIT)])
def update_download_flow(flow_id: str, body: dict[str, Any] = Body(...),
                         client: IngestionClient = Depends(get_ingestion_client)):
    return relay(call(client, "PUT", _path(flow_id), json=_editable(body)))


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(EDIT)])
def delete_download_flow(flow_id: str, client: IngestionClient = Depends(get_ingestion_client)):
    return relay(call(client, "DELETE", _path(flow_id)))


@router.post("/{flow_id}/runs", status_code=status.HTTP_202_ACCEPTED)
def start_download_run(flow_id: str, user: User = Depends(EDIT),
                       client: IngestionClient = Depends(get_ingestion_client)):
    return relay(call(client, "POST", _path(flow_id, "runs"), json={"user": {"id": user.id, "name": user.name}}))


@router.get("/{flow_id}/runs", dependencies=[Depends(VIEW)])
def list_download_runs(flow_id: str, client: IngestionClient = Depends(get_ingestion_client)):
    return relay(call(client, "GET", _path(flow_id, "runs")))


@router.get("/{flow_id}/runs/{run_id}", dependencies=[Depends(VIEW)])
def get_download_run(flow_id: str, run_id: str, client: IngestionClient = Depends(get_ingestion_client)):
    return relay(call(client, "GET", _path(flow_id, "runs", run_id)))


@router.get("/{flow_id}/runs/{run_id}/log", dependencies=[Depends(VIEW)])
def get_download_run_log(flow_id: str, run_id: str, after: int = Query(0, ge=0),
                         level: str | None = Query(None, pattern="^(info|aviso|error)$"),
                         format: str = Query("json", pattern="^(json|text)$"),  # noqa: A002
                         client: IngestionClient = Depends(get_ingestion_client)):
    params = {"after": after, "format": format, **({"level": level} if level else {})}
    response = call(client, "GET", _path(flow_id, "runs", run_id, "log"), params=params)
    if format == "text" and response.status_code == status.HTTP_200_OK:
        return Response(response.content, media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": response.headers.get("content-disposition", "attachment")})
    return relay(response)

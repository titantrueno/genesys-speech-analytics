"""Estado de la plataforma guardado por cuenta de la API (FE015): flujos de insights y secciones de la configuración.

La API valida el contenido (el grafo de un flujo, los valores de cada sección) y lo mantiene en memoria; aquí solo se
guarda y se devuelve, para que sobreviva a un reinicio. El servicio de ingesta sigue siendo el único escritor de la
base (ADR-008). Solo comprueba la forma: identificadores y claves válidos y objetos JSON donde se esperan.
"""
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Response, status
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, StringConstraints

from app import ids
from ingestion import db

SETTING_KEY = r"^[a-z][a-z0-9_]{0,39}$"
Text = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class Author(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Text
    name: Text


class InsightFlowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: Text
    author: Author
    graph: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SettingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: dict[str, Any]


def _flow_id(flow_id: str) -> str:
    flow_id = ids.normalize(flow_id)
    if not ids.is_valid(flow_id, ids.FLOW):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Flow not found")
    return flow_id


def _flow(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "author": {"id": row["author_id"], "name": row["author_name"]},
            "graph": row["graph"], "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat()}


def build_state_router(database_url: str, clock: Callable[[], datetime]) -> APIRouter:
    router = APIRouter(tags=["estado de la plataforma"])

    @router.get("/insight-flows", summary="Stored insight flows")
    def list_insight_flows():
        with db.connect(database_url, row_factory=dict_row) as conn:
            rows = conn.execute("SELECT * FROM insight_flow ORDER BY updated_at DESC").fetchall()
        return {"items": [_flow(row) for row in rows]}

    @router.put("/insight-flows/{flow_id}", summary="Saves an insight flow (creates it or replaces it entirely)")
    def put_insight_flow(flow_id: str, body: InsightFlowIn):
        flow_id = _flow_id(flow_id)
        if ids.normalize(body.id) != flow_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail=[{"type": "value_error", "loc": ["body", "id"],
                                         "msg": "Does not match the flow of the path"}])
        with db.connect(database_url, row_factory=dict_row) as conn:
            row = conn.execute(
                "INSERT INTO insight_flow (id, name, author_id, author_name, graph, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, "
                "graph = EXCLUDED.graph, updated_at = EXCLUDED.updated_at RETURNING *",
                (flow_id, body.name, body.author.id, body.author.name, Jsonb(body.graph), body.created_at,
                 body.updated_at)).fetchone()
        return _flow(row)

    @router.delete("/insight-flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT,
                   summary="Deletes an insight flow (does nothing if it does not exist)")
    def delete_insight_flow(flow_id: str):
        with db.connect(database_url) as conn:
            conn.execute("DELETE FROM insight_flow WHERE id = %s", (_flow_id(flow_id),))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/settings", summary="Stored sections of the global settings")
    def list_settings():
        with db.connect(database_url) as conn:
            rows = conn.execute("SELECT key, value FROM platform_setting ORDER BY key").fetchall()
        return {"items": dict(rows)}

    @router.put("/settings/{key}", summary="Saves a section of the global settings")
    def put_setting(body: SettingIn, key: str = Path(pattern=SETTING_KEY)):
        with db.connect(database_url) as conn:
            conn.execute("INSERT INTO platform_setting (key, value, updated_at) VALUES (%s, %s, %s) "
                         "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
                         (key, Jsonb(body.value), clock()))
        return {"key": key, "value": body.value}

    return router

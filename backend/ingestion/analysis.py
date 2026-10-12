"""Escritura de summary y main topic generados por un flujo de insights (FE013, criterios 19 y 20). Solo la llama la API.

El servicio de ingesta es el único que escribe en PostgreSQL (ADR-008). Por conversación, en una transacción: se lee la
fila de `analysis` con `FOR UPDATE`, se escriben los campos vacíos (o todos con `overwrite`) y se anota en `llm_meta`
quién los generó. El `status` de la fila no cambia: el resto del análisis sigue como estaba.
"""
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from psycopg.types.json import Jsonb

from ingestion import db

COLUMNS = {"summary": "summary", "main_topic": "main_topic"}  # lista blanca: el nombre de columna nunca viene de fuera
Target = Literal["summary", "main_topic"]
# Un valor vacío dejaría el campo «escrito» pero vacío, y la siguiente ejecución lo volvería a tomar por pendiente.
Value = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
MAX_ITEMS = 100


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldItem(_Strict):
    conversation_id: str = Field(max_length=60)
    values: dict[Target, Value] = Field(min_length=1)


class FieldsIn(_Strict):
    run_id: str = Field(max_length=60)
    provider: str = Field(max_length=40)
    model: str = Field(max_length=100)
    overwrite: bool
    items: list[FieldItem] = Field(max_length=MAX_ITEMS)


def write_fields(database_url: str, body: FieldsIn, now: datetime) -> list[dict]:
    results = []
    with db.connect(database_url) as conn:
        for item in body.items:
            with conn.transaction():
                row = conn.execute("SELECT summary, main_topic FROM analysis WHERE conversation_id = %s FOR UPDATE",
                                   (item.conversation_id,)).fetchone()
                if row is None:
                    results.append({"conversation_id": item.conversation_id,
                                    "outcomes": {t: "no_encontrada" for t in item.values}})
                    continue
                current = dict(zip(COLUMNS, row))
                chosen = {t: v for t, v in item.values.items() if body.overwrite or not current[t]}
                if chosen:
                    trace = {"provider": body.provider, "model": body.model, "run_id": body.run_id,
                             "at": now.isoformat()}
                    assignments = ", ".join(f"{COLUMNS[t]} = %s" for t in chosen)
                    conn.execute(f"UPDATE analysis SET {assignments}, llm_meta = llm_meta || %s, updated_at = now() "
                                 "WHERE conversation_id = %s",
                                 [*chosen.values(), Jsonb({t: trace for t in chosen}), item.conversation_id])
                results.append({"conversation_id": item.conversation_id,
                                "outcomes": {t: "escrito" if t in chosen else "omitido" for t in item.values}})
    return results


def build_analysis_router(database_url: str, clock: Callable[[], datetime]) -> APIRouter:
    router = APIRouter(prefix="/analysis", tags=["análisis"])

    @router.post("/fields", summary="Escribe summary y main topic generados por un flujo de insights")
    def post_fields(body: FieldsIn):
        return {"results": write_fields(database_url, body, clock())}

    return router

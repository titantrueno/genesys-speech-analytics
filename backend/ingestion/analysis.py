"""Escritura de los campos del análisis generados por un flujo de insights (FE013 y FE014). Solo la llama la API.

El servicio de ingesta es el único que escribe en PostgreSQL (ADR-008). Por conversación, en una transacción: se lee la
fila de `analysis` con `FOR UPDATE`, se escriben los campos vacíos (o todos con `overwrite`) y se anota en `llm_meta`
quién los generó. El `status` de la fila no cambia: el resto del análisis sigue como estaba.

La API ya ha validado el significado de cada valor (rangos, taxonomía, códigos); aquí solo se comprueba su forma, para
que nunca llegue a la base algo que no sea del tipo de su columna.

- «Vacío» es `NULL` (o texto vacío) en los escalares, `NULL` o `[]` en las listas y la **ausencia de la clave** en
  `compliance` y `entities`, que se combinan clave a clave sin borrar las demás.
- `sentiment` solo se escribe si Genesys no da el sentimiento de la conversación (`customer_sentiment`), ni siquiera
  con `overwrite`.
"""
import math
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.types.json import Jsonb

from ingestion import db

# Listas blancas: el nombre de columna nunca viene de fuera.
TEXT_COLUMNS = ("summary", "main_topic", "resolution", "churn_risk")
NUMBER_COLUMNS = ("csat", "effort", "sentiment")
LIST_COLUMNS = ("secondary_topics", "keywords")
COLUMNS = (*TEXT_COLUMNS, *NUMBER_COLUMNS, *LIST_COLUMNS)
# Destinos con clave: `compliance:<código del check>` y `entity:<tipo>` (el mismo patrón y tipos que la API).
CHECK_TARGET = re.compile(r"^compliance:([a-z][a-z0-9_]{1,39})$")
ENTITY_TYPES = ("importe", "producto", "fecha", "comercio")
ENTITY_TARGET = re.compile(rf"^entity:({'|'.join(ENTITY_TYPES)})$")
KEYED = {"compliance": CHECK_TARGET, "entities": ENTITY_TARGET}
MAX_ITEMS = 100
# Límites de forma (hallazgo de /review de FE014): la API ya acota cada destino; esto protege la base.
MAX_TEXT, MAX_LIST = 4000, 100
KEPT, GENESYS_SENTIMENT = "Ya tenía valor", "Genesys ya da el sentimiento"


def _text(value: Any) -> bool:
    # Un texto vacío dejaría el campo «escrito» pero vacío, y la siguiente ejecución lo volvería a tomar por pendiente.
    return isinstance(value, str) and bool(value.strip()) and len(value) <= MAX_TEXT


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _shape_error(target: str, value: Any) -> str | None:
    if target in TEXT_COLUMNS:
        return None if _text(value) else f"se espera un texto no vacío de hasta {MAX_TEXT} caracteres"
    if target in NUMBER_COLUMNS:
        return None if _number(value) else "se espera un número"
    if target in LIST_COLUMNS:
        valid = isinstance(value, list) and len(value) <= MAX_LIST and all(_text(v) for v in value)
        return None if valid else f"se espera una lista de hasta {MAX_LIST} textos"
    if CHECK_TARGET.match(target):
        return None if value is None or isinstance(value, bool) else "se espera true, false o null"
    if ENTITY_TARGET.match(target):
        return None if _text(value) else "se espera un texto no vacío"
    return "campo destino desconocido"


def _split(target: str) -> tuple[str, str | None]:
    """Columna y clave de un destino: `("csat", None)` o `("compliance", "saludo")`."""
    for column, pattern in KEYED.items():
        match = pattern.match(target)
        if match:
            return column, match.group(1)
    return target, None


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldItem(_Strict):
    conversation_id: str = Field(max_length=60)
    values: dict[str, Any] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _shapes(cls, values: dict[str, Any]) -> dict[str, Any]:
        errors = [f"{t}: {e}" for t, v in values.items() if (e := _shape_error(t, v))]
        if errors:
            raise ValueError("; ".join(errors))
        return {t: v.strip() if isinstance(v, str) else v for t, v in values.items()}


class FieldsIn(_Strict):
    run_id: str = Field(max_length=60)
    provider: str = Field(max_length=40)
    model: str = Field(max_length=100)
    overwrite: bool
    items: list[FieldItem] = Field(max_length=MAX_ITEMS)


def _is_empty(current: dict, target: str) -> bool:
    column, key = _split(target)
    if key is not None:
        return key not in (current[column] or {})
    value = current[column]
    return value is None or value == "" or value == []


def _write_one(conn, item: FieldItem, body: FieldsIn, trace: dict) -> dict:
    row = conn.execute(
        f"SELECT {', '.join(f'a.{c}' for c in (*COLUMNS, *KEYED))}, c.customer_sentiment FROM analysis a "
        "JOIN conversation c ON c.id = a.conversation_id WHERE a.conversation_id = %s FOR UPDATE OF a",
        (item.conversation_id,)).fetchone()
    if row is None:
        return {"conversation_id": item.conversation_id,
                "outcomes": {t: "no_encontrada" for t in item.values}, "reasons": {}}
    current = dict(zip((*COLUMNS, *KEYED, "customer_sentiment"), row))
    reasons = {}
    for target in item.values:
        if target == "sentiment" and current["customer_sentiment"] is not None:
            reasons[target] = GENESYS_SENTIMENT
        elif not body.overwrite and not _is_empty(current, target):
            reasons[target] = KEPT
    chosen = {t: v for t, v in item.values.items() if t not in reasons}
    if chosen:
        assignments, params = [], []
        merged: dict[str, dict] = {}
        for target, value in chosen.items():
            column, key = _split(target)
            if key is not None:
                merged.setdefault(column, {})[key] = value
            else:
                assignments.append(f"{column} = %s")
                params.append(Jsonb(value) if column in LIST_COLUMNS else value)
        for column, keys in merged.items():
            assignments.append(f"{column} = coalesce({column}, '{{}}') || %s")
            params.append(Jsonb(keys))
        conn.execute(f"UPDATE analysis SET {', '.join(assignments)}, llm_meta = llm_meta || %s, updated_at = now() "
                     "WHERE conversation_id = %s",
                     [*params, Jsonb({t: trace for t in chosen}), item.conversation_id])
    return {"conversation_id": item.conversation_id,
            "outcomes": {t: "omitido" if t in reasons else "escrito" for t in item.values}, "reasons": reasons}


def write_fields(database_url: str, body: FieldsIn, now: datetime) -> list[dict]:
    trace = {"provider": body.provider, "model": body.model, "run_id": body.run_id, "at": now.isoformat()}
    results = []
    with db.connect(database_url) as conn:
        for item in body.items:
            with conn.transaction():
                results.append(_write_one(conn, item, body, trace))
    return results


def build_analysis_router(database_url: str, clock: Callable[[], datetime]) -> APIRouter:
    router = APIRouter(prefix="/analysis", tags=["análisis"])

    @router.post("/fields", summary="Escribe campos del análisis generados por un flujo de insights")
    def post_fields(body: FieldsIn):
        return {"results": write_fields(database_url, body, clock())}

    return router

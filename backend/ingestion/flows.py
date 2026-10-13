"""Flujos de descarga: modelo, validación, intervalos, programación y persistencia (FE011, criterios 13, 14 y 16).

Un flujo guarda su zona horaria (la de la plataforma cuando se guardó, la envía la API): «hoy», «ayer» y las horas de
la programación se calculan en ella, también en las ejecuciones programadas.
"""
import random
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import Field, field_validator

from app import ids
# Intervalo y programación: compartidos con la caja «Genesys download» de los flujos de insights (FE017).
from app.flows.download_config import (  # noqa: F401  (reexportados: los usan el programador y los tests)
    MAX_DAYS, MAX_EVERY_HOURS, MAX_HOURS, MAX_SPECIFIC_DAYS, Daily, EveryHours, Interval, NoSchedule, RelativeInterval,
    Schedule, SpecificInterval, _error, _localize, _Strict, next_occurrence, resolve_interval)

_rng = random.SystemRandom()
MAX_NAME = 80
ACTIVE = ("pendiente", "en_curso")


class Person(_Strict):
    id: str
    name: str


class FlowIn(_Strict):
    name: str = Field(max_length=MAX_NAME)
    interval: Interval
    channels: list[Literal["voz", "chat"]]
    schedule: Schedule = Schedule({"type": "desactivada"})
    active: bool = True
    overwrite: bool = False
    timezone: str
    author: Person | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not value.strip():
            raise _error("The name cannot be empty")
        return value.strip()

    @field_validator("channels")
    @classmethod
    def _channels(cls, value: list[str]) -> list[str]:
        if not value:
            raise _error("Choose at least one channel")
        return sorted(set(value), key=["voz", "chat"].index)

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise _error(f"Zona horaria desconocida: {value}") from None
        return value


def semantic_errors(flow: FlowIn, now: datetime) -> list[dict]:
    """Reglas que dependen de varios campos o de la hora actual, con la ruta del campo como en un `422` de FastAPI."""
    errors = []
    interval = flow.interval.root
    if isinstance(interval, SpecificInterval):
        if _localize(interval.to, flow.timezone) > now:
            errors.append({"type": "value_error", "loc": ["body", "interval", "to"],
                           "msg": "The interval cannot end in the future"})
        if not isinstance(flow.schedule.root, NoSchedule):
            errors.append({"type": "value_error", "loc": ["body", "schedule"],
                           "msg": "A scheduled download needs a relative interval"})
    return errors


# Persistencia ----------------------------------------------------------------------------------------------------------

def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def valid_flow_id(flow_id: str) -> str | None:
    value = ids.normalize(flow_id)
    return value if ids.is_valid(value, ids.FLOW) else None


def _next_run(flow: FlowIn, now: datetime) -> datetime | None:
    return next_occurrence(flow.schedule, flow.timezone, now) if flow.active else None


def _to_dict(row: dict, last_run: dict | None) -> dict:
    return {"id": row["id"], "name": row["name"], "interval": row["interval"], "channels": row["channels"],
            "schedule": row["schedule"], "active": row["active"], "overwrite": row["overwrite"],
            "timezone": row["timezone"],
            "author": {"id": row["author_id"], "name": row["author_name"]},
            "created_at": _iso(row["created_at"]), "updated_at": _iso(row["updated_at"]),
            "next_run_at": _iso(row["next_run_at"]),
            "last_run": {"id": last_run["id"], "status": last_run["status"], "created_at": _iso(last_run["created_at"])}
            if last_run else None}


_LAST_RUNS = ("SELECT DISTINCT ON (flow_id) flow_id, id, status, created_at FROM download_run "
              "ORDER BY flow_id, created_at DESC")


def list_flows(conn: psycopg.Connection) -> list[dict]:
    cur = conn.cursor(row_factory=dict_row)
    last = {r["flow_id"]: r for r in cur.execute(_LAST_RUNS).fetchall()}
    rows = cur.execute("SELECT * FROM download_flow ORDER BY updated_at DESC").fetchall()
    return [_to_dict(row, last.get(row["id"])) for row in rows]


def get_flow(conn: psycopg.Connection, flow_id: str) -> dict | None:
    flow_id = valid_flow_id(flow_id)
    if flow_id is None:
        return None
    cur = conn.cursor(row_factory=dict_row)
    row = cur.execute("SELECT * FROM download_flow WHERE id = %s", (flow_id,)).fetchone()
    if row is None:
        return None
    last = cur.execute("SELECT id, status, created_at FROM download_run WHERE flow_id = %s "
                       "ORDER BY created_at DESC LIMIT 1", (flow_id,)).fetchone()
    return _to_dict(row, last)


def _values(flow: FlowIn) -> tuple:
    return (flow.name, Jsonb(flow.interval.model_dump(mode="json", by_alias=True)), flow.channels,
            Jsonb(flow.schedule.model_dump(mode="json")), flow.active, flow.overwrite, flow.timezone)


def create_flow(conn: psycopg.Connection, flow: FlowIn, author: Person, now: datetime) -> dict:
    flow_id = ids.new_id(ids.FLOW, _rng)
    conn.execute("INSERT INTO download_flow (name, interval, channels, schedule, active, overwrite, timezone, id, "
                 "author_id, author_name, next_run_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (*_values(flow), flow_id, author.id, author.name, _next_run(flow, now)))
    return get_flow(conn, flow_id)


def update_flow(conn: psycopg.Connection, flow_id: str, flow: FlowIn, now: datetime) -> dict:
    conn.execute("UPDATE download_flow SET name = %s, interval = %s, channels = %s, schedule = %s, active = %s, "
                 "overwrite = %s, timezone = %s, next_run_at = %s, updated_at = now() WHERE id = %s",
                 (*_values(flow), _next_run(flow, now), flow_id))
    return get_flow(conn, flow_id)


def has_active_run(conn: psycopg.Connection, flow_id: str) -> bool:
    return conn.execute("SELECT 1 FROM download_run WHERE flow_id = %s AND status = ANY(%s)",
                        (flow_id, list(ACTIVE))).fetchone() is not None


def delete_flow(conn: psycopg.Connection, flow_id: str) -> None:
    conn.execute("DELETE FROM download_flow WHERE id = %s", (flow_id,))


def refresh_schedules(conn: psycopg.Connection, now: datetime) -> None:
    """Al arrancar: las ejecuciones perdidas mientras el servicio estaba parado no se recuperan (criterio 16)."""
    cur = conn.cursor(row_factory=dict_row)
    for row in cur.execute("SELECT id, schedule, timezone, active FROM download_flow").fetchall():
        schedule = Schedule.model_validate(row["schedule"])
        next_run = next_occurrence(schedule, row["timezone"], now) if row["active"] else None
        conn.execute("UPDATE download_flow SET next_run_at = %s WHERE id = %s", (next_run, row["id"]))


def interrupt_active_runs(conn: psycopg.Connection, now: datetime) -> int:
    """Al arrancar, ninguna ejecución sigue viva: las que quedaron activas acaban en `error`."""
    return conn.execute("UPDATE download_run SET status = 'error', error = %s, finished_at = %s "
                        "WHERE status = ANY(%s)",
                        ("Interrupted by a restart of the ingestion service", now, list(ACTIVE))).rowcount

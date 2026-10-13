"""Flujos de descarga: modelo, validación, intervalos, programación y persistencia (FE011, criterios 13, 14 y 16).

Un flujo guarda su zona horaria (la de la plataforma cuando se guardó, la envía la API): «hoy», «ayer» y las horas de
la programación se calculan en ella, también en las ejecuciones programadas.
"""
import random
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app import ids

_rng = random.SystemRandom()
MAX_NAME = 80
MAX_HOURS, MAX_DAYS, MAX_SPECIFIC_DAYS = 720, 90, 90
MAX_EVERY_HOURS = 24
ACTIVE = ("pendiente", "en_curso")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _error(message: str) -> PydanticCustomError:
    return PydanticCustomError("value_error", message)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RelativeInterval(_Strict):
    type: Literal["relativo"]
    unit: Literal["hoy", "ayer", "horas", "dias"]
    amount: int | None = None

    @model_validator(mode="after")
    def _amount(self):
        if self.unit in ("hoy", "ayer"):
            if self.amount is not None:
                raise _error("“hoy” and “ayer” take no amount")
        elif self.unit == "horas" and not (self.amount is not None and 1 <= self.amount <= MAX_HOURS):
            raise _error(f"The number of hours must be between 1 and {MAX_HOURS}")
        elif self.unit == "dias" and not (self.amount is not None and 1 <= self.amount <= MAX_DAYS):
            raise _error(f"The number of days must be between 1 and {MAX_DAYS}")
        return self


class SpecificInterval(_Strict):
    type: Literal["especifico"]
    from_: datetime = Field(alias="from")
    to: datetime

    @model_validator(mode="after")
    def _order(self):
        if self.from_ >= self.to:
            raise _error("“From” must be before “to”")
        if self.to - self.from_ > timedelta(days=MAX_SPECIFIC_DAYS):
            raise _error(f"The interval cannot exceed {MAX_SPECIFIC_DAYS} days")
        return self


class Interval(RootModel[Annotated[Union[RelativeInterval, SpecificInterval], Field(discriminator="type")]]):
    pass


class NoSchedule(_Strict):
    type: Literal["desactivada"]


class EveryHours(_Strict):
    type: Literal["cada_horas"]
    hours: int

    @field_validator("hours")
    @classmethod
    def _range(cls, value: int) -> int:
        if not 1 <= value <= MAX_EVERY_HOURS:
            raise _error(f"The hours must be between 1 and {MAX_EVERY_HOURS}")
        return value


class Daily(_Strict):
    type: Literal["diaria"]
    time: str

    @field_validator("time")
    @classmethod
    def _format(cls, value: str) -> str:
        if not _HHMM.match(value):
            raise _error("The time must have the format HH:MM")
        return value


class Schedule(RootModel[Annotated[Union[NoSchedule, EveryHours, Daily], Field(discriminator="type")]]):
    pass


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


# Intervalos y programación ---------------------------------------------------------------------------------------------

def _localize(value: datetime, tz: str) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=ZoneInfo(tz))


def _midnight(day: date, tz: str) -> datetime:
    return datetime.combine(day, time(), tzinfo=ZoneInfo(tz))


def resolve_interval(interval: Interval, tz: str, now: datetime) -> tuple[datetime, datetime]:
    """Instantes de inicio y fin de una ejecución lanzada en `now`."""
    value = interval.root
    if isinstance(value, SpecificInterval):
        return _localize(value.from_, tz), _localize(value.to, tz)
    today = now.astimezone(ZoneInfo(tz)).date()
    if value.unit == "hoy":
        return _midnight(today, tz), now
    if value.unit == "ayer":
        return _midnight(today - timedelta(days=1), tz), _midnight(today, tz)
    span = timedelta(hours=value.amount) if value.unit == "horas" else timedelta(days=value.amount)
    return (now.astimezone(timezone.utc) - span).astimezone(now.tzinfo), now


def next_occurrence(schedule: Schedule, tz: str, after: datetime) -> datetime | None:
    """Siguiente ejecución programada estrictamente posterior a `after`, en hora local de `tz`.

    «Cada N horas» se alinea con la medianoche local (cada 5 horas: 00, 05, 10, 15 y 20 h); «diaria», a su hora.
    """
    value = schedule.root
    if isinstance(value, NoSchedule):
        return None
    day = after.astimezone(ZoneInfo(tz)).date()
    for offset in range(3):
        current = day + timedelta(days=offset)
        if isinstance(value, Daily):
            hour, minute = (int(part) for part in value.time.split(":"))
            candidates = [datetime.combine(current, time(hour, minute), tzinfo=ZoneInfo(tz))]
        else:
            candidates = [datetime.combine(current, time(h), tzinfo=ZoneInfo(tz))
                          for h in range(0, 24, value.hours)]
        for candidate in candidates:
            if candidate > after:
                return candidate
    return None


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

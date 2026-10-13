"""Configuración de una descarga de Genesys: intervalo, programación y su resolución en instantes (FE011 y FE017).

La comparten los flujos de descarga del servicio de ingesta (`ingestion/flows.py`) y la caja «Genesys download» de los
flujos de insights (`app/flows/model.py`), para que las dos validen y programen igual. Son modelos y funciones puros.
"""
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator
from pydantic_core import PydanticCustomError

MAX_HOURS, MAX_DAYS, MAX_SPECIFIC_DAYS = 720, 90, 90
MAX_EVERY_HOURS = 24
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

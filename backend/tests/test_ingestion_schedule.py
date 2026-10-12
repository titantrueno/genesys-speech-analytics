"""Intervalos y programación de los flujos de descarga (FE011, T5; criterios 13 y 16). Funciones puras."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from ingestion.flows import Interval, Schedule, next_occurrence, resolve_interval

MADRID = "Europe/Madrid"
UTC = timezone.utc


def _madrid(*args) -> datetime:
    return datetime(*args, tzinfo=ZoneInfo(MADRID))


@pytest.mark.parametrize("interval, now, expected", [
    # «hoy» justo después de medianoche en Madrid: el día empieza a las 22:00 UTC del día anterior (lección 5).
    ({"type": "relativo", "unit": "hoy"}, _madrid(2026, 10, 12, 0, 30),
     (datetime(2026, 10, 11, 22, 0, tzinfo=UTC), _madrid(2026, 10, 12, 0, 30))),
    ({"type": "relativo", "unit": "ayer"}, _madrid(2026, 10, 12, 0, 10),
     (datetime(2026, 10, 10, 22, 0, tzinfo=UTC), datetime(2026, 10, 11, 22, 0, tzinfo=UTC))),
    # «ayer» cruzando el cambio de hora de octubre: el 25 dura 25 horas.
    ({"type": "relativo", "unit": "ayer"}, _madrid(2026, 10, 26, 9, 0),
     (datetime(2026, 10, 24, 22, 0, tzinfo=UTC), datetime(2026, 10, 25, 23, 0, tzinfo=UTC))),
    ({"type": "relativo", "unit": "horas", "amount": 6}, _madrid(2026, 10, 12, 12, 0),
     (_madrid(2026, 10, 12, 6, 0), _madrid(2026, 10, 12, 12, 0))),
    ({"type": "relativo", "unit": "dias", "amount": 2}, _madrid(2026, 10, 12, 12, 0),
     (_madrid(2026, 10, 10, 12, 0), _madrid(2026, 10, 12, 12, 0))),
    ({"type": "especifico", "from": "2026-10-01T08:00", "to": "2026-10-02T20:30"}, _madrid(2026, 10, 12, 12, 0),
     (_madrid(2026, 10, 1, 8, 0), _madrid(2026, 10, 2, 20, 30))),
])
def test_intervals_resolve_in_the_flow_timezone(interval, now, expected):
    start, end = resolve_interval(Interval.model_validate(interval), MADRID, now)
    assert (start, end) == expected
    assert start.tzinfo is not None and end.tzinfo is not None


@pytest.mark.parametrize("schedule, after, expected", [
    ({"type": "desactivada"}, _madrid(2026, 10, 12, 10, 15), None),
    ({"type": "cada_horas", "hours": 1}, _madrid(2026, 10, 12, 10, 15), _madrid(2026, 10, 12, 11, 0)),
    ({"type": "cada_horas", "hours": 1}, _madrid(2026, 10, 12, 11, 0), _madrid(2026, 10, 12, 12, 0)),
    # Cada 5 horas: 00, 05, 10, 15 y 20 h de cada día; tras las 20 h, la siguiente es a medianoche.
    ({"type": "cada_horas", "hours": 5}, _madrid(2026, 10, 12, 21, 0), _madrid(2026, 10, 13, 0, 0)),
    ({"type": "diaria", "time": "07:30"}, _madrid(2026, 10, 12, 7, 0), _madrid(2026, 10, 12, 7, 30)),
    ({"type": "diaria", "time": "07:30"}, _madrid(2026, 10, 12, 8, 0), _madrid(2026, 10, 13, 7, 30)),
])
def test_next_occurrence(schedule, after, expected):
    assert next_occurrence(Schedule.model_validate(schedule), MADRID, after) == expected


def test_next_occurrence_is_strictly_after_the_given_instant():
    schedule = Schedule.model_validate({"type": "diaria", "time": "07:30"})
    at = _madrid(2026, 10, 12, 7, 30)
    assert next_occurrence(schedule, MADRID, at) == _madrid(2026, 10, 13, 7, 30)


def test_a_daily_schedule_keeps_its_local_time_across_the_october_change():
    schedule = Schedule.model_validate({"type": "diaria", "time": "07:30"})
    after = _madrid(2026, 10, 24, 7, 0)  # la primera, el 24 (verano); la segunda, el 25 (invierno)
    first = next_occurrence(schedule, MADRID, after)
    second = next_occurrence(schedule, MADRID, first)
    assert (first.astimezone(UTC).hour, second.astimezone(UTC).hour) == (5, 6)  # 07:30 en verano y en invierno

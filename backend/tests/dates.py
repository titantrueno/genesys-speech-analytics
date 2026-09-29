"""Fechas de los tests relativas a la fecha de referencia del dataset (FE009).

Ningún test fija una fecha del dataset: así la batería pasa con cualquier `DATA_SEED` y `DATA_REFERENCE_DATE`.
"""
from datetime import date, timedelta

from app.data.store import reference_date

DEFAULT_PERIOD_DAYS = 30  # los 30 días que acaban el día anterior a la fecha de referencia (FE001)


def day_ago(days: int) -> date:
    return reference_date() - timedelta(days=days)


def days_ago(days: int) -> str:
    """Fecha ISO relativa a la de referencia, para parámetros y cuerpos de las peticiones."""
    return day_ago(days).isoformat()


def default_period() -> tuple[date, date]:
    """Periodo por defecto calculado aquí, sin usar el del backend."""
    date_to = day_ago(1)
    return date_to - timedelta(days=DEFAULT_PERIOD_DAYS - 1), date_to


def weekday_on_or_before(day: date, weekday: int) -> date:
    """El último `weekday` (0 = lunes) en o antes de `day`."""
    return day - timedelta(days=(day.weekday() - weekday) % 7)

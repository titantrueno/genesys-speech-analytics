"""Reloj compartido por los stores en memoria (flujos, ejecuciones y configuración)."""
import threading
from datetime import datetime, timedelta, timezone

_clock_lock = threading.Lock()
_last_time = datetime.min.replace(tzinfo=timezone.utc)


def now() -> datetime:
    """Hora actual estrictamente creciente, para que el orden por modificación sea estable."""
    global _last_time
    with _clock_lock:
        _last_time = max(datetime.now(timezone.utc), _last_time + timedelta(microseconds=1))
        return _last_time

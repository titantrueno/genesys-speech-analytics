"""Registro de auditoría compartido por la configuración (FE005) y por usuarios y roles (FE006).

Cada store escribe aquí bajo su propio cerrojo, en la misma operación que guarda el cambio. Se pierde al reiniciar la
API, como el resto de escrituras (ADR-002).
"""
import random
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Protocol

from app import ids
from app.clock import now

_rng = random.SystemRandom()


class Actor(Protocol):
    id: str
    name: str


@dataclass(frozen=True)
class AuditEntry:
    id: str
    user_id: str
    user_name: str
    at: datetime
    section: str
    element: str
    before: Any
    after: Any

    def to_dict(self) -> dict:
        return {"id": self.id, "user": {"id": self.user_id, "name": self.user_name}, "at": self.at.isoformat(),
                "section": self.section, "element": self.element, "before": self.before, "after": self.after}


class AuditLog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: list[AuditEntry] = []

    def record(self, actor: Actor, section: str, element: str, before: Any, after: Any) -> AuditEntry:
        entry = AuditEntry(ids.new_id(ids.AUDIT, _rng), actor.id, actor.name, now(), section, element, before, after)
        with self._lock:
            self._entries.append(entry)
        return entry

    def entries(self, sections: Iterable[str] | None = None) -> list[AuditEntry]:
        """Entradas de las secciones indicadas (todas si es `None`), de la más reciente a la más antigua."""
        wanted = None if sections is None else set(sections)
        with self._lock:
            return [e for e in reversed(self._entries) if wanted is None or e.section in wanted]


_log = AuditLog()


def get_audit_log() -> AuditLog:
    return _log


def reset_audit_log() -> None:
    global _log
    _log = AuditLog()

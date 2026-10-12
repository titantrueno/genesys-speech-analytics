"""Repositorio de conversaciones (FE012, ADR-002): la interfaz por la que los servicios obtienen las conversaciones.

Dos implementaciones, una por origen de datos: `SyntheticRepository` (el dataset generado, en memoria) y
`RealRepository` (PostgreSQL de FE011, en `app/data/real.py`). `active_repository()` elige según la configuración global.
`version()` cambia cuando cambian los datos; los cachés derivados se indexan por ella.
"""
from collections import defaultdict
from datetime import timedelta
from functools import cache
from typing import Protocol

from app.models import Conversation

FCR_WINDOW = timedelta(days=7)
SYNTHETIC, REAL = "sintetico", "real"


class DataUnavailable(Exception):
    """El origen activo no responde (PostgreSQL caído con el origen `real`): la API responde `503`."""


class ConversationRepository(Protocol):
    origin: str

    def version(self) -> object: ...

    def conversations(self) -> list[Conversation]: ...

    def index(self) -> dict[str, Conversation]: ...

    def followups(self) -> dict[str, bool]: ...

    def queues(self) -> list[tuple[str, str]]:
        """Colas `(id, nombre)` que ofrecen los filtros."""
        ...

    def agents(self) -> list[tuple[str, str, str | None, str | None]]:
        """Agentes `(id, nombre, id de su cola, nombre de su cola)` que ofrecen los filtros."""
        ...


def followup_map(conversations: list[Conversation]) -> dict[str, bool]:
    """Indica si el cliente volvió a contactar en los 7 días siguientes a cada conversación."""
    from bisect import bisect_right
    by_customer = defaultdict(list)
    for conv in conversations:
        if conv.customer_id is not None:
            by_customer[conv.customer_id].append(conv.started_at)
    for starts in by_customer.values():
        starts.sort()
    index = {}
    for conv in conversations:
        if conv.customer_id is None:  # sin cliente identificado no hay recontacto que detectar
            index[conv.id] = False
            continue
        starts = by_customer[conv.customer_id]
        nxt = bisect_right(starts, conv.started_at)
        index[conv.id] = nxt < len(starts) and starts[nxt] <= conv.started_at + FCR_WINDOW
    return index


class SyntheticRepository:
    origin = SYNTHETIC

    def version(self) -> object:
        return SYNTHETIC

    def conversations(self) -> list[Conversation]:
        return _synthetic_dataset()

    def index(self) -> dict[str, Conversation]:
        return _synthetic_index()

    def followups(self) -> dict[str, bool]:
        return _synthetic_followups()

    def queues(self) -> list[tuple[str, str]]:
        from app.data.catalog import QUEUE_IDS, QUEUES
        return [(QUEUE_IDS[name], name) for name in QUEUES]

    def agents(self) -> list[tuple[str, str, str | None, str | None]]:
        from app.data.catalog import AGENT_IDS, AGENTS_BY_QUEUE, QUEUE_IDS
        return [(AGENT_IDS[name], name, QUEUE_IDS[queue], queue)
                for queue, names in AGENTS_BY_QUEUE.items() for name in names]


@cache
def _synthetic_dataset() -> list[Conversation]:
    import os

    from app.data.generator import generate_dataset
    from app.data.store import reference_date
    return generate_dataset(seed=int(os.environ.get("DATA_SEED", "42")), reference_date=reference_date())


@cache
def _synthetic_index() -> dict[str, Conversation]:
    return {conv.id: conv for conv in _synthetic_dataset()}


@cache
def _synthetic_followups() -> dict[str, bool]:
    return followup_map(_synthetic_dataset())


_synthetic = SyntheticRepository()


def active_repository() -> ConversationRepository:
    from app.config.store import get_config  # import diferido: la configuración depende del dataset
    if get_config().sources.origin == REAL:
        from app.data.real import real_repository
        return real_repository()
    return _synthetic


def cached_by_version(fn):
    """Cachea el resultado de `fn()` mientras no cambien el origen activo ni su versión (FE012).

    Sustituye a `@cache` en lo derivado del dataset: al cambiar de origen o llegar datos nuevos, se recalcula.
    """
    import functools
    cache: dict = {}

    @functools.wraps(fn)
    def wrapper():
        repository = active_repository()
        key = (repository.origin, repository.version())
        if key not in cache:
            cache.clear()
            cache[key] = fn()
        return cache[key]

    wrapper.cache_clear = cache.clear
    return wrapper

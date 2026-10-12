"""Índice de búsqueda en caliente (FE012, criterio 11, ADR-005).

Un índice por origen de datos. La primera vez que se usa un origen se construye en línea; después, si cambia su versión
(una descarga ha insertado o actualizado conversaciones), se lanza **una sola** reconstrucción en un hilo y la búsqueda
sigue usando el índice anterior hasta que el nuevo está listo (swap atómico). Una reconstrucción que falla (PostgreSQL
caído) conserva el índice vigente y se reintenta en la siguiente petición.
"""
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from app.data.repository import ConversationRepository, DataUnavailable, active_repository
from app.models import Conversation
from app.search.engine import SearchEngine

log = logging.getLogger(__name__)


@dataclass
class _Entry:
    version: object
    engine: SearchEngine


class SearchIndex:
    def __init__(self, build: Callable[[list[Conversation]], SearchEngine],
                 repository: Callable[[], ConversationRepository] = active_repository):
        self._build = build
        self._repository = repository
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}
        self._rebuilding: dict[str, threading.Thread] = {}

    def engine(self) -> SearchEngine:
        repository = self._repository()
        origin, version = repository.origin, repository.version()
        with self._lock:
            entry = self._entries.get(origin)
            if entry is None:
                entry = self._entries[origin] = _Entry(version, self._build(repository.conversations()))
            elif entry.version != version and origin not in self._rebuilding:
                thread = threading.Thread(target=self._rebuild, args=(origin, repository), daemon=True,
                                          name=f"search-index-{origin}")
                self._rebuilding[origin] = thread
                thread.start()
            return entry.engine

    def _rebuild(self, origin: str, repository: ConversationRepository) -> None:
        try:
            version = repository.version()
            engine = self._build(repository.conversations())
            with self._lock:
                self._entries[origin] = _Entry(version, engine)
        except DataUnavailable:
            log.warning("No se pudo reconstruir el índice de búsqueda (%s): se conserva el anterior", origin)
        except Exception:  # noqa: BLE001  (un fallo del hilo no debe dejar la reconstrucción marcada como en curso)
            log.exception("Fallo al reconstruir el índice de búsqueda (%s)", origin)
        finally:
            with self._lock:
                self._rebuilding.pop(origin, None)

    def wait(self) -> None:
        """Espera a que acaben las reconstrucciones en curso (tests y apagado)."""
        with self._lock:
            threads = list(self._rebuilding.values())
        for thread in threads:
            thread.join()

    def reset(self) -> None:
        self.wait()
        with self._lock:
            self._entries.clear()

    def has_engine(self, origin: str | None = None) -> bool:
        with self._lock:
            return (origin in self._entries) if origin else bool(self._entries)

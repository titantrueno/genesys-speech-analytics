"""Configuración global (FE005): estado vigente y versión.

Toda escritura pasa por `apply_change`, que guarda y audita (en el registro compartido de `app/audit.py`) bajo el
mismo cerrojo: ningún cambio aceptado queda sin entrada y ninguno rechazado la crea.

Las secciones de preferencias (`general`, `sources`, `privacy` y `ai`, entre ellas el origen de datos) se guardan en
PostgreSQL y se recuperan al arrancar (FE015): un cambio se guarda antes de aplicarse y, si no se puede guardar, se
rechaza (`503`). Si el servicio de ingesta no responde al arrancar, la API sigue con los valores por defecto y lo
reintenta cada `LOAD_RETRY_S`. La taxonomía, los checks, los KPIs y la auditoría siguen en memoria (ADR-002).
"""
import logging
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import date, datetime, tzinfo
from functools import cache
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app import ids
from app.audit import AuditEntry, get_audit_log
from app.auth import User
from app.config.checks import Check, initial_checks
from app.config.kpis import KpiTarget, initial_kpis
from app.config.model import SECTIONS, AiConfig, GeneralConfig, PrivacyConfig, SourcesConfig
from app.config.taxonomy import Topic, initial_main_topics, initial_secondary_topics
from app.flows.catalog import DEFAULT_MODEL, DEFAULT_PROVIDER
from app.clock import now
from app.state_backend import StateBackend, StateUnavailable, default_backend

logger = logging.getLogger(__name__)
# Campos de `Config` que se guardan, con su modelo: la clave en la base es el nombre del campo.
PERSISTED = {"general": GeneralConfig, "sources": SourcesConfig, "privacy": PrivacyConfig, "ai": AiConfig}
LOAD_RETRY_S = 5.0

DEFAULT_GENERAL = GeneralConfig(platform_name="Speech & Text Analytics", timezone="Europe/Madrid", language="es-ES")


@dataclass(frozen=True)
class Connector:
    id: str
    name: str
    channel: str
    status: str
    last_sync: datetime


def _default_connectors() -> dict[str, Connector]:
    started = now()
    connectors = [Connector(ids.stable_id(ids.CONNECTOR, f"genesys-{channel}"), name, channel, "conectado", started)
                  for channel, name in [("voz", "Genesys Cloud · voz transcrita"), ("chat", "Genesys Cloud · chat")]]
    return {c.id: c for c in connectors}


@dataclass(frozen=True)
class Config:
    """Instantánea inmutable: quien la lee no ve cambios a medias."""
    version: int = 0
    general: GeneralConfig = DEFAULT_GENERAL
    sources: SourcesConfig = SourcesConfig(origin="sintetico")
    privacy: PrivacyConfig = PrivacyConfig(pii_masking=True)
    ai: AiConfig = AiConfig(provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL)
    connectors: dict[str, Connector] = field(default_factory=_default_connectors)
    main_topics: dict[str, Topic] = field(default_factory=initial_main_topics)
    secondary_topics: dict[str, Topic] = field(default_factory=initial_secondary_topics)
    checks: dict[str, Check] = field(default_factory=initial_checks)
    kpis: dict[str, KpiTarget] = field(default_factory=initial_kpis)

    def topic_name(self, code: str) -> str:
        """Nombre vigente de un main topic, esté o no activo."""
        topic = self.main_topics.get(code)
        return topic.name if topic else code


Change = Callable[[Config], tuple[Any, Any, dict[str, Any]]]


def stored_sections(values: dict[str, dict]) -> dict[str, Any]:
    """Secciones guardadas que siguen siendo válidas; una que ya no lo es (p. ej. un modelo retirado) se ignora."""
    sections = {}
    for key, model in PERSISTED.items():
        if key not in values:
            continue
        try:
            sections[key] = model.model_validate(values[key])
        except ValueError:
            logger.warning("Sección de configuración guardada no válida, se usa la vigente: %s", key)
    return sections


class ConfigStore:
    def __init__(self, backend: StateBackend | None = None) -> None:
        self._lock = threading.Lock()
        self._config = Config()
        self._backend = backend
        self._loaded = backend is None
        self._next_attempt = 0.0

    def _ensure_loaded(self) -> None:
        """Bajo el cerrojo. Si la carga falla, se sigue con lo que hay en memoria y se reintenta más tarde."""
        if self._loaded or time.monotonic() < self._next_attempt:
            return
        try:
            values = self._backend.load_settings()
        except StateUnavailable as exc:
            logger.warning("No se pudo cargar la configuración guardada (%s); se reintenta en %ss", exc, LOAD_RETRY_S)
            self._next_attempt = time.monotonic() + LOAD_RETRY_S
            return
        sections = stored_sections(values)
        if sections:
            self._config = replace(self._config, version=self._config.version + 1, **sections)
        self._loaded = True

    def get(self) -> Config:
        with self._lock:
            self._ensure_loaded()
            return self._config

    def apply_change(self, user: User, section: str, element: str, change: Change) -> Config:
        """Aplica `change` sobre la configuración vigente y audita el cambio, todo bajo el cerrojo.

        `change` recibe la configuración y devuelve el valor anterior y el nuevo (para la auditoría) y los campos
        de `Config` que sustituye. Si el valor no cambia, no se guarda ni se audita.
        """
        with self._lock:
            self._ensure_loaded()
            before, after, fields = change(self._config)
            if before == after:
                return self._config
            if self._backend:
                for key in PERSISTED.keys() & fields.keys():
                    self._backend.save_setting(key, fields[key].model_dump(mode="json"))
            self._config = replace(self._config, version=self._config.version + 1, **fields)
            get_audit_log().record(user, section, element, before, after)
            return self._config

    def audit(self, section: str | None = None) -> list[AuditEntry]:
        """Entradas de la configuración: el registro es compartido, pero aquí no se ven las de usuarios (FE006)."""
        return get_audit_log().entries([section] if section else SECTIONS)


_store = ConfigStore(default_backend())


def get_config_store() -> ConfigStore:
    return _store


def get_config() -> Config:
    return _store.get()


def reset_config_store(backend: StateBackend | None = None) -> None:
    global _store
    _store = ConfigStore(backend)


def topic_name(code: str) -> str:
    return get_config().topic_name(code)


@cache
def _zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def current_zone() -> tzinfo:
    """Zona horaria configurada: en ella se interpretan los filtros de fecha y los días de las series (FE005)."""
    return _zone(get_config().general.timezone)


def local_day(moment: datetime, zone: tzinfo | None = None) -> date:
    return moment.astimezone(zone or current_zone()).date()

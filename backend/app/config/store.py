"""Configuración global en memoria (FE005): estado vigente y versión.

Toda escritura pasa por `apply_change`, que guarda y audita (en el registro compartido de `app/audit.py`) bajo el
mismo cerrojo: ningún cambio aceptado queda sin entrada y ninguno rechazado la crea. Se pierde al reiniciar la API, como el resto de escrituras (ADR-002).
"""
import threading
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
from app.config.model import SECTIONS, AiConfig, GeneralConfig, PrivacyConfig
from app.config.taxonomy import Topic, initial_main_topics, initial_secondary_topics
from app.clock import now

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
    privacy: PrivacyConfig = PrivacyConfig(pii_masking=True)
    ai: AiConfig = AiConfig(provider="simulado", model="mock-rapido")
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


class ConfigStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._config = Config()

    def get(self) -> Config:
        with self._lock:
            return self._config

    def apply_change(self, user: User, section: str, element: str, change: Change) -> Config:
        """Aplica `change` sobre la configuración vigente y audita el cambio, todo bajo el cerrojo.

        `change` recibe la configuración y devuelve el valor anterior y el nuevo (para la auditoría) y los campos
        de `Config` que sustituye. Si el valor no cambia, no se guarda ni se audita.
        """
        with self._lock:
            before, after, fields = change(self._config)
            if before == after:
                return self._config
            self._config = replace(self._config, version=self._config.version + 1, **fields)
            get_audit_log().record(user, section, element, before, after)
            return self._config

    def audit(self, section: str | None = None) -> list[AuditEntry]:
        """Entradas de la configuración: el registro es compartido, pero aquí no se ven las de usuarios (FE006)."""
        return get_audit_log().entries([section] if section else SECTIONS)


_store = ConfigStore()


def get_config_store() -> ConfigStore:
    return _store


def get_config() -> Config:
    return _store.get()


def reset_config_store() -> None:
    global _store
    _store = ConfigStore()


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

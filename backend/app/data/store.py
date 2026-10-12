"""Fachada de acceso a las conversaciones (FE012): delega en el repositorio del origen activo.

Los servicios siguen llamando a `get_dataset()`, `conversation_index()` y `followup_index()`; qué origen los atiende
(sintético o real) lo decide la configuración global.
"""
import os
from datetime import date, timedelta

from app.data.repository import FCR_WINDOW, active_repository  # noqa: F401  (FCR_WINDOW se reexporta)
from app.models import Conversation


def reference_date() -> date:
    configured = os.environ.get("DATA_REFERENCE_DATE")
    return date.fromisoformat(configured) if configured else date.today()


def get_dataset() -> list[Conversation]:
    return active_repository().conversations()


def followup_index() -> dict[str, bool]:
    return active_repository().followups()


def conversation_index() -> dict[str, Conversation]:
    return active_repository().index()


def default_period_end() -> date:
    """Último día del periodo por defecto: ayer con datos sintéticos (un día completo) y hoy con datos reales, que se
    descargan al día y si no quedarían fuera de la vista inicial (FE012)."""
    from app.config.store import get_config  # import diferido: la configuración depende del dataset
    today = reference_date()
    return today if get_config().sources.origin == "real" else today - timedelta(days=1)

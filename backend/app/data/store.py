"""Fachada de acceso a las conversaciones (FE012): delega en el repositorio del origen activo.

Los servicios siguen llamando a `get_dataset()`, `conversation_index()` y `followup_index()`; qué origen los atiende
(sintético o real) lo decide la configuración global.
"""
import os
from datetime import date

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

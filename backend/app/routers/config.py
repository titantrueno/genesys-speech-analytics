"""API de configuración (FE005). Lecturas con `config:view`; escrituras con `config:edit`; el nombre, público."""
from collections import Counter
from dataclasses import replace
from functools import cache
from typing import Any, Literal, TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, ValidationError

from app import ids
from app.auth import User, require_permission
from app.config.model import LANGUAGES, SECTIONS, AiConfig, GeneralConfig, PrivacyConfig, field_errors, timezones
from app.config.store import Config, Connector, get_config, get_config_store
from app.data.store import get_dataset
from app.flows.catalog import MODELS, PROVIDERS
from app.flows.store import now

router = APIRouter(prefix="/api/config", tags=["config"])

Model = TypeVar("Model", bound=BaseModel)

VIEW = require_permission("config:view")
EDIT = require_permission("config:edit")


def _parse(model: type[Model], payload: Any) -> Model:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=field_errors(exc)) from None


@cache
def _conversations_by_channel() -> Counter:
    return Counter(c.channel for c in get_dataset())


def _connector(connector: Connector) -> dict:
    return {"id": connector.id, "name": connector.name, "channel": connector.channel, "status": connector.status,
            "last_sync": connector.last_sync.isoformat(),
            "conversations": _conversations_by_channel()[connector.channel]}


def _options() -> dict:
    return {
        "languages": [{"value": v, "label": label} for v, label in LANGUAGES.items()],
        "timezones": timezones(),
        "providers": [{"value": v, "label": p["label"], "models": [{"value": m, "label": MODELS[m]} for m in p["models"]]}
                      for v, p in PROVIDERS.items()],
        "sections": [{"value": v, "label": label} for v, label in SECTIONS.items()],
    }


def config_body(config: Config) -> dict:
    return {
        "version": config.version,
        "general": config.general.model_dump(),
        "privacy": config.privacy.model_dump(),
        "ai": {**config.ai.model_dump(), "simulated": True},
        "options": _options(),
    }


@router.get("/public")
def public_config() -> dict:
    """Solo el nombre de la plataforma, para la pantalla de login."""
    return {"platform_name": get_config().general.platform_name}


@router.get("", dependencies=[Depends(VIEW)])
def read_config() -> dict:
    return config_body(get_config())


@router.put("/general")
def update_general(payload: Any = Body(...), user: User = Depends(EDIT)) -> dict:
    general = _parse(GeneralConfig, payload)
    config = get_config_store().apply_change(user, "general", SECTIONS["general"], lambda c: (
        c.general.model_dump(), general.model_dump(), {"general": general}))
    return config_body(config)


@router.put("/privacy")
def update_privacy(payload: Any = Body(...), user: User = Depends(EDIT)) -> dict:
    privacy = _parse(PrivacyConfig, payload)
    config = get_config_store().apply_change(user, "privacidad", "Enmascarado de PII", lambda c: (
        c.privacy.model_dump(), privacy.model_dump(), {"privacy": privacy}))
    return config_body(config)


@router.put("/ai")
def update_ai(payload: Any = Body(...), user: User = Depends(EDIT)) -> dict:
    ai = _parse(AiConfig, payload)
    config = get_config_store().apply_change(user, "modelos", "Modelo por defecto", lambda c: (
        c.ai.model_dump(), ai.model_dump(), {"ai": ai}))
    return config_body(config)


@router.get("/connectors", dependencies=[Depends(VIEW)])
def list_connectors() -> dict:
    return {"items": [_connector(c) for c in get_config().connectors.values()]}


@router.post("/connectors/{connector_id}/sync")
def sync_connector(connector_id: str, user: User = Depends(EDIT)) -> dict:
    """Simula una sincronización: actualiza la fecha y no cambia el dataset."""
    connector_id = ids.normalize(connector_id)
    if connector_id not in get_config().connectors:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conector no encontrado")
    synced_at = now()

    def change(c: Config):
        old = c.connectors[connector_id]
        new = replace(old, last_sync=synced_at)
        return ({"last_sync": old.last_sync.isoformat()}, {"last_sync": new.last_sync.isoformat()},
                {"connectors": {**c.connectors, connector_id: new}})

    config = get_config_store().apply_change(user, "fuentes", get_config().connectors[connector_id].name, change)
    return _connector(config.connectors[connector_id])


@router.get("/audit", dependencies=[Depends(VIEW)])
def list_audit(section: Literal[*SECTIONS] | None = Query(None)) -> dict:  # type: ignore[valid-type]
    return {"items": [e.to_dict() for e in get_config_store().audit(section)]}

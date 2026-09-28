"""API de configuración (FE005). Lecturas con `config:view`; escrituras con `config:edit`; el nombre, público."""
from collections import Counter
from dataclasses import dataclass, replace
from functools import cache
from typing import Any, Callable, Literal, TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ValidationError

from app import ids
from app.auth import User, require_permission
from app.config.checks import Check, CheckIn
from app.config.model import LANGUAGES, SECTIONS, AiConfig, GeneralConfig, PrivacyConfig, field_errors, timezones
from app.config.store import Config, Connector, get_config, get_config_store
from app.config.taxonomy import (MainTopicIn, SecondaryTopicIn, Topic, main_topic_usage,
                                 secondary_topic_usage)
from app.text import normalize_text
from app.data.store import get_dataset
from app.flows.catalog import MODELS, PROVIDERS
from app.clock import now

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


# --- Taxonomía ---

@dataclass(frozen=True)
class TopicKind:
    field: str  # atributo de `Config`
    prefix: str
    model: type[MainTopicIn]
    label: str
    usage: Callable[[], Counter]
    unique_names: bool


TOPIC_KINDS = {
    "main-topics": TopicKind("main_topics", ids.TOPIC, MainTopicIn, "Main topic", main_topic_usage, True),
    "secondary-topics": TopicKind("secondary_topics", ids.SECONDARY_TOPIC, SecondaryTopicIn, "Tema secundario",
                                  secondary_topic_usage, False),
}
TopicKindParam = Literal["main-topics", "secondary-topics"]


def _topic_body(kind: TopicKind, topic: Topic) -> dict:
    return {"id": topic.id, **topic.audit_value(), "conversations": kind.usage()[topic.code]}


def _unprocessable(field: str, message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                         detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}])


def _find_topic(kind: TopicKind, topic_id: str) -> Topic:
    topic_id = ids.normalize(topic_id)
    topic = next((t for t in getattr(get_config(), kind.field).values() if t.id == topic_id), None)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{kind.label} no encontrado")
    return topic


def _check_unique_name(kind: TopicKind, topics: dict[str, Topic], name: str, code: str) -> None:
    if kind.unique_names and any(normalize_text(t.name) == normalize_text(name) and t.code != code
                                 for t in topics.values()):
        raise _unprocessable("name", "Ya existe otro con ese nombre")


def _element(kind: TopicKind, topic: Topic) -> str:
    return f"{kind.label} «{topic.name}»"


@router.get("/taxonomy", dependencies=[Depends(VIEW)])
def read_taxonomy() -> dict:
    config = get_config()
    return {name.replace("-", "_"): [_topic_body(kind, t) for t in getattr(config, kind.field).values()]
            for name, kind in TOPIC_KINDS.items()}


@router.post("/taxonomy/{kind_name}", status_code=status.HTTP_201_CREATED)
def create_topic(kind_name: TopicKindParam, payload: Any = Body(...), user: User = Depends(EDIT)) -> dict:
    kind = TOPIC_KINDS[kind_name]
    topic = Topic.from_input(kind.prefix, _parse(kind.model, payload))

    def change(c: Config):
        topics = getattr(c, kind.field)
        if topic.code in topics:
            raise _unprocessable("code", "Ya existe un elemento con ese código")
        _check_unique_name(kind, topics, topic.name, topic.code)
        return None, topic.audit_value(), {kind.field: {**topics, topic.code: topic}}

    get_config_store().apply_change(user, "taxonomia", _element(kind, topic), change)
    return _topic_body(kind, topic)


@router.put("/taxonomy/{kind_name}/{topic_id}")
def update_topic(kind_name: TopicKindParam, topic_id: str, payload: Any = Body(...),
                 user: User = Depends(EDIT)) -> dict:
    kind = TOPIC_KINDS[kind_name]
    current = _find_topic(kind, topic_id)
    data = _parse(kind.model, payload)
    if data.code != current.code:
        raise _unprocessable("code", "El código no se puede cambiar")
    topic = Topic.from_input(kind.prefix, data)

    def change(c: Config):
        topics = getattr(c, kind.field)
        _check_unique_name(kind, topics, topic.name, topic.code)
        return topics[topic.code].audit_value(), topic.audit_value(), {kind.field: {**topics, topic.code: topic}}

    get_config_store().apply_change(user, "taxonomia", _element(kind, current), change)
    return _topic_body(kind, topic)


@router.delete("/taxonomy/{kind_name}/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(kind_name: TopicKindParam, topic_id: str, user: User = Depends(EDIT)) -> Response:
    kind = TOPIC_KINDS[kind_name]
    topic = _find_topic(kind, topic_id)
    if kind.usage()[topic.code]:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail="Está asignado a conversaciones: no se puede borrar, solo desactivar")

    def change(c: Config):
        topics = dict(getattr(c, kind.field))
        removed = topics.pop(topic.code)
        return removed.audit_value(), None, {kind.field: topics}

    get_config_store().apply_change(user, "taxonomia", _element(kind, topic), change)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Cumplimiento ---

def _find_check(check_id: str) -> Check:
    check = next((c for c in get_config().checks.values() if c.id == ids.normalize(check_id)), None)
    if check is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Check no encontrado")
    return check


def _check_unique_check_name(checks: dict[str, Check], name: str, code: str) -> None:
    if any(normalize_text(c.name) == normalize_text(name) and c.code != code for c in checks.values()):
        raise _unprocessable("name", "Ya existe otro check con ese nombre")


def _check_element(check: Check) -> str:
    return f"Check «{check.name}»"


@router.get("/compliance-checks", dependencies=[Depends(VIEW)])
def list_checks() -> dict:
    return {"items": [c.to_dict() for c in get_config().checks.values()]}


@router.post("/compliance-checks", status_code=status.HTTP_201_CREATED)
def create_check(payload: Any = Body(...), user: User = Depends(EDIT)) -> dict:
    check = Check.from_input(_parse(CheckIn, payload), builtin=False)

    def change(c: Config):
        if check.code in c.checks:
            raise _unprocessable("code", "Ya existe un check con ese código")
        _check_unique_check_name(c.checks, check.name, check.code)
        return None, check.audit_value(), {"checks": {**c.checks, check.code: check}}

    get_config_store().apply_change(user, "cumplimiento", _check_element(check), change)
    return check.to_dict()


@router.put("/compliance-checks/{check_id}")
def update_check(check_id: str, payload: Any = Body(...), user: User = Depends(EDIT)) -> dict:
    current = _find_check(check_id)
    data = _parse(CheckIn, payload)
    if data.code != current.code:
        raise _unprocessable("code", "El código no se puede cambiar")
    check = Check.from_input(data, builtin=current.builtin)

    def change(c: Config):
        _check_unique_check_name(c.checks, check.name, check.code)
        return c.checks[check.code].audit_value(), check.audit_value(), {"checks": {**c.checks, check.code: check}}

    get_config_store().apply_change(user, "cumplimiento", _check_element(current), change)
    return check.to_dict()


@router.delete("/compliance-checks/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_check(check_id: str, user: User = Depends(EDIT)) -> Response:
    check = _find_check(check_id)
    if check.builtin:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail="Es un check del análisis: no se puede borrar, solo desactivar")

    def change(c: Config):
        checks = dict(c.checks)
        removed = checks.pop(check.code)
        return removed.audit_value(), None, {"checks": checks}

    get_config_store().apply_change(user, "cumplimiento", _check_element(check), change)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

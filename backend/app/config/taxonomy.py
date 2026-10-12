"""Taxonomía editable (FE005, criterio 7): main topics (`1TP`) y temas secundarios (`1TS`).

El **código** es la clave en conversaciones, filtros, URLs, consultas guardadas y flujos, así que no cambia nunca; el
identificador se deriva de él (v5). Un tema desactivado deja de ofrecerse, pero sigue siendo un valor válido: sus
conversaciones, KPIs y drill-down no cambian.
"""
from collections import Counter
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, StringConstraints

from app import ids
from app.config.model import Section
from app.data.catalog import MAIN_TOPIC_DESCRIPTIONS, MAIN_TOPICS, SECONDARY_TOPICS
from app.data.repository import cached_by_version
from app.data.store import get_dataset

MAX_NAME = 80
MAX_DESCRIPTION = 300
MAX_KEYWORDS = 30
MAX_KEYWORD = 60

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_DESCRIPTION)]
Keyword = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_KEYWORD)]


class MainTopicIn(Section):
    code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    name: Name
    description: Description = ""
    keywords: list[Keyword] = Field(default_factory=list, max_length=MAX_KEYWORDS)
    active: bool = True


class SecondaryTopicIn(MainTopicIn):
    # Los temas secundarios del dataset se guardan como texto en minúsculas y con espacios («compras online»).
    code: Annotated[str, StringConstraints(pattern=r"^[a-záéíóúüñ0-9][a-záéíóúüñ0-9 _-]{0,59}$")]


@dataclass(frozen=True)
class Topic:
    id: str
    code: str
    name: str
    description: str
    keywords: tuple[str, ...]
    active: bool

    @classmethod
    def from_input(cls, prefix: str, data: MainTopicIn) -> "Topic":
        return cls(ids.stable_id(prefix, data.code), data.code, data.name, data.description, tuple(data.keywords),
                   data.active)

    def audit_value(self) -> dict:
        return {"code": self.code, "name": self.name, "description": self.description,
                "keywords": list(self.keywords), "active": self.active}


def initial_main_topics() -> dict[str, Topic]:
    return {code: Topic(ids.stable_id(ids.TOPIC, code), code, t.name, MAIN_TOPIC_DESCRIPTIONS[code],
                        tuple(t.keywords), True)
            for code, t in MAIN_TOPICS.items()}


def initial_secondary_topics() -> dict[str, Topic]:
    return {code: Topic(ids.stable_id(ids.SECONDARY_TOPIC, code), code, code, "", (), True)
            for code in SECONDARY_TOPICS}


@cached_by_version
def main_topic_usage() -> Counter:
    return Counter(c.analysis.main_topic for c in get_dataset())


@cached_by_version
def secondary_topic_usage() -> Counter:
    return Counter(s for c in get_dataset() for s in set(c.analysis.secondary_topics))

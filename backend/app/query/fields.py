from dataclasses import dataclass, field
from typing import Any, Callable

from app import ids
from app.config.store import Config, get_config
from app.config.compliance import check_result
from app.data.catalog import AGENT_IDS, QUEUE_IDS
from app.data.store import followup_index
from app.models import Conversation

OPERATOR_LABELS = {
    "is": "es", "is_not": "no es", "in": "es alguno de", "not_in": "no es ninguno de",
    "eq": "=", "ne": "≠", "gt": ">", "gte": "≥", "lt": "<", "lte": "≤", "between": "entre",
    "passes": "cumple", "fails": "no cumple", "not_applicable": "no aplica",
    "contains": "contiene", "not_contains": "no contiene",
}
OPERATORS_BY_TYPE = {
    "categorical": ["is", "is_not", "in", "not_in"],
    "numeric": ["eq", "ne", "gt", "gte", "lt", "lte", "between"],
    "check": ["passes", "fails", "not_applicable"],
    "text": ["contains", "not_contains"],
    "boolean": ["is"],
}
SPEAKERS = ["cliente", "agente", "bot"]


@dataclass(frozen=True)
class FieldDef:
    key: str
    label: str
    type: str
    extract: Callable[[Conversation], Any]
    values: list[tuple[str, str]] = field(default_factory=list)
    min: float | None = None
    max: float | None = None
    id_prefix: str | None = None
    multi_valued: bool = False
    speakers: bool = False
    # Valores válidos que ya no se ofrecen (temas desactivados): se aceptan en consultas, pero no salen en el esquema.
    hidden: frozenset[str] = frozenset()
    # Un campo no ofrecido (check desactivado) sigue siendo válido en consultas guardadas, pero no sale en el esquema.
    offered: bool = True

    @property
    def operators(self) -> list[str]:
        return OPERATORS_BY_TYPE[self.type]

    def schema(self) -> dict:
        data = {
            "key": self.key, "label": self.label, "type": self.type,
            "operators": [{"key": o, "label": OPERATOR_LABELS[o]} for o in self.operators],
        }
        if self.values:
            data["values"] = [{"value": v, "label": label} for v, label in self.values if v not in self.hidden]
        if self.min is not None:
            data["min"], data["max"] = self.min, self.max
        if self.speakers:
            data["speakers"] = SPEAKERS
        return data


def _topic_field(key: str, label: str, topics, extract, multi_valued: bool = False) -> FieldDef:
    return FieldDef(key, label, "categorical", extract, [(t.code, t.name) for t in topics.values()],
                    multi_valued=multi_valued, hidden=frozenset(t.code for t in topics.values() if not t.active))


def build_fields(config: Config) -> dict[str, "FieldDef"]:
    return {f.key: f for f in _field_list(config)}


def _field_list(config: Config) -> list[FieldDef]:
    return [
        FieldDef("channel", "Canal", "categorical", lambda c: c.channel, [("voz", "Voz"), ("chat", "Chat")]),
        FieldDef("queue", "Cola", "categorical", lambda c: c.queue_id,
                 [(qid, name) for name, qid in QUEUE_IDS.items()], id_prefix=ids.QUEUE),
        FieldDef("agent", "Agente", "categorical", lambda c: c.agent_id,
                 [(aid, name) for name, aid in AGENT_IDS.items()], id_prefix=ids.AGENT),
        _topic_field("main_topic", "Main topic", config.main_topics, lambda c: c.analysis.main_topic),
        _topic_field("secondary_topic", "Tema secundario", config.secondary_topics,
                     lambda c: c.analysis.secondary_topics, multi_valued=True),
        FieldDef("resolution", "Resolución", "categorical", lambda c: c.analysis.resolution,
                 [("resuelta", "Resuelta"), ("no_resuelta", "No resuelta"), ("escalada", "Escalada")]),
        FieldDef("churn_risk", "Riesgo de abandono", "categorical", lambda c: c.analysis.churn_risk,
                 [("bajo", "Bajo"), ("medio", "Medio"), ("alto", "Alto")]),
        FieldDef("sentiment", "Sentimiento", "numeric", lambda c: c.analysis.sentiment, min=-1, max=1),
        FieldDef("csat", "CSAT predicho", "numeric", lambda c: c.analysis.csat, min=1, max=5),
        FieldDef("effort", "Esfuerzo del cliente", "numeric", lambda c: c.analysis.effort, min=1, max=5),
        FieldDef("duration", "Duración (s)", "numeric", lambda c: c.duration_s, min=0, max=86400),
        FieldDef("turns", "Nº de turnos", "numeric", lambda c: len(c.turns), min=0, max=1000),
        *[
            FieldDef(f"check:{check.code}", check.name, "check", lambda c, code=check.code: check_result(c, code),
                     offered=check.active)
            for check in config.checks.values()
        ],
        FieldDef("summary", "Summary", "text", lambda c: c.analysis.summary),
        FieldDef("transcript", "Transcripción", "text", lambda c: c.turns, speakers=True),
        FieldDef("repeat_contact", "Recontacto en 7 días", "boolean", lambda c: followup_index()[c.id]),
    ]


_cache: tuple[Config, dict[str, FieldDef]] | None = None


def get_fields() -> dict[str, FieldDef]:
    """Campos del explorador según la configuración vigente (FE005).

    Se reconstruyen solo cuando cambia la instantánea de configuración, que es inmutable: se compara por identidad y no
    por versión, porque la versión vuelve a 0 al reiniciar el store.
    """
    global _cache
    config = get_config()
    if _cache is None or _cache[0] is not config:
        _cache = (config, build_fields(config))
    return _cache[1]

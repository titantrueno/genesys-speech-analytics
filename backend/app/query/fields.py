import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable

from app import ids
from app.data.catalog import AGENT_IDS, COMPLIANCE_CHECKS, MAIN_TOPICS, QUEUE_IDS, SECONDARY_TOPICS
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


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


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

    @property
    def operators(self) -> list[str]:
        return OPERATORS_BY_TYPE[self.type]

    def schema(self) -> dict:
        data = {
            "key": self.key, "label": self.label, "type": self.type,
            "operators": [{"key": o, "label": OPERATOR_LABELS[o]} for o in self.operators],
        }
        if self.values:
            data["values"] = [{"value": v, "label": label} for v, label in self.values]
        if self.min is not None:
            data["min"], data["max"] = self.min, self.max
        if self.speakers:
            data["speakers"] = SPEAKERS
        return data


def _labels(codes, labels=None):
    return [(c, (labels or {}).get(c, c)) for c in codes]


_FIELD_LIST = [
    FieldDef("channel", "Canal", "categorical", lambda c: c.channel, [("voz", "Voz"), ("chat", "Chat")]),
    FieldDef("queue", "Cola", "categorical", lambda c: c.queue_id,
             [(qid, name) for name, qid in QUEUE_IDS.items()], id_prefix=ids.QUEUE),
    FieldDef("agent", "Agente", "categorical", lambda c: c.agent_id,
             [(aid, name) for name, aid in AGENT_IDS.items()], id_prefix=ids.AGENT),
    FieldDef("main_topic", "Main topic", "categorical", lambda c: c.analysis.main_topic,
             [(code, t.name) for code, t in MAIN_TOPICS.items()]),
    FieldDef("secondary_topic", "Tema secundario", "categorical", lambda c: c.analysis.secondary_topics,
             _labels(SECONDARY_TOPICS), multi_valued=True),
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
        FieldDef(f"check:{code}", label, "check", lambda c, code=code: c.analysis.compliance.get(code))
        for code, label in COMPLIANCE_CHECKS.items()
    ],
    FieldDef("summary", "Summary", "text", lambda c: c.analysis.summary),
    FieldDef("transcript", "Transcripción", "text", lambda c: c.turns, speakers=True),
    FieldDef("repeat_contact", "Recontacto en 7 días", "boolean", lambda c: followup_index()[c.id]),
]

FIELDS: dict[str, FieldDef] = {f.key: f for f in _FIELD_LIST}

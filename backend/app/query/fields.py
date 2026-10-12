from dataclasses import dataclass, field, replace
from typing import Any, Callable

from app import ids
from app.config.store import Config, get_config
from app.config.compliance import check_result
from app.data.repository import REAL, ConversationRepository, active_repository
from app.data.store import followup_index
from app.models import Conversation

OPERATOR_LABELS = {
    "is": "es", "is_not": "no es", "in": "es alguno de", "not_in": "no es ninguno de",
    "eq": "=", "ne": "≠", "gt": ">", "gte": "≥", "lt": "<", "lte": "≤", "between": "entre",
    "passes": "cumple", "fails": "no cumple", "not_applicable": "no aplica",
    "contains": "contiene", "not_contains": "no contiene",
    "is_empty": "está vacío", "is_not_empty": "no está vacío",
}
# Con conversaciones reales todos los campos admiten estos operadores: un campo sin analizar está vacío (FE012).
EMPTY_OPERATORS = ("is_empty", "is_not_empty")
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
    # Campo que depende del análisis de la plataforma: una conversación sin analizar no cumple ninguna condición salvo
    # «está vacío» (FE012, criterio 10).
    analysis: bool = False
    # Operadores añadidos a los del tipo (solo con el origen `real`).
    extra_operators: tuple[str, ...] = ()
    # Campos de texto simple (ANI, DNIS, `externalTag`): el texto de la conversación en lugar de resumen o turnos.
    text_of: Callable[[Conversation], str | None] | None = None

    @property
    def operators(self) -> list[str]:
        return [*OPERATORS_BY_TYPE[self.type], *self.extra_operators]

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


def build_fields(config: Config, repository: ConversationRepository | None = None) -> dict[str, "FieldDef"]:
    repository = repository or active_repository()
    fields = [replace(f, analysis=f.key in ANALYSIS_FIELDS or f.type == "check")
              for f in _field_list(config, repository)]
    if repository.origin == REAL:
        fields += _genesys_fields(repository)
        fields = [replace(f, extra_operators=(*f.extra_operators, *EMPTY_OPERATORS)) for f in fields]
    return {f.key: f for f in fields}


def _field_list(config: Config, repository: ConversationRepository) -> list[FieldDef]:
    return [
        FieldDef("channel", "Canal", "categorical", lambda c: c.channel, [("voz", "Voz"), ("chat", "Chat")]),
        FieldDef("queue", "Cola", "categorical", lambda c: c.queue_id, list(repository.queues()),
                 id_prefix=ids.QUEUE),
        FieldDef("agent", "Agente", "categorical", lambda c: c.agent_id,
                 [(aid, name) for aid, name, _, _ in repository.agents()], id_prefix=ids.AGENT),
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
        FieldDef("repeat_contact", "Recontacto en 7 días", "boolean",
                 lambda c: None if c.analysis.pending else followup_index()[c.id]),
    ]


# Quién terminó la conversación, según el `disconnectType` del último tramo del cliente.
DISCONNECT_LABELS = {"client": "Cliente", "peer": "Agente o bot", "endpoint": "Error del extremo", "system": "Sistema",
                     "error": "Error", "transfer": "Transferencia", "timeout": "Tiempo agotado"}
TIME_FIELDS = [("handle_s", "Gestión (s)"), ("queue_wait_s", "Espera en cola (s)"), ("talk_s", "Conversación (s)"),
               ("hold_s", "En espera (s)"), ("acw_s", "Trabajo posterior (s)"), ("bot_time_s", "Tiempo con el bot (s)")]
# Campos que dependen del análisis de la plataforma (los de `_field_list`); el resto de campos son datos de origen.
ANALYSIS_FIELDS = frozenset({"main_topic", "secondary_topic", "resolution", "churn_risk", "csat", "effort", "summary",
                             "repeat_contact"})


def _metric(key: str):
    return lambda c: c.genesys.metrics.get(key) if c.genesys else None


def _flag(attribute: str):
    return lambda c: getattr(c.genesys, attribute) if c.genesys else None


def _entry_flows(c: Conversation) -> list[str]:
    segments = c.genesys.segments if c.genesys else []
    return sorted({s["flow"]["name"] for s in segments if s["kind"] in ("flujo_entrada", "ivr") and s["flow"]})


def _wrapups(c: Conversation) -> list[str]:
    segments = c.genesys.segments if c.genesys else []
    return sorted({s["wrapup"]["name"] for s in segments if s["wrapup"]})


def _topics(c: Conversation) -> list[str]:
    return sorted({t["name"] for t in c.genesys.topics if t["name"]}) if c.genesys else []


def _distinct(conversations, extract) -> list[tuple[str, str]]:
    return [(v, v) for v in sorted({v for c in conversations for v in extract(c)})]


def _genesys_fields(repository: ConversationRepository) -> list[FieldDef]:
    """Campos con la analítica de Genesys (FE012, criterio 7); solo existen con el origen `real`."""
    convs = repository.conversations()
    disconnect = {c.genesys.disconnect_type for c in convs if c.genesys and c.genesys.disconnect_type}

    def text(key: str, label: str, attribute: str) -> FieldDef:
        return FieldDef(key, label, "text", lambda c: None, text_of=lambda c: getattr(c.genesys, attribute, None))

    return [
        text("gc_ani", "ANI (teléfono de origen)", "ani"),
        text("gc_dnis", "DNIS (teléfono de destino)", "dnis"),
        text("gc_external_tag", "externalTag", "external_tag"),
        FieldDef("gc_flow", "Flujo de IVR o de entrada", "categorical", _entry_flows, _distinct(convs, _entry_flows),
                 multi_valued=True),
        FieldDef("gc_wrapup", "Wrap-up", "categorical", _wrapups, _distinct(convs, _wrapups), multi_valued=True),
        FieldDef("gc_disconnect_by", "Quién terminó", "categorical",
                 lambda c: c.genesys.disconnect_type if c.genesys else None,
                 [(d, DISCONNECT_LABELS.get(d, d)) for d in sorted(disconnect)]),
        FieldDef("gc_contained", "Contenida en el bot", "boolean", _flag("contained_in_bot")),
        FieldDef("gc_derived", "Derivada a agente", "boolean", _flag("derived_to_agent")),
        FieldDef("gc_abandoned", "Abandono en cola", "boolean", _flag("abandoned_in_queue")),
        FieldDef("gc_reconnected", "Reconexión", "boolean", _flag("reconnected")),
        FieldDef("gc_undelivered", "Mensajes no entregados", "numeric", _flag("undelivered_messages"), min=0, max=1000),
        FieldDef("gc_transcript_quality", "Calidad de la transcripción", "categorical", _flag("transcript_quality"),
                 [("completa", "Completa"), ("parcial", "Parcial"), ("sin_transcripcion", "Sin transcripción")]),
        FieldDef("gc_topic", "Tema de Genesys", "categorical", _topics, _distinct(convs, _topics), multi_valued=True),
        FieldDef("gc_sentiment", "Sentimiento de Genesys", "numeric", _flag("customer_sentiment"), min=-1, max=1),
        FieldDef("gc_silence_pct", "% de silencio", "numeric",
                 lambda c: (c.genesys.metrics.get("sta_time_pct") or {}).get("silence") if c.genesys else None,
                 min=0, max=100),
        *[FieldDef(f"gc_{key}", label, "numeric", _metric(key), min=0, max=86400) for key, label in TIME_FIELDS],
    ]


_cache: tuple[tuple, dict[str, FieldDef]] | None = None


def get_fields() -> dict[str, FieldDef]:
    """Campos del explorador según la configuración vigente (FE005) y el origen de datos (FE012).

    Se reconstruyen solo cuando cambia la instantánea de configuración, que es inmutable (se compara por identidad y no
    por versión, porque la versión vuelve a 0 al reiniciar el store), el origen o los datos del origen real.
    """
    global _cache
    config, repository = get_config(), active_repository()
    key = (config, repository.origin, repository.version())
    if _cache is None or _cache[0][0] is not config or _cache[0][1:] != key[1:]:
        _cache = (key, build_fields(config, repository))
    return _cache[1]

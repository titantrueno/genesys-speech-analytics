from dataclasses import dataclass
from statistics import mean
from typing import Callable

from app.config.compliance import active_checks, check_result, is_compliant
from app.models import Conversation


@dataclass(frozen=True)
class KpiDef:
    code: str
    label: str
    unit: str
    higher_is_better: bool


KPI_DEFS = [
    KpiDef("volume", "Volumen", "conversaciones", True),
    KpiDef("aht_s", "Duración media (AHT)", "s", False),
    KpiDef("sentiment_avg", "Sentimiento medio", "índice", True),
    KpiDef("negative_pct", "Conversaciones negativas", "%", False),
    KpiDef("resolution_rate", "Tasa de resolución", "%", True),
    KpiDef("escalation_rate", "Tasa de escalado", "%", False),
    KpiDef("fcr_rate", "Resolución en primer contacto (FCR)", "%", True),
    KpiDef("csat_avg", "CSAT predicho", "1-5", True),
    KpiDef("effort_avg", "Esfuerzo del cliente", "1-5", False),
    KpiDef("compliance_rate", "Cumplimiento", "%", True),
    KpiDef("churn_high_pct", "Riesgo de abandono alto", "%", False),
    KpiDef("first_response_s", "Primera respuesta (chat)", "s", False),
    KpiDef("avg_turns", "Turnos medios", "turnos", False),
]
KPI_CODES = [k.code for k in KPI_DEFS]
# KPIs que dependen del análisis de la plataforma: con conversaciones reales sin analizar quedan «pendientes» (FE012).
ANALYSIS_KPIS = frozenset({"resolution_rate", "escalation_rate", "fcr_rate", "csat_avg", "effort_avg",
                           "compliance_rate", "churn_high_pct"})
NEGATIVE_THRESHOLD = -0.3


def _avg(values) -> float | None:
    values = list(values)
    return mean(values) if values else None


def _pct(convs: list[Conversation], predicate: Callable[[Conversation], bool]) -> float | None:
    return 100 * sum(1 for c in convs if predicate(c)) / len(convs) if convs else None


def round_value(value):
    return round(value, 2) + 0.0 if isinstance(value, float) else value


def _first_agent_offset(conv: Conversation) -> int | None:
    return next((t.offset_s for t in conv.turns if t.speaker == "agente"), None)


def handle_time(conv: Conversation) -> float | None:
    """Gestión de la conversación: la duración en el dataset sintético; la gestión total (`handle_s`) de Genesys en las
    reales, solo si las atendió un agente."""
    if conv.genesys is None:
        return conv.duration_s
    return conv.genesys.metrics.get("handle_s") if conv.genesys.derived_to_agent else None


def pending_analysis(convs: list[Conversation]) -> bool:
    return any(c.analysis.pending for c in convs)


def kpi_bases(convs: list[Conversation]) -> dict[str, int | None]:
    """Conversaciones sobre las que se calculan los KPIs que pueden usar solo una parte de ellas."""
    return {
        "aht_s": sum(1 for c in convs if handle_time(c) is not None),
        "sentiment_avg": sum(1 for c in convs if c.analysis.sentiment is not None),
        "negative_pct": sum(1 for c in convs if c.analysis.sentiment is not None),
        "first_response_s": sum(1 for c in convs if c.channel == "chat" and _first_agent_offset(c) is not None),
    }


def compute_kpis(convs: list[Conversation], followups: dict[str, bool], rounded: bool = True) -> dict:
    raw = _raw_kpis(convs, followups)
    return {code: round_value(value) for code, value in raw.items()} if rounded else raw


def _raw_kpis(convs: list[Conversation], followups: dict[str, bool]) -> dict[str, float | int | None]:
    chats = [c for c in convs if c.channel == "chat"]
    # Lo que depende del análisis se calcula solo con las conversaciones analizadas (FE012): sin ninguna, es `None`.
    analysed = [c for c in convs if not c.analysis.pending]
    with_sentiment = [c for c in convs if c.analysis.sentiment is not None]
    return {
        "volume": len(convs),
        "aht_s": _avg(t for t in (handle_time(c) for c in convs) if t is not None),
        "sentiment_avg": _avg(c.analysis.sentiment for c in with_sentiment),
        "negative_pct": _pct(with_sentiment, lambda c: c.analysis.sentiment < NEGATIVE_THRESHOLD),
        "resolution_rate": _pct(analysed, lambda c: c.analysis.resolution == "resuelta"),
        "escalation_rate": _pct(analysed, lambda c: c.analysis.resolution == "escalada"),
        "fcr_rate": _pct(analysed, lambda c: not followups[c.id]),
        "csat_avg": _avg(c.analysis.csat for c in analysed if c.analysis.csat is not None),
        "effort_avg": _avg(c.analysis.effort for c in analysed if c.analysis.effort is not None),
        "compliance_rate": _pct(analysed, is_compliant),
        "churn_high_pct": _pct(analysed, lambda c: c.analysis.churn_risk == "alto"),
        "first_response_s": _avg(t for t in (_first_agent_offset(c) for c in chats) if t is not None),
        "avg_turns": _avg(len(c.turns) for c in convs),
    }


def compute_kpi(code: str, convs: list[Conversation], followups: dict[str, bool]):
    return compute_kpis(convs, followups)[code]


def compliance_by_check(convs: list[Conversation]) -> list[dict]:
    result = []
    for check in active_checks():
        values = {c.id: check_result(c, check.code) for c in convs}
        applicable = [c for c in convs if values[c.id] is not None]
        result.append({"code": check.code, "label": check.name,
                       "value": round_value(_pct(applicable, lambda c: values[c.id])),
                       "applicable": len(applicable)})
    return result


def delta(current, previous) -> float | None:
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


def delta_pct(current, previous, unit: str = "") -> float | None:
    """Variación relativa; no se calcula para índices que cruzan el cero, donde solo tiene sentido `delta`."""
    if current is None or not previous or unit == "índice":
        return None
    return round(100 * (current - previous) / abs(previous), 2)

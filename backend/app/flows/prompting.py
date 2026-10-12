"""Ejecución de prompts (FE004, criterio 5).

`PromptRunner` es el punto de extensión para un LLM real (ADR-006). La implementación actual, `MockPromptRunner`,
no llama a ningún modelo: deriva un resultado determinista del análisis de cada conversación, con la forma que
pide el formato de salida.
"""
import hashlib
import json
import re
from typing import Any, Protocol

from app.config.store import topic_name
from app.flows.model import PromptConfig
from app.flows.rules import VARIABLE
from app.models import Conversation
from app.privacy.masking import masked
from app.text import normalize_text

NEGATIVE_BELOW, POSITIVE_ABOVE = -0.3, 0.3  # mismos umbrales que las etiquetas de sentimiento de la UI
RESOLUTION_LABELS = {"resuelta": "resuelta", "no_resuelta": "no resuelta", "escalada": "escalada"}


class PromptRunner(Protocol):
    def run(self, config: PromptConfig, conversation: Conversation, previous: Any | None) -> Any:
        """Resultado del prompt para una conversación; `previous` es el del prompt anterior en una cadena."""


def sentiment_class(value: float | None) -> str:
    if value is None:
        return "sin dato"
    if value < NEGATIVE_BELOW:
        return "negativo"
    return "positivo" if value > POSITIVE_ABOVE else "neutro"


def _topic_name(conv: Conversation) -> str:
    return topic_name(conv.analysis.main_topic) if conv.analysis.main_topic else ""


def _turn_line(turn) -> str:
    return f"{turn.speaker}: {turn.text}" + ("" if turn.delivered else " [no entregado]")


def _resolution(conv: Conversation) -> str:
    resolution = conv.analysis.resolution
    return RESOLUTION_LABELS[resolution] if resolution else "pendiente de análisis"


def _yes(value: bool) -> str:
    return "sí" if value else "no"


def genesys_metadata(conv: Conversation) -> str:
    """Analítica de Genesys de una conversación real, en una línea (variable `{{metadatos}}`, FE012)."""
    g = conv.genesys
    metrics = g.metrics
    parts = []
    if g.ani:
        parts.append(f"ANI: {g.ani}")
    if g.dnis:
        parts.append(f"DNIS: {g.dnis}")
    if g.external_tag:
        parts.append(f"externalTag: {g.external_tag}")
    wrapups = sorted({s["wrapup"]["name"] for s in g.segments if s["wrapup"]})
    if wrapups:
        parts.append(f"Wrap-up: {', '.join(wrapups)}")
    parts.append("Contenida en el bot" if g.contained_in_bot else "Derivada a agente" if g.derived_to_agent
                 else "Sin agente ni contención en el bot")
    parts += [f"Reconexión: {_yes(g.reconnected)}", f"Abandono en cola: {_yes(g.abandoned_in_queue)}",
              f"Calidad de la transcripción: {g.transcript_quality}"]
    if g.disconnect_type:
        parts.append(f"Terminó: {g.disconnect_type}")
    if g.undelivered_messages:
        parts.append(f"Mensajes no entregados: {g.undelivered_messages}")
    for key, label in (("handle_s", "Gestión"), ("queue_wait_s", "Espera en cola"), ("talk_s", "Conversación"),
                       ("hold_s", "En espera"), ("acw_s", "Trabajo posterior")):
        if key in metrics:
            parts.append(f"{label}: {metrics[key]:.0f} s")
    silence = (metrics.get("sta_time_pct") or {}).get("silence")
    if silence is not None:
        parts.append(f"Silencio: {silence:.0f} %")
    if g.topics:
        parts.append(f"Temas de Genesys: {', '.join(dict.fromkeys(t['name'] for t in g.topics))}")
    return " · ".join(parts)


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def render_template(template: str, conversation: Conversation, previous: Any | None = None) -> str:
    conv = conversation
    # El prompt recibe siempre el texto enmascarado, esté o no activado el interruptor de Privacidad (FE012).
    visible = masked(conv)
    sentiment = "sin dato" if conv.analysis.sentiment is None else f"{conv.analysis.sentiment:+.2f}"
    metadata = (f"Canal: {conv.channel} · Cola: {conv.queue or 'sin cola'} · Fecha: {conv.started_at:%Y-%m-%d %H:%M} · "
                f"Duración: {conv.duration_s} s · Sentimiento: {sentiment} · Resolución: {_resolution(conv)}")
    if conv.genesys is not None:
        metadata += " · " + genesys_metadata(conv)
    values = {
        "transcripcion": "\n".join(_turn_line(t) for t in visible.turns),
        "summary": visible.analysis.summary,
        "main_topic": _topic_name(conv),
        "metadatos": metadata,
        "resultado_anterior": "" if previous is None else _as_text(previous),
    }
    return VARIABLE.sub(lambda m: values.get(m.group(1), m.group(0)), template)


def _unit(*parts: Any) -> float:
    """Número estable en [0, 1) a partir de las entradas (sin `hash()`, que cambia entre procesos)."""
    digest = hashlib.sha256("|".join(_as_text(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _words(text: str) -> str:
    return " " + " ".join(re.findall(r"\w+", normalize_text(text))) + " "


def _facts(conv: Conversation) -> list[tuple[int, str]]:
    """Hechos del análisis que puede nombrar una etiqueta, con su prioridad (el main topic primero)."""
    analysis = conv.analysis
    topic = [(5, _topic_name(conv)), (5, analysis.main_topic.replace("_", " "))] if analysis.main_topic else []
    sentiment = ([(4, sentiment_class(analysis.sentiment)), (4, f"sentimiento {sentiment_class(analysis.sentiment)}")]
                 if analysis.sentiment is not None else [])
    resolution = [(3, RESOLUTION_LABELS[analysis.resolution])] if analysis.resolution else []
    churn = ([(2, f"riesgo {analysis.churn_risk}"), (2, f"riesgo de abandono {analysis.churn_risk}")]
             if analysis.churn_risk else [])
    return [*topic, *sentiment, *resolution, *churn, *[(1, t) for t in analysis.secondary_topics],
            (1, conv.channel), *([(1, conv.queue)] if conv.queue else [])]


def choose_label(labels: list[str], conv: Conversation, key: float) -> str:
    """La etiqueta que nombra un hecho del análisis: primero la idéntica a un hecho, luego la que lo contiene."""
    facts = [(priority, _words(fact)) for priority, fact in _facts(conv)]
    best, best_score = None, None
    for position, label in enumerate(labels):
        words = _words(label)
        for priority, fact in facts:
            tier = 2 if words == fact else 1 if fact in words else 0
            score = (tier, priority, len(fact), -position)
            if tier and (best_score is None or score > best_score):
                best, best_score = label, score
    return best if best is not None else labels[int(key * len(labels))]


def _text(config: PromptConfig, conv: Conversation, previous: Any | None) -> str:
    analysis = conv.analysis
    if analysis.pending:  # sin summary ni main topic: se resume lo primero que dijo el cliente
        first = next((t.text for t in masked(conv).turns if t.speaker == "cliente"), "sin transcripción")
        text = f"{conv.channel.capitalize()}: {first.split('. ')[0].rstrip('.')[:160]}."
    else:
        first_sentence = analysis.summary.split(". ")[0].rstrip(".") + "."
        text = f"{_topic_name(conv)}: {first_sentence}"
    if config.model == "mock-preciso":
        text += f" Tono {sentiment_class(analysis.sentiment)}"
        text += f" ({analysis.sentiment:+.2f})" if analysis.sentiment is not None else ""
        text += f", conversación {_resolution(conv)}"
        text += f" y riesgo de abandono {analysis.churn_risk}." if analysis.churn_risk else "."
    if previous is not None:
        text = f"A partir de «{_as_text(previous)[:120]}»: {text}"
    return text


def _known_field(name: str, field_type: str, conv: Conversation) -> tuple[bool, Any]:
    analysis = conv.analysis
    known = {
        ("main_topic", "texto"): _topic_name(conv),
        ("sentimiento", "numero"): analysis.sentiment,
        ("sentimiento", "texto"): sentiment_class(analysis.sentiment),
        ("resolucion", "texto"): analysis.resolution,
        ("resolucion", "booleano"): analysis.resolution == "resuelta",
        ("csat", "numero"): analysis.csat,
        ("riesgo_abandono", "texto"): analysis.churn_risk,
        ("riesgo_abandono", "booleano"): analysis.churn_risk == "alto",
        ("canal", "texto"): conv.channel,
        ("cola", "texto"): conv.queue or "",
        ("resumen", "texto"): analysis.summary,
    }
    key = (normalize_text(name), field_type)
    return (key in known, known.get(key))


def _json(config: PromptConfig, conv: Conversation, previous: Any | None) -> dict:
    result = {}
    for field in config.output.fields or []:
        found, value = _known_field(field.name, field.type, conv)
        if not found:
            unit = _unit(conv.id, config.template, config.model, field.name, previous)
            value = {"texto": _topic_name(conv), "numero": round(unit * 10, 1), "booleano": unit >= 0.5}[field.type]
        result[field.name] = value
    return result


class MockPromptRunner:
    def run(self, config: PromptConfig, conversation: Conversation, previous: Any | None) -> Any:
        output = config.output.type
        if output == "etiqueta":
            key = _unit(conversation.id, config.template, config.model, config.temperature, previous)
            return choose_label(config.output.labels, conversation, key)
        if output == "json":
            return _json(config, conversation, previous)
        return _text(config, conversation, previous)

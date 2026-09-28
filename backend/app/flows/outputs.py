"""Outputs de un flujo (FE004, criterio 5): tabla por conversación, métrica por etiqueta e informe resumen."""
import json
from collections import Counter
from math import floor
from typing import Any

from app.config.store import topic_name
from app.flows.model import OutputConfig
from app.models import Conversation
from app.services.listing import list_item


def build_table(conversations: list[Conversation], results: dict[str, Any]) -> dict:
    return {"rows": [{"conversation": list_item(conv), "result": results[conv.id]} for conv in conversations]}


def percentages(counts: list[int]) -> list[float]:
    """Porcentajes con un decimal que suman exactamente 100 (restos mayores sobre las décimas)."""
    total = sum(counts)
    if total == 0:
        return [0.0] * len(counts)
    exact = [1000 * count / total for count in counts]
    tenths = [floor(value) for value in exact]
    order = sorted(range(len(counts)), key=lambda i: (tenths[i] - exact[i], i))
    for i in order[:1000 - sum(tenths)]:
        tenths[i] += 1
    return [t / 10 for t in tenths]


def build_metric(labels: list[str], conversations: list[Conversation], results: dict[str, Any], config: OutputConfig) -> dict:
    counts = Counter(results[conv.id] for conv in conversations)
    values = [counts[label] for label in labels]
    return {
        "aggregation": config.aggregation,
        "total": len(conversations),
        "items": [{"label": label, "count": count, "percent": percent}
                  for label, count, percent in zip(labels, values, percentages(values))],
    }


def _decimal(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def build_report(conversations: list[Conversation], results: dict[str, Any], config: OutputConfig) -> dict:
    size = len(conversations)
    days = sorted(conv.started_at.date() for conv in conversations)
    topics = Counter(topic_name(conv.analysis.main_topic) for conv in conversations)
    topic_counts = [count for _, count in topics.most_common()]
    shares = dict(zip([name for name, _ in topics.most_common()], percentages(topic_counts)))
    average = sum(conv.analysis.sentiment for conv in conversations) / size
    frequent = Counter(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False, sort_keys=True)
                       for r in results.values()).most_common(3)
    lines = [
        f"Informe «{config.destination.strip()}»",
        "",
        f"Muestra: {size} conversaciones, del {days[0]:%d/%m/%Y} al {days[-1]:%d/%m/%Y}.",
        "Reparto por main topic: " + "; ".join(
            f"{name} ({count}, {shares[name]:.1f} %)".replace(".", ",") for name, count in topics.most_common(5)) + ".",
        f"Sentimiento medio: {_decimal(average)}.",
        "Resultados más frecuentes: " + "; ".join(f"«{value[:160]}» ({count})" for value, count in frequent) + ".",
    ]
    return {"text": "\n".join(lines)}

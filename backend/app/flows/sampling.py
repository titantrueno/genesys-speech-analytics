"""Sampling real sobre el dataset mock (FE004, criterio 5): filtros de FE002 y método aleatorio, estratificado o primeros N."""
import copy
import random
from collections import defaultdict
from math import floor

from app.data.store import get_dataset
from app.flows.model import SamplingConfig
from app.models import Conversation
from app.query.engine import run_query
from app.query.model import parse_query

STRATUM_KEYS = {
    "canal": lambda c: c.channel,
    "cola": lambda c: c.queue_id,
    "main_topic": lambda c: c.analysis.main_topic,
}
ORDER_KEYS = {
    "fecha": lambda c: c.started_at,
    "duracion": lambda c: c.duration_s,
    "sentimiento": lambda c: c.analysis.sentiment,
    "csat": lambda c: c.analysis.csat,
}


def candidates(config: SamplingConfig) -> list[Conversation]:
    """Conversaciones que cumplen los filtros del nodo, en el orden del dataset."""
    return run_query(parse_query(copy.deepcopy(config.query)), get_dataset())


def _chronological(conversations: list[Conversation]) -> list[Conversation]:
    return sorted(conversations, key=lambda c: (c.started_at, c.id))


def proportional_quotas(sizes: dict[str, int], total: int, wanted: int) -> dict[str, int]:
    """Reparto proporcional por restos mayores: cada cuota queda a menos de 1 de su valor exacto."""
    exact = {group: wanted * size / total for group, size in sizes.items()}
    quotas = {group: floor(value) for group, value in exact.items()}
    remaining = wanted - sum(quotas.values())
    for group in sorted(exact, key=lambda g: (quotas[g] - exact[g], g))[:remaining]:
        quotas[group] += 1
    return quotas


def draw_sample(conversations: list[Conversation], config: SamplingConfig, seed: int) -> list[Conversation]:
    size = min(config.size, len(conversations))
    rng = random.Random(seed)
    if config.method == "aleatorio":
        return _chronological(rng.sample(conversations, size))
    if config.method == "estratificado":
        key = STRATUM_KEYS[config.stratify_by]
        groups: dict[str, list[Conversation]] = defaultdict(list)
        for conv in conversations:
            groups[key(conv)].append(conv)
        quotas = proportional_quotas({g: len(members) for g, members in groups.items()}, len(conversations), size)
        picked = [conv for group in sorted(groups) for conv in rng.sample(groups[group], quotas[group])]
        return _chronological(picked)
    key = ORDER_KEYS[config.order_by]
    descending = config.order == "desc"
    ordered = sorted(conversations, key=lambda c: c.id)
    ordered.sort(key=key, reverse=descending)
    return ordered[:size]

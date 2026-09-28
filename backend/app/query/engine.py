from functools import cache

from app.data.store import conversation_index
from app.models import Conversation
from app.privacy.masking import masked, masking_enabled
from app.query.fields import get_fields, normalize_text
from app.query.model import Condition, Group, Query


def _source(conversation_id: str, masked_text: bool) -> Conversation:
    conv = conversation_index()[conversation_id]
    return masked(conv) if masked_text else conv


# El texto se busca tal como se muestra: enmascarado si el interruptor de Privacidad está activado (FE005).
@cache
def _normalized_summary(conversation_id: str, masked_text: bool) -> str:
    return normalize_text(_source(conversation_id, masked_text).analysis.summary)


@cache
def _normalized_turns(conversation_id: str, masked_text: bool) -> tuple[tuple[str, str], ...]:
    return tuple((t.speaker, normalize_text(t.text)) for t in _source(conversation_id, masked_text).turns)


def _categorical(cond: Condition, value) -> bool:
    values = cond.value if isinstance(cond.value, list) else [cond.value]
    if isinstance(value, list):
        hit = any(v in value for v in values)
    else:
        hit = value in values
    return hit if cond.operator in ("is", "in") else not hit


def _numeric(cond: Condition, value: float) -> bool:
    target = cond.value
    return {
        "eq": lambda: value == target,
        "ne": lambda: value != target,
        "gt": lambda: value > target,
        "gte": lambda: value >= target,
        "lt": lambda: value < target,
        "lte": lambda: value <= target,
        "between": lambda: target[0] <= value <= target[1],
    }[cond.operator]()


def _check(cond: Condition, value: bool | None) -> bool:
    return {"passes": value is True, "fails": value is False, "not_applicable": value is None}[cond.operator]


def _text(cond: Condition, conv: Conversation) -> bool:
    needle = normalize_text(cond.value)
    masked_text = masking_enabled()
    if cond.field == "summary":
        found = needle in _normalized_summary(conv.id, masked_text)
    else:
        found = any(needle in text for speaker, text in _normalized_turns(conv.id, masked_text)
                    if cond.speaker is None or speaker == cond.speaker)
    return found if cond.operator == "contains" else not found


def _condition(cond: Condition, conv: Conversation) -> bool:
    fdef = get_fields()[cond.field]
    if fdef.type == "text":
        return _text(cond, conv)
    value = fdef.extract(conv)
    if fdef.type == "categorical":
        return _categorical(cond, value)
    if fdef.type == "numeric":
        return _numeric(cond, value)
    if fdef.type == "check":
        return _check(cond, value)
    return value == cond.value


def evaluate(node: Group | Condition, conv: Conversation) -> bool:
    if isinstance(node, Condition):
        return _condition(node, conv)
    if not node.conditions:
        return True
    results = (evaluate(child, conv) for child in node.conditions)
    return all(results) if node.op == "and" else any(results)


def run_query(query: Query, conversations: list[Conversation]) -> list[Conversation]:
    return [c for c in conversations
            if query.date_from <= c.started_at.date() <= query.date_to and evaluate(query.root, c)]

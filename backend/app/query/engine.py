from app.config.compliance import PENDING, check_state
from app.config.store import current_zone, local_day
from app.models import Conversation
from app.privacy.masking import masked, masking_enabled
from app.query.fields import EMPTY_OPERATORS, FieldDef, get_fields
from app.text import normalize_text
from app.query.model import Condition, Group, Query

# El texto se busca tal como se muestra: enmascarado si el interruptor de Privacidad está activado (FE005). Los cachés
# comprueban que la conversación sigue siendo el mismo objeto: una descarga nueva (FE012) la sustituye por otra.
_summaries: dict[tuple[str, bool], tuple[Conversation, str]] = {}
_turns: dict[tuple[str, bool], tuple[Conversation, tuple[tuple[str, str], ...]]] = {}


def _source(conv: Conversation, masked_text: bool) -> Conversation:
    return masked(conv) if masked_text else conv


def _normalized_summary(conv: Conversation, masked_text: bool) -> str:
    cached = _summaries.get((conv.id, masked_text))
    if cached is None or cached[0] is not conv:
        cached = _summaries[(conv.id, masked_text)] = (
            conv, normalize_text(_source(conv, masked_text).analysis.summary))
    return cached[1]


def _normalized_turns(conv: Conversation, masked_text: bool) -> tuple[tuple[str, str], ...]:
    cached = _turns.get((conv.id, masked_text))
    if cached is None or cached[0] is not conv:
        cached = _turns[(conv.id, masked_text)] = (
            conv, tuple((t.speaker, normalize_text(t.text)) for t in _source(conv, masked_text).turns))
    return cached[1]


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


def _text(cond: Condition, fdef: FieldDef, conv: Conversation) -> bool:
    needle = normalize_text(cond.value)
    masked_text = masking_enabled()
    if fdef.text_of is not None:  # ANI, DNIS y externalTag no se enmascaran (FE012)
        found = needle in normalize_text(fdef.text_of(conv) or "")
    elif cond.field == "summary":
        found = needle in _normalized_summary(conv, masked_text)
    else:
        found = any(needle in text for speaker, text in _normalized_turns(conv, masked_text)
                    if cond.speaker is None or speaker == cond.speaker)
    return found if cond.operator == "contains" else not found


def _is_empty(cond: Condition, fdef: FieldDef, conv: Conversation) -> bool:
    if fdef.type == "check":
        return check_state(conv, fdef.key.removeprefix("check:")) == PENDING
    if fdef.text_of is not None:
        return not (fdef.text_of(conv) or "").strip()
    if fdef.key == "summary":
        return not conv.analysis.summary.strip()
    if fdef.key == "transcript":
        return not any(cond.speaker is None or t.speaker == cond.speaker for t in conv.turns)
    value = fdef.extract(conv)
    return value is None or value == []


def _condition(cond: Condition, conv: Conversation, fields: dict[str, FieldDef]) -> bool:
    fdef = fields[cond.field]
    if cond.operator in EMPTY_OPERATORS:
        return _is_empty(cond, fdef, conv) == (cond.operator == "is_empty")
    # Un campo sin analizar no cumple ninguna condición salvo «está vacío» (FE012, criterio 10), campo a campo (FE014).
    if fdef.analysis and _is_empty(cond, fdef, conv):
        return False
    if fdef.type == "text":
        return _text(cond, fdef, conv)
    value = fdef.extract(conv)
    if value is None and fdef.type in ("categorical", "numeric", "boolean"):
        return False
    if fdef.type == "categorical":
        return _categorical(cond, value)
    if fdef.type == "numeric":
        return _numeric(cond, value)
    if fdef.type == "check":
        return _check(cond, value)
    return value == cond.value


def evaluate(node: Group | Condition, conv: Conversation, fields: dict[str, FieldDef] | None = None) -> bool:
    fields = fields or get_fields()
    if isinstance(node, Condition):
        return _condition(node, conv, fields)
    if not node.conditions:
        return True
    results = (evaluate(child, conv, fields) for child in node.conditions)
    return all(results) if node.op == "and" else any(results)


def run_query(query: Query, conversations: list[Conversation]) -> list[Conversation]:
    zone, fields = current_zone(), get_fields()
    return [c for c in conversations
            if query.date_from <= local_day(c.started_at, zone) <= query.date_to and evaluate(query.root, c, fields)]

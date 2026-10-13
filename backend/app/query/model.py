from datetime import date, timedelta
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, ValidationError

from app import ids
from app.data.store import default_period_end
from app.query.fields import EMPTY_OPERATORS, SPEAKERS, FieldDef, get_fields

MAX_DEPTH = 2
MAX_CONDITIONS = 50
MAX_LIST_VALUES = 200
DEFAULT_PERIOD_DAYS = 30


class QueryError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__("consulta no válida")
        self.errors = errors


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    operator: str
    value: Any = None
    speaker: str | None = None


def _node_kind(value: Any) -> str:
    if isinstance(value, dict):
        return "group" if "op" in value else "condition"
    return "group" if isinstance(value, Group) else "condition"


class Group(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["and", "or"]
    conditions: list[
        Annotated[Union[Annotated[Condition, Tag("condition")], Annotated["Group", Tag("group")]], Discriminator(_node_kind)]
    ] = []


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    date_from: date | None = Field(None, alias="from")
    date_to: date | None = Field(None, alias="to")
    root: Group


def default_period() -> tuple[date, date]:
    date_to = default_period_end()
    return date_to - timedelta(days=DEFAULT_PERIOD_DAYS - 1), date_to


def _path_from_loc(loc: tuple) -> tuple[str, str | None]:
    path, attribute, items = "", None, list(loc)
    while items:
        part = items.pop(0)
        if part in ("condition", "group"):
            continue
        if part == "conditions" and items and isinstance(items[0], int):
            path += f".conditions[{items.pop(0)}]"
        elif isinstance(part, str):
            if not path:
                path = part
            else:
                attribute = part
    return path, attribute


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_condition(cond: Condition, path: str) -> str | None:
    fdef: FieldDef | None = get_fields().get(cond.field)
    if fdef is None:
        return f"Campo desconocido: {cond.field}"
    if cond.operator not in fdef.operators:
        return f"Operador '{cond.operator}' no válido para el campo {fdef.label}"
    if cond.speaker is not None and not fdef.speakers:
        return f"El campo {fdef.label} no admite hablante"
    if cond.speaker is not None and cond.speaker not in SPEAKERS:
        return f"Hablante no válido: {cond.speaker}"
    if cond.operator in EMPTY_OPERATORS:  # «está vacío» no lleva valor (FE012)
        cond.value = None
        return None
    return {
        "categorical": _check_categorical, "numeric": _check_numeric, "check": _check_check,
        "text": _check_text, "boolean": _check_boolean,
    }[fdef.type](cond, fdef)


def _check_categorical(cond: Condition, fdef: FieldDef) -> str | None:
    allowed = {v for v, _ in fdef.values}
    normalize = ids.normalize if fdef.id_prefix else (lambda v: v)
    if cond.operator in ("in", "not_in"):
        if not isinstance(cond.value, list) or not cond.value:
            return f"'{cond.operator}' espera una lista de valores no vacía"
        if len(cond.value) > MAX_LIST_VALUES:
            return f"Una lista admite como máximo {MAX_LIST_VALUES} valores"
        values = [normalize(v) if isinstance(v, str) else v for v in cond.value]
    else:
        if not isinstance(cond.value, str):
            return f"{fdef.label} espera un único valor de texto"
        values = [normalize(cond.value)]
    invalid = [v for v in values if v not in allowed]
    if invalid:
        return f"Valor no válido para {fdef.label}: {', '.join(map(str, invalid))}"
    cond.value = values if cond.operator in ("in", "not_in") else values[0]
    return None


def _check_numeric(cond: Condition, fdef: FieldDef) -> str | None:
    if cond.operator == "between":
        if not (isinstance(cond.value, list) and len(cond.value) == 2 and all(map(_is_number, cond.value))
                and cond.value[0] <= cond.value[1]):
            return "'entre' requiere dos números [mín, máx] con mín ≤ máx"
        numbers = cond.value
    else:
        if not _is_number(cond.value):
            return f"{fdef.label} espera un número"
        numbers = [cond.value]
    if any(n < fdef.min or n > fdef.max for n in numbers):
        return f"{fdef.label} fuera de rango [{fdef.min}, {fdef.max}]"
    return None


def _check_check(cond: Condition, fdef: FieldDef) -> str | None:
    cond.value = None
    return None


def _check_text(cond: Condition, fdef: FieldDef) -> str | None:
    if not isinstance(cond.value, str) or not cond.value.strip():
        return f"{fdef.label} espera un texto no vacío"
    cond.value = cond.value.strip()
    return None


def _check_boolean(cond: Condition, fdef: FieldDef) -> str | None:
    if not isinstance(cond.value, bool):
        return f"{fdef.label} espera un booleano (true o false)"
    return None


def _walk(group: Group, path: str, depth: int, errors: list[dict]) -> None:
    for i, node in enumerate(group.conditions):
        node_path = f"{path}.conditions[{i}]"
        if isinstance(node, Group):
            if depth + 1 > MAX_DEPTH:
                errors.append({"path": node_path, "message": f"Maximum nesting level: {MAX_DEPTH}"})
            else:
                _walk(node, node_path, depth + 1, errors)
        else:
            message = _check_condition(node, node_path)
            if message:
                errors.append({"path": node_path, "message": message})


def _count_conditions(group: Group) -> int:
    return sum(_count_conditions(n) if isinstance(n, Group) else 1 for n in group.conditions)


def parse_query(payload: dict) -> Query:
    try:
        query = Query.model_validate(payload)
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            path, attribute = _path_from_loc(tuple(err["loc"]))
            message = f"{attribute}: {err['msg']}" if attribute else err["msg"]
            errors.append({"path": path or "root", "message": message})
        raise QueryError(errors) from None

    default_from, default_to = default_period()
    query.date_from = query.date_from or default_from
    query.date_to = query.date_to or default_to
    errors: list[dict] = []
    if query.date_from > query.date_to:
        errors.append({"path": "from", "message": "'from' must be before or equal to 'to'"})
    if _count_conditions(query.root) > MAX_CONDITIONS:
        errors.append({"path": "root", "message": f"A query allows at most {MAX_CONDITIONS} conditions"})
    else:
        _walk(query.root, "root", 1, errors)
    if errors:
        raise QueryError(errors)
    return query

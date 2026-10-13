"""Campos destino del Output «Guardar en campos» (FE013 y FE014): qué valores acepta cada uno.

`coerce(destino, valor)` devuelve lo que se guarda, `NO_VALUE` si la respuesta dice que no hay nada que guardar (una
entidad vacía o una lista vacía) o lanza `ValueRejected` con el motivo. Los textos se comparan sin distinguir
mayúsculas, tildes ni espacios en los extremos. Los rangos los aplica la API y no el proveedor: la salida estructurada
de Anthropic no admite `minimum`, `maximum` ni restricciones de listas (spec de FE014, riesgos).

Las reglas del editor (`app/flows/rules.py`) usan los mismos conjuntos de valores válidos (`accepts_option`).
"""
import math
from typing import Any

from app.config.store import get_config
from app.flows import catalog
from app.text import normalize_text

NO_VALUE = object()
RESOLUTIONS = {"resuelta": "Resuelta", "no_resuelta": "No resuelta", "escalada": "Escalada"}
CHURN_RISKS = ("bajo", "medio", "alto")
COMPLIANCE_ANSWERS = {"cumple": True, "no_cumple": False, "no_aplica": None}
RANGES = {"csat": (1, 5), "effort": (1, 5), "sentiment": (-1, 1)}
MAX_KEYWORDS = 10


class ValueRejected(ValueError):
    pass


def _key(value: str) -> str:
    """`" No Aplica "` → `"no_aplica"`: sin mayúsculas, tildes ni espacios, que pasan a ser guiones bajos."""
    return "_".join(normalize_text(value).split())


def _taxonomy_code(value: str, topics: dict) -> str | None:
    wanted = normalize_text(value.strip())
    for code, topic in topics.items():
        if topic.active and wanted in (normalize_text(code), normalize_text(topic.name)):
            return code
    return None


def topic_code(value: str) -> str | None:
    """Código de un main topic **activo** dado por código o por nombre."""
    return _taxonomy_code(value, get_config().main_topics)


def secondary_topic_code(value: str) -> str | None:
    return _taxonomy_code(value, get_config().secondary_topics)


def _resolution(value: str) -> str | None:
    key = _key(value)
    return next((code for code, label in RESOLUTIONS.items() if key in (code, _key(label))), None)


def _check_answer(value: str) -> tuple[bool, bool | None]:
    key = _key(value)
    return (key in COMPLIANCE_ANSWERS, COMPLIANCE_ANSWERS.get(key))


def accepts_option(target: str, option: str) -> bool:
    """Si un valor permitido de un campo JSON es un valor válido del destino (reglas del editor, criterio 6)."""
    if target == "main_topic":
        return topic_code(option) is not None
    if target == "secondary_topics":
        return secondary_topic_code(option) is not None
    if target == "resolution":
        return _resolution(option) is not None
    if target == "churn_risk":
        return _key(option) in CHURN_RISKS
    if catalog.check_code(target):
        return _check_answer(option)[0]
    return True


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueRejected(f"{label}: se esperaba un texto")
    return value.strip()


def _texts(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueRejected(f"{label}: se esperaba una lista de textos")
    return [v.strip() for v in value]


def coerce(target: str, value: Any) -> Any:
    config = get_config()
    label = catalog.target_label(target, config.checks)
    if target in RANGES:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueRejected(f"{label}: se esperaba un número")
        low, high = RANGES[target]
        if not low <= value <= high:
            raise ValueRejected(f"{label}: {value} está fuera del rango de {low} a {high}")
        return float(value)
    if target in ("secondary_topics", "keywords"):
        values = _texts(value, label)
        if not values:
            return NO_VALUE
        if target == "keywords":
            if not all(values):
                raise ValueRejected(f"{label}: hay una palabra clave vacía")
            return values[:MAX_KEYWORDS]
        codes = []
        for item in values:
            code = secondary_topic_code(item)
            if code is None:
                raise ValueRejected(f"{label}: «{item[:80]}» no es un tema secundario activo")
            if code not in codes:
                codes.append(code)
        return codes
    text = _text(value, label)
    code = catalog.check_code(target)
    if code is not None:
        check = config.checks.get(code)
        if check is None or not check.active:
            raise ValueRejected(f"{label}: el check ya no existe o está desactivado")
        known, answer = _check_answer(text)
        if not known:
            raise ValueRejected(f"{label}: «{text[:80]}» no es cumple, no_cumple ni no_aplica")
        return answer
    if target.startswith(catalog.ENTITY_PREFIX):
        return text or NO_VALUE
    if target == "summary":
        if not text:
            raise ValueRejected(f"{label}: la respuesta está vacía")
        return text
    if target == "main_topic":
        found = topic_code(text)
        if found is None:
            raise ValueRejected(f"«{text[:80]}» no es un main topic activo")
        return found
    if target == "resolution":
        found = _resolution(text)
        if found is None:
            raise ValueRejected(f"{label}: «{text[:80]}» no es resuelta, no_resuelta ni escalada")
        return found
    if target == "churn_risk":
        if _key(text) not in CHURN_RISKS:
            raise ValueRejected(f"{label}: «{text[:80]}» no es bajo, medio ni alto")
        return _key(text)
    raise ValueRejected(f"Campo destino desconocido: {target}")

"""Cumplimiento efectivo de cada conversación según los checks configurados (FE005, criterio 9).

Todo lo que antes leía `analysis.compliance` (detalle, KPI, desglose por check, filtro `compliant` del drill-down y
campos `check:*` del explorador) pasa por aquí, así que un cambio de configuración se refleja en todos a la vez.
"""
from app.config.checks import Check
from app.config.store import Config, get_config
from app.models import Conversation
from app.text import normalize_text

# Turnos del agente normalizados, por conversación. Se comprueba que sigue siendo el mismo objeto: una descarga nueva de
# conversaciones reales (FE012) lo sustituye, y las que crean los tests tienen su propio identificador.
_agent_texts: dict[str, tuple[Conversation, str]] = {}


def _agent_text(conv: Conversation) -> str:
    """Se evalúa sobre el texto original: el enmascarado solo afecta a lo que se ve."""
    cached = _agent_texts.get(conv.id)
    if cached is None or cached[0] is not conv:
        text = "\n".join(normalize_text(t.text) for t in conv.turns if t.speaker == "agente")
        cached = _agent_texts[conv.id] = (conv, text)
    return cached[1]


def evaluate(check: Check, conv: Conversation) -> bool | None:
    if conv.analysis.pending or not check.applies_to(conv.channel):
        return None  # sin analizar (FE012) o un check que no aplica al canal
    if check.builtin:
        return conv.analysis.compliance.get(check.code)
    text = _agent_text(conv)
    return any(normalize_text(phrase) in text for phrase in check.phrases)


_cache: tuple[Config, dict[str, dict[str, bool | None]]] | None = None


def _results(conv: Conversation, config: Config) -> dict[str, bool | None]:
    """Resultado de todos los checks (activos o no), cacheado por instantánea de configuración."""
    global _cache
    if _cache is None or _cache[0] is not config:
        _cache = (config, {})
    by_conv = _cache[1]
    result = by_conv.get(conv.id)
    if result is None:
        result = by_conv[conv.id] = {code: evaluate(check, conv) for code, check in config.checks.items()}
    return result


def check_result(conv: Conversation, code: str) -> bool | None:
    return _results(conv, get_config()).get(code)


def effective_compliance(conv: Conversation) -> dict[str, bool | None]:
    """Resultado de los checks activos, en su orden de configuración."""
    config = get_config()
    results = _results(conv, config)
    return {code: results[code] for code, check in config.checks.items() if check.active}


def is_compliant(conv: Conversation) -> bool:
    return all(v for v in effective_compliance(conv).values() if v is not None)


def active_checks() -> list[Check]:
    return [c for c in get_config().checks.values() if c.active]

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


PENDING = "pendiente"  # sin resultado todavía: ni del análisis ni, en un check personalizado, de sus frases


def evaluate(check: Check, conv: Conversation) -> bool | None | str:
    """`True` (cumple), `False` (no cumple), `None` (no aplica) o `PENDING`.

    Un resultado guardado en el análisis (el sintético, o el de un flujo de insights con un LLM, FE014) manda sobre las
    frases. Sin él, un check base queda pendiente y uno personalizado se evalúa por frases (ADR-007).
    """
    if not check.applies_to(conv.channel):
        return None
    if check.code in conv.analysis.compliance:
        return conv.analysis.compliance[check.code]
    if check.builtin:
        return PENDING
    text = _agent_text(conv)
    return any(normalize_text(phrase) in text for phrase in check.phrases)


_cache: tuple[Config, dict[str, tuple[Conversation, dict[str, bool | None | str]]]] | None = None


def _results(conv: Conversation, config: Config) -> dict[str, bool | None | str]:
    """Resultado de todos los checks (activos o no), cacheado por instantánea de configuración y por conversación: una
    recarga de las reales (un flujo acaba de escribir su cumplimiento, FE014) la sustituye por otro objeto."""
    global _cache
    if _cache is None or _cache[0] is not config:
        _cache = (config, {})
    by_conv = _cache[1]
    cached = by_conv.get(conv.id)
    if cached is None or cached[0] is not conv:
        cached = by_conv[conv.id] = (conv, {code: evaluate(check, conv) for code, check in config.checks.items()})
    return cached[1]


def check_state(conv: Conversation, code: str) -> bool | None | str:
    return _results(conv, get_config()).get(code, PENDING)


def check_result(conv: Conversation, code: str) -> bool | None:
    """Como `check_state`, con un pendiente leído como «sin resultado» (`None`)."""
    state = check_state(conv, code)
    return None if state == PENDING else state


def _active_states(conv: Conversation) -> dict[str, bool | None | str]:
    config = get_config()
    results = _results(conv, config)
    return {code: results[code] for code, check in config.checks.items() if check.active}


def effective_compliance(conv: Conversation) -> dict[str, bool | None]:
    """Resultado de los checks activos que lo tienen, en su orden de configuración."""
    return {code: state for code, state in _active_states(conv).items() if state != PENDING}


def pending_checks(conv: Conversation) -> list[str]:
    return [code for code, state in _active_states(conv).items() if state == PENDING]


def has_compliance(conv: Conversation) -> bool:
    """Si la conversación cuenta para el cumplimiento: algún check activo que le aplica tiene resultado (FE014)."""
    config = get_config()
    return any(state != PENDING and config.checks[code].applies_to(conv.channel)
               for code, state in _active_states(conv).items())


def is_compliant(conv: Conversation) -> bool:
    return all(v for v in effective_compliance(conv).values() if v is not None)


def active_checks() -> list[Check]:
    return [c for c in get_config().checks.values() if c.active]

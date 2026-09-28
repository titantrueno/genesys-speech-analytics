"""Enmascarado de datos personales por patrones (FE005, criterio 10).

`mask` sustituye emails, IBAN, tarjetas completas, DNI/NIE y teléfonos por `[EMAIL]`, `[IBAN]`, `[TARJETA]`, `[DNI]`
y `[TELÉFONO]`. El orden importa: el IBAN y la tarjeta van antes que el DNI y el teléfono, para que un número largo no
se enmascare a trozos. Los últimos 4 dígitos de una tarjeta («terminada en 1234») no identifican a nadie y se
conservan, igual que importes, fechas y horas.
"""
import re
from app.models import Conversation

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("[IBAN]", re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?(?![A-Za-z0-9])")),
    ("[TARJETA]", re.compile(r"(?<!\d)(?:\d{4}[ -]?){3}\d{1,7}(?!\d)")),
    ("[DNI]", re.compile(rf"(?<![\w-])(?:[XYZxyz][- ]?\d{{7}}|\d{{8}})[- ]?[{_DNI_LETTERS}{_DNI_LETTERS.lower()}](?!\w)")),
    ("[TELÉFONO]", re.compile(r"(?<![\w+])(?:(?:\+|00)34[ -]?)?[6789]\d{2}(?:(?:[ -]?\d{3}){2}|(?:[ -]\d{2}){3})(?![\w,.]\d|\w)")),
]


def mask(text: str) -> str:
    for token, pattern in PATTERNS:
        text = pattern.sub(token, text)
    return text


_cache: dict[str, tuple[Conversation, Conversation]] = {}


def masked(conversation: Conversation) -> Conversation:
    """Copia de la conversación con la transcripción y el summary enmascarados; el dataset no cambia.

    Se cachea por identificador, comprobando que el original es el mismo objeto (los tests crean conversaciones propias).
    """
    cached = _cache.get(conversation.id)
    if cached is not None and cached[0] is conversation:
        return cached[1]
    analysis = conversation.analysis.model_copy(update={"summary": mask(conversation.analysis.summary)})
    turns = [t.model_copy(update={"text": mask(t.text)}) for t in conversation.turns]
    result = conversation.model_copy(update={"turns": turns, "analysis": analysis})
    _cache[conversation.id] = (conversation, result)
    return result


def masking_enabled() -> bool:
    from app.config.store import get_config  # import diferido: la configuración depende de auth y flujos
    return get_config().privacy.pii_masking


def shown(conversation: Conversation) -> Conversation:
    """La conversación tal como se muestra: enmascarada si el interruptor de Privacidad está activado."""
    return masked(conversation) if masking_enabled() else conversation

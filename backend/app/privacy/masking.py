"""Enmascarado de datos personales por patrones (FE005, criterio 10).

`mask` sustituye emails, IBAN, tarjetas completas, DNI/NIE y teléfonos por `[EMAIL]`, `[IBAN]`, `[TARJETA]`, `[DNI]`
y `[TELÉFONO]`. El orden importa: el IBAN y la tarjeta van antes que el DNI y el teléfono, para que un número largo no
se enmascare a trozos. Un DNI/NIE solo se enmascara si va pegado a su letra (o con guion) y la letra de control cuadra:
un número de 8 cifras seguido de «y», «a» o «e» no es un DNI. Los últimos 4 dígitos de una tarjeta («terminada en
1234») no identifican a nadie y se conservan, igual que importes, fechas y horas.
"""
import re

from app.models import Conversation

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("[IBAN]", re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,3})?(?![A-Za-z0-9])")),
    ("[TARJETA]", re.compile(r"(?<!\d)(?:\d{4}[ -]?){3}\d{1,7}(?!\d)")),
    ("[DNI]", re.compile(r"(?<![\w-])(?P<prefix>[XYZxyz]-?)?(?P<number>\d{7,8})-?(?P<letter>[A-Za-z])(?!\w)")),
    ("[TELÉFONO]", re.compile(r"(?<![\w+])(?:(?:\+|00)34[ -]?)?[6789]\d{2}(?:(?:[ -]?\d{3}){2}|(?:[ -]\d{2}){3})(?![\w,.]\d|\w)")),
]


def _dni(match: re.Match) -> str:
    """Solo es un DNI/NIE si la letra de control cuadra (en el NIE, X, Y y Z valen 0, 1 y 2): así «20213570 y» no lo es."""
    prefix, number, letter = match["prefix"], match["number"], match["letter"].upper()
    if prefix:
        if len(number) != 7:
            return match[0]
        number = str("XYZ".index(prefix[0].upper())) + number
    elif len(number) != 8:
        return match[0]
    return "[DNI]" if _DNI_LETTERS[int(number) % 23] == letter else match[0]


def mask(text: str) -> str:
    for token, pattern in PATTERNS:
        text = pattern.sub(_dni if token == "[DNI]" else token, text)
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

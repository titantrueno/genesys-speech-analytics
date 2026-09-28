"""Normalización y tokenización compartidas por el motor, la expansión y el resaltado."""
import re
from collections.abc import Iterable

from app.query.fields import normalize_text

# «no» y «sin» cambian el sentido («no reconozco»), así que no son palabras vacías.
STOPWORDS = {
    "a", "al", "algo", "con", "de", "del", "el", "en", "es", "esa", "ese", "eso", "esta", "este", "esto", "ha",
    "han", "he", "la", "las", "le", "les", "lo", "los", "me", "mi", "mis", "o", "para", "pero", "por", "que",
    "se", "su", "sus", "te", "tu", "un", "una", "unos", "unas", "y", "ya", "yo",
}
_WORD_RE = re.compile(r"[a-z0-9]+")
_SURFACE_WORD_RE = re.compile(r"\w+")
MIN_HIGHLIGHT = 3
STEM = 5


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(normalize_text(text)) if w not in STOPWORDS]


def matching_terms(text: str, terms: Iterable[str]) -> list[str]:
    """Palabras de `text`, tal y como aparecen, que coinciden con algún término normalizado.

    Coinciden si son iguales o comparten los 5 primeros caracteres («bloqueada» ~ «bloquear»).
    """
    wanted = {t for t in terms if len(t) >= MIN_HIGHLIGHT}
    stems = {t[:STEM] for t in wanted if len(t) >= STEM}
    found: list[str] = []
    for match in _SURFACE_WORD_RE.finditer(text):
        word = match.group()
        norm = normalize_text(word)
        if len(norm) < MIN_HIGHLIGHT or word in found:
            continue
        if norm in wanted or (len(norm) >= STEM and norm[:STEM] in stems):
            found.append(word)
    return found

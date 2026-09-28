"""Normalización de texto compartida: comparar sin distinguir mayúsculas ni tildes."""
import unicodedata


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()

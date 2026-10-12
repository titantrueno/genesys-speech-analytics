"""Campos destino del Output «Guardar en campos» (FE013): qué valores acepta cada uno.

`main_topic` solo acepta main topics **activos** de la taxonomía, por código o por nombre (sin distinguir mayúsculas,
tildes ni espacios en los extremos), y se guarda siempre por su código.
"""
from app.config.store import get_config
from app.text import normalize_text


def topic_code(value: str) -> str | None:
    wanted = normalize_text(value.strip())
    for code, topic in get_config().main_topics.items():
        if topic.active and wanted in (normalize_text(code), normalize_text(topic.name)):
            return code
    return None

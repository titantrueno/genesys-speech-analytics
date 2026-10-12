"""Lectura del `.env` de la raíz con una lista blanca de claves por proceso (FE011, criterio 3).

La API solo conoce cómo llegar al servicio de ingesta; las credenciales de Genesys son del servicio de ingesta y la API
nunca las lee. Una variable de entorno tiene prioridad sobre el fichero.
"""
import os
from collections.abc import Iterable
from pathlib import Path

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
API_KEYS = ("INGESTION_URL", "INGESTION_TOKEN")
# Lectura de solo lectura de las conversaciones reales (FE012). Nunca las credenciales de Genesys.
API_DATABASE_KEYS = ("DATABASE_URL",)
# Servicio de LLM (FE013): es el único proceso que lee las claves de los proveedores.
LLM_KEYS = ("LLM_TOKEN", "LLM_MAX_CONCURRENCY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def _parse(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return {}
    values = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def read_env(keys: Iterable[str], path: Path = ROOT_ENV) -> dict[str, str]:
    """Valores de `keys` presentes en el entorno o en el fichero; el resto de claves del fichero se ignoran."""
    keys = tuple(keys)
    from_file = _parse(path)
    values = {}
    for key in keys:
        value = os.environ.get(key, from_file.get(key))
        if value:
            values[key] = value
    return values


def api_env(path: Path = ROOT_ENV) -> dict[str, str]:
    return read_env(API_KEYS, path)

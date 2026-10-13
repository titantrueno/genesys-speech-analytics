"""Configuración del servicio de LLM: su lista blanca de claves del `.env` (FE013, criterio 2).

Es el único proceso que lee las claves de los proveedores. Una clave vacía cuenta como no configurada.
"""
from dataclasses import dataclass, field
from pathlib import Path

from app.envfile import LLM_KEYS, ROOT_ENV, read_env

PROVIDER_KEYS = ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
DEFAULT_CONCURRENCY, MAX_CONCURRENCY = 4, 64


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    # Ni el token ni las claves entran en el `repr`, que acaba en logs y trazas.
    token: str = field(repr=False)
    api_keys: dict[str, str] = field(default_factory=dict, repr=False)
    max_concurrency: int = DEFAULT_CONCURRENCY


def _concurrency(value: str | None) -> int:
    if value is None:
        return DEFAULT_CONCURRENCY
    if not value.isdigit() or not 1 <= int(value) <= MAX_CONCURRENCY:
        raise SettingsError(f"LLM_MAX_CONCURRENCY must be an integer between 1 and {MAX_CONCURRENCY}")
    return int(value)


def load_settings(path: Path = ROOT_ENV) -> Settings:
    values = read_env(LLM_KEYS, path)
    if "LLM_TOKEN" not in values:
        raise SettingsError(f"Missing LLM_TOKEN in the environment or in {path.name}")
    return Settings(token=values["LLM_TOKEN"], api_keys={k: values[k] for k in PROVIDER_KEYS if k in values},
                    max_concurrency=_concurrency(values.get("LLM_MAX_CONCURRENCY")))

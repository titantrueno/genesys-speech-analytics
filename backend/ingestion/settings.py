"""Configuración del servicio de ingesta: su lista blanca de claves del `.env` (FE011, criterio 3)."""
from dataclasses import dataclass, field
from pathlib import Path

from app.envfile import ROOT_ENV, read_env

KEYS = ("DATABASE_URL", "INGESTION_TOKEN", "GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION")
REQUIRED = ("DATABASE_URL", "INGESTION_TOKEN")


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    # Ningún valor con credenciales entra en el `repr`, que acaba en logs y trazas.
    database_url: str = field(repr=False)
    token: str = field(repr=False)
    genesys_client_id: str | None = None
    genesys_client_secret: str | None = field(default=None, repr=False)
    genesys_region: str | None = None


def load_settings(path: Path = ROOT_ENV) -> Settings:
    values = read_env(KEYS, path)
    missing = [key for key in REQUIRED if key not in values]
    if missing:
        raise SettingsError(f"Missing {', '.join(missing)} in the environment or in {path.name}")
    return Settings(
        database_url=values["DATABASE_URL"],
        token=values["INGESTION_TOKEN"],
        genesys_client_id=values.get("GENESYS_CLIENT_ID"),
        genesys_client_secret=values.get("GENESYS_CLIENT_SECRET"),
        genesys_region=values.get("GENESYS_REGION"),
    )

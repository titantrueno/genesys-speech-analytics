"""Configuración del servicio de ingesta y de la API (FE011, T1, criterio 3).

Cada proceso lee del `.env` solo su lista blanca de claves: la API nunca ve las credenciales de Genesys.
"""
import ast
from pathlib import Path

import pytest

from app import envfile
from ingestion.settings import Settings, SettingsError, load_settings

BACKEND = Path(__file__).resolve().parents[1]
ENV_FILE = """\
# Credenciales del laboratorio
GENESYS_CLIENT_ID=cliente-de-prueba
GENESYS_CLIENT_SECRET="secreto-de-prueba"
GENESYS_REGION=eu-west-1
DATABASE_URL=postgresql://speech:clave@localhost:5432/speech_analytics
INGESTION_TOKEN='token-de-prueba'
OTRA_CLAVE=sin-uso
"""


@pytest.fixture
def env_path(tmp_path, monkeypatch):
    for key in ["GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION", "DATABASE_URL", "INGESTION_TOKEN",
                "INGESTION_URL", "OTRA_CLAVE"]:
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(ENV_FILE)
    return path


def test_the_api_only_reads_its_own_keys(env_path):
    assert envfile.api_env(env_path) == {"INGESTION_TOKEN": "token-de-prueba"}


def test_the_environment_overrides_the_file(env_path, monkeypatch):
    monkeypatch.setenv("INGESTION_URL", "http://ingesta:8001")
    monkeypatch.setenv("INGESTION_TOKEN", "token-del-entorno")
    assert envfile.api_env(env_path) == {"INGESTION_URL": "http://ingesta:8001", "INGESTION_TOKEN": "token-del-entorno"}


def test_a_missing_file_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv("INGESTION_TOKEN", raising=False)
    monkeypatch.delenv("INGESTION_URL", raising=False)
    assert envfile.api_env(tmp_path / "no-existe.env") == {}


def test_the_ingestion_service_reads_its_settings(env_path):
    settings = load_settings(env_path)
    assert settings.database_url == "postgresql://speech:clave@localhost:5432/speech_analytics"
    assert settings.token == "token-de-prueba"
    assert (settings.genesys_client_id, settings.genesys_client_secret, settings.genesys_region) == (
        "cliente-de-prueba", "secreto-de-prueba", "eu-west-1")


def test_secrets_never_appear_in_the_settings_representation(env_path):
    text = repr(load_settings(env_path))
    for secret in ["secreto-de-prueba", "token-de-prueba", "clave@"]:
        assert secret not in text


@pytest.mark.parametrize("missing", ["DATABASE_URL", "INGESTION_TOKEN"])
def test_the_service_refuses_to_start_without_database_or_token(env_path, missing):
    env_path.write_text("\n".join(line for line in ENV_FILE.splitlines() if not line.startswith(missing)))
    with pytest.raises(SettingsError, match=missing):
        load_settings(env_path)


def test_settings_built_in_code_need_no_genesys_credentials():
    assert Settings(database_url="postgresql://x", token="t").genesys_client_secret is None


def _imports(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules |= {node.module} | {f"{node.module}.{alias.name}" for alias in node.names}
    return modules


def test_the_ingestion_package_only_shares_identifiers_clock_and_env_with_the_api():
    allowed = ("app.ids", "app.clock", "app.envfile")
    for path in (BACKEND / "ingestion").rglob("*.py"):
        used = {m for m in _imports(path) if m.startswith("app.")}
        forbidden = {m for m in used if not any(m == a or m.startswith(f"{a}.") for a in allowed)}
        assert not forbidden, f"{path.relative_to(BACKEND)} importa {sorted(forbidden)}"


def test_the_api_never_imports_the_ingestion_package():
    for path in (BACKEND / "app").rglob("*.py"):
        assert not any(m == "ingestion" or m.startswith("ingestion.") for m in _imports(path)), path

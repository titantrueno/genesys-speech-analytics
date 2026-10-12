"""Configuración del servicio de LLM y su aislamiento (FE013, T4; criterio 2).

El servicio de LLM es el único proceso que lee las claves de los proveedores; la API y la ingesta nunca las ven.
"""
from pathlib import Path

import pytest

from app import envfile
from ingestion import settings as ingestion_settings
from llm.settings import Settings, SettingsError, load_settings
from tests.test_ingestion_settings import _imports

BACKEND = Path(__file__).resolve().parents[1]
PROVIDER_KEYS = ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
ENV_FILE = """\
GEMINI_API_KEY=clave-gemini-ficticia
OPENAI_API_KEY="clave-openai-ficticia"
ANTHROPIC_API_KEY=
LLM_TOKEN=token-llm-de-prueba
LLM_MAX_CONCURRENCY=6
INGESTION_TOKEN=token-de-ingesta
DATABASE_URL=postgresql://speech:clave@localhost:5432/speech_analytics
"""


@pytest.fixture
def env_path(tmp_path, monkeypatch):
    for key in (*PROVIDER_KEYS, "LLM_TOKEN", "LLM_MAX_CONCURRENCY", "LLM_URL", "INGESTION_TOKEN", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(ENV_FILE)
    return path


def test_the_llm_service_reads_only_its_keys(env_path):
    settings = load_settings(env_path)
    assert settings.token == "token-llm-de-prueba"
    assert settings.max_concurrency == 6
    # Una clave vacía es una clave sin configurar.
    assert settings.api_keys == {"GEMINI_API_KEY": "clave-gemini-ficticia", "OPENAI_API_KEY": "clave-openai-ficticia"}


def test_keys_never_appear_in_the_settings_representation(env_path):
    text = repr(load_settings(env_path))
    for secret in ("clave-gemini-ficticia", "clave-openai-ficticia", "token-llm-de-prueba"):
        assert secret not in text


def test_the_service_refuses_to_start_without_its_token(env_path):
    env_path.write_text("\n".join(line for line in ENV_FILE.splitlines() if not line.startswith("LLM_TOKEN")))
    with pytest.raises(SettingsError, match="LLM_TOKEN"):
        load_settings(env_path)


@pytest.mark.parametrize("value", ["cero", "0", "65"])
def test_an_invalid_concurrency_is_refused(env_path, value):
    env_path.write_text(ENV_FILE.replace("LLM_MAX_CONCURRENCY=6", f"LLM_MAX_CONCURRENCY={value}"))
    with pytest.raises(SettingsError, match="LLM_MAX_CONCURRENCY"):
        load_settings(env_path)


def test_concurrency_defaults_to_four():
    assert Settings(token="t").max_concurrency == 4


def test_neither_the_api_nor_the_ingestion_service_read_provider_keys(env_path):
    for key in PROVIDER_KEYS:
        assert key not in envfile.API_KEYS + envfile.API_DATABASE_KEYS
        assert key not in ingestion_settings.KEYS
    assert set(envfile.api_env(env_path)) <= {"LLM_URL", "LLM_TOKEN", "INGESTION_URL", "INGESTION_TOKEN"}
    assert all(key not in envfile.read_env(ingestion_settings.KEYS, env_path) for key in PROVIDER_KEYS)


def test_no_module_outside_the_llm_service_names_a_provider_key():
    for package in ("app", "ingestion"):
        for path in (BACKEND / package).rglob("*.py"):
            if path == BACKEND / "app" / "envfile.py":
                continue  # define la lista blanca del servicio de LLM
            text = path.read_text()
            assert not any(key in text for key in PROVIDER_KEYS), path.relative_to(BACKEND)


def test_the_llm_package_only_shares_identifiers_clock_and_env_with_the_api():
    allowed = ("app.ids", "app.clock", "app.envfile")
    for path in (BACKEND / "llm").rglob("*.py"):
        used = {m for m in _imports(path) if m.startswith("app.")}
        forbidden = {m for m in used if not any(m == a or m.startswith(f"{a}.") for a in allowed)}
        assert not forbidden, f"{path.relative_to(BACKEND)} importa {sorted(forbidden)}"
        assert not any(m == "ingestion" or m.startswith("ingestion.") for m in _imports(path)), path


def test_neither_the_api_nor_the_ingestion_service_import_the_llm_package():
    for package in ("app", "ingestion"):
        for path in (BACKEND / package).rglob("*.py"):
            assert not any(m == "llm" or m.startswith("llm.") for m in _imports(path)), path

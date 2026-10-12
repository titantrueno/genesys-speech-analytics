"""Ayudas de los tests del origen `real` (FE012): sembrado con el ejecutor de FE011 sobre el Genesys falso."""
import pytest

from app import auth
from ingestion.runs import RunExecutor, create_run
from tests.ingestion_helpers import DAY_END, DAY_START, client_factory, create_flow, fixtures, make_fake

SHORT_IDS = {
    "voz_bot_agente": "7b94988a", "voz_contenida_bot": "37dcbccf", "chat_bot_agente": "f7e79502",
    "chat_no_entregado": "9e3ec75a", "chat_reconexion": "c870bc58", "voz_agente_parcial": "687f2225",
}


def seed_real(database_url: str, conversations=None, start=DAY_START, end=DAY_END) -> int:
    """Carga en PostgreSQL las 10 fixtures de FE011 (o las indicadas) con una ejecución real del ejecutor."""
    flow_id = create_flow(database_url)
    run_id = create_run(database_url, flow_id, "manual", start, end, ["voz", "chat"], ("1US-PRUEBA", "Admin"))
    fake = make_fake(conversations)
    RunExecutor(database_url, client_factory(fake)).execute(run_id)
    return len(fixtures() if conversations is None else conversations)


@pytest.fixture
def real_api(api, pg_url, monkeypatch):
    """API con el origen `real` sobre una base sembrada con las fixtures de FE011."""
    monkeypatch.setenv("DATABASE_URL", pg_url)
    seed_real(pg_url)
    assert api.put("/api/config/sources", json={"origin": "real"}).status_code == 200
    return api


def as_role(api, role: str):
    user = auth.get_store().find_by_email(f"{role}@bancohorizonte.demo")
    api.headers["Authorization"] = f"Bearer {auth.create_token(user)}"
    return api

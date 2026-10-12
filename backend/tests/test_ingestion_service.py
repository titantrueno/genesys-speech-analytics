"""Servicio de ingesta (FE011, T1): token interno, CORS cerrado, salud y migraciones."""
import psycopg
import pytest
from fastapi.testclient import TestClient

from ingestion import db
from ingestion.main import create_app
from ingestion.settings import Settings

TOKEN = "token-interno-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
# Puerto 1 en local: la conexión se rechaza al instante, sin esperar a un tiempo de espera.
UNREACHABLE_DB = "postgresql://nadie@127.0.0.1:1/nada?connect_timeout=1"


def _client(database_url: str = UNREACHABLE_DB) -> TestClient:
    return TestClient(create_app(Settings(database_url=database_url, token=TOKEN), migrate_on_start=False))


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer otro-token"},
    {"Authorization": TOKEN},
    {"Authorization": f"Basic {TOKEN}"},
    {"Authorization": "Bearer ñandú-token".encode()},
])
def test_without_the_internal_token_every_request_is_rejected(headers):
    response = _client().get("/health", headers=headers)
    assert response.status_code == 401
    assert TOKEN not in response.text


def test_the_service_is_not_exposed_to_browsers():
    response = _client().options("/health", headers={"Origin": "http://localhost:5173",
                                                    "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in response.headers


def test_health_reports_an_unreachable_database_without_leaking_its_url():
    response = _client().get("/health", headers=AUTH)
    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "no disponible"}
    assert "127.0.0.1" not in response.text


@pytest.mark.pg
def test_health_with_the_token_and_the_database(pg_url):
    with TestClient(create_app(Settings(database_url=pg_url, token=TOKEN))) as client:
        response = client.get("/health", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.pg
def test_migrations_create_the_whole_schema(pg_url):
    with psycopg.connect(pg_url) as conn:
        applied = db.migrate(conn)
        tables = {row[0] for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
    assert applied == ["0001_initial"]
    assert {"schema_migrations", "conversation", "segment", "turn", "topic_hit", "analysis", "raw_payload",
            "queue", "agent", "flow", "wrapup", "division",
            "download_flow", "download_run", "run_log"} <= tables


@pytest.mark.pg
def test_running_the_migrations_again_keeps_the_data(pg_url):
    with psycopg.connect(pg_url) as conn:
        db.migrate(conn)
        conn.execute("INSERT INTO queue (id, genesys_id, name) VALUES (%s, %s, %s)",
                     ("1QU-00000000-0000-5000-8000-000000000000", "cola-genesys", "AIT_Transcription"))
    with TestClient(create_app(Settings(database_url=pg_url, token=TOKEN))):
        pass  # el arranque vuelve a migrar
    with psycopg.connect(pg_url) as conn:
        assert db.migrate(conn) == []
        assert conn.execute("SELECT name FROM queue").fetchall() == [("AIT_Transcription",)]

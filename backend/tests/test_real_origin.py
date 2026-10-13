"""Origen `real` (FE012, T2; criterios 2, 3 y 4): las secciones de datos leen PostgreSQL, caen con `503` si no responde
y ven las descargas nuevas sin reiniciar."""
import psycopg
import pytest

from app.data.store import get_dataset
from tests.ingestion_helpers import fixture, spread, DAY_START
from tests.real_helpers import real_api, seed_real  # noqa: F401  (fixture)

pytestmark = pytest.mark.pg
FIXTURE_COUNT = 10


def _total(api) -> int:
    response = api.get("/api/conversations", params={"from": "2026-10-01", "to": "2026-10-31", "page_size": 100})
    assert response.status_code == 200, response.text
    return response.json()["total"]


def test_the_real_origin_serves_only_the_database_conversations(real_api, pg_url):
    with psycopg.connect(pg_url) as conn:
        in_database = conn.execute("SELECT count(*) FROM conversation").fetchone()[0]
    assert in_database == FIXTURE_COUNT
    assert _total(real_api) == in_database
    assert len(get_dataset()) == in_database
    assert all(c.genesys is not None for c in get_dataset())


def test_switching_back_to_synthetic_restores_the_generated_dataset(real_api):
    real_api.put("/api/config/sources", json={"origin": "sintetico"})
    assert all(c.genesys is None for c in get_dataset())
    assert len(get_dataset()) > FIXTURE_COUNT


def test_new_downloads_appear_in_the_next_request(real_api, pg_url):
    assert _total(real_api) == FIXTURE_COUNT
    extra = spread([fixture("7b94988a")], 3, DAY_START, 1)
    seed_real(pg_url, extra)
    assert _total(real_api) == FIXTURE_COUNT + 3


def test_without_postgres_data_sections_answer_503_and_configuration_keeps_working(real_api, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nadie:nada@127.0.0.1:1/ninguna")
    for url in ("/api/conversations", "/api/metrics/summary", "/api/catalog"):
        response = real_api.get(url)
        assert response.status_code == 503, (url, response.status_code)
        assert "Real data" in response.json()["detail"]
    assert real_api.get("/api/config").status_code == 200
    assert real_api.put("/api/config/sources", json={"origin": "sintetico"}).status_code == 200
    assert real_api.get("/api/conversations").status_code == 200


# --- Casos límite del repositorio real (/test) ---

def test_the_api_connection_to_postgres_is_read_only(real_api):
    from app.data.real import real_repository
    with real_repository()._connect() as conn:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("UPDATE conversation SET duration_s = 0")
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("DELETE FROM turn")


def test_a_changed_database_url_is_noticed_even_within_the_same_request(real_api, pg_url, monkeypatch):
    from app.data.real import real_repository
    repository = real_repository()
    assert len(repository.conversations()) == FIXTURE_COUNT
    monkeypatch.setenv("DATABASE_URL", "postgresql://nadie:nada@127.0.0.1:1/ninguna")
    from app.data.repository import DataUnavailable
    with pytest.raises(DataUnavailable):
        repository.conversations()

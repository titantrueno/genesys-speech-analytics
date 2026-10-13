"""Un main topic usado en datos reales no se borra, sea cual sea el origen activo (FE013, T3; criterio 30)."""
import psycopg
import pytest

from tests.real_helpers import real_api, seed_real  # noqa: F401  (fixture)
from tests.test_config_taxonomy import MAIN, NEW_TOPIC, create, taxonomy, topic

pytestmark = pytest.mark.pg
UNREACHABLE = "postgresql://nadie:nada@127.0.0.1:1/ninguna"


def _assign_in_database(pg_url: str, code: str, count: int) -> None:
    """Simula lo que escribe un flujo de insights (FE013) en `count` conversaciones reales."""
    with psycopg.connect(pg_url) as conn:
        conn.execute("UPDATE analysis SET main_topic = %s WHERE conversation_id IN ("
                     "SELECT conversation_id FROM analysis ORDER BY conversation_id LIMIT %s)", (code, count))


def _codes(api) -> set[str]:
    return {t["code"] for t in taxonomy(api)["main_topics"]}


def test_a_topic_used_only_in_real_data_cannot_be_deleted_from_the_synthetic_origin(api, pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    seed_real(pg_url)
    created = create(api)
    assert created["conversations"] == 0  # el recuento visible es el del origen activo, el sintético
    _assign_in_database(pg_url, NEW_TOPIC["code"], 2)

    response = api.delete(f"{MAIN}/{created['id']}")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "0 synthetic conversations" in detail and "2 real" in detail and "deactivated" in detail
    assert NEW_TOPIC["code"] in _codes(api)


def test_if_postgres_does_not_answer_the_topic_is_not_deleted(api, pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE)
    created = create(api)
    response = api.delete(f"{MAIN}/{created['id']}")
    assert response.status_code == 503
    assert response.json()["detail"] == "Usage in the real data cannot be checked"
    assert NEW_TOPIC["code"] in _codes(api)


def test_without_database_url_only_the_synthetic_data_counts(api, pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    created = create(api)
    assert api.delete(f"{MAIN}/{created['id']}").status_code == 204
    assert NEW_TOPIC["code"] not in _codes(api)


def test_with_the_real_origin_the_synthetic_data_still_counts(real_api, pg_url):
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("SELECT count(*) FROM analysis WHERE main_topic = 'cajeros'").fetchone()[0] == 0
    cajeros = topic(real_api, "cajeros")
    assert cajeros["conversations"] == 0  # no la usa ninguna conversación real…
    response = real_api.delete(f"{MAIN}/{cajeros['id']}")
    assert response.status_code == 409  # …pero sí el dataset sintético
    assert "0 real" in response.json()["detail"]


def test_a_secondary_topic_is_not_checked_against_postgres(api, pg_url, monkeypatch):
    # Los temas secundarios no los escribe ningún flujo: su borrado no depende de que PostgreSQL responda.
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE)
    payload = {k: v for k, v in NEW_TOPIC.items() if k != "description"}
    created = create(api, payload, "/api/config/taxonomy/secondary-topics")
    assert api.delete(f"/api/config/taxonomy/secondary-topics/{created['id']}").status_code == 204

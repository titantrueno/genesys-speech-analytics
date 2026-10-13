import os

os.environ.setdefault("DATA_SEED", "42")
os.environ.setdefault("DATA_REFERENCE_DATE", "2026-09-27")
os.environ.setdefault("FLOW_RUN_STEP_DELAY_MS", "0")
# Los tests no leen la PostgreSQL de desarrollo del `.env`: un valor vacío tiene prioridad sobre el fichero. Los que
# necesitan una base la ponen con `monkeypatch.setenv("DATABASE_URL", pg_url)`.
os.environ["DATABASE_URL"] = ""
# Ni el servicio de LLM real (FE013): sin token, el cliente lo da por no disponible. Los tests usan un doble.
os.environ["LLM_TOKEN"] = ""
# Ni el servicio de ingesta (FE015): sin token, los flujos de insights y la configuración viven solo en memoria. Los
# tests que los guardan pasan su propio almacén a `reset_flow_store` y `reset_config_store`.
os.environ["INGESTION_TOKEN"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app.audit import reset_audit_log  # noqa: E402
from app.main import app  # noqa: E402
from app.config.store import reset_config_store  # noqa: E402
from app.flows.runs import reset_run_store  # noqa: E402
from app.flows.store import reset_flow_store  # noqa: E402
from app.query.saved import reset_saved_store  # noqa: E402


@pytest.fixture
def api():
    auth.reset_store()
    reset_saved_store()
    reset_flow_store()
    reset_run_store()
    reset_config_store()
    reset_audit_log()
    client = TestClient(app)
    admin = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    client.headers["Authorization"] = f"Bearer {auth.create_token(admin)}"
    return client


@pytest.fixture
def pg_url():
    """Base de PostgreSQL de tests (FE011), con el esquema `public` vacío.

    Sin `TEST_DATABASE_URL` el test se salta; con `REQUIRE_PG=1` (el gate) falla, para que `ci.sh` nunca pase en verde
    sin haber ejecutado los tests de PostgreSQL.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("REQUIRE_PG") == "1":
            pytest.fail("REQUIRE_PG=1 y falta TEST_DATABASE_URL")
        pytest.skip("Sin TEST_DATABASE_URL: los tests de PostgreSQL los ejecuta ./scripts/ci.sh")
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        name = conn.execute("SELECT current_database()").fetchone()[0]
        assert name.endswith("_test"), f"TEST_DATABASE_URL apunta a {name!r}: solo se vacía una base *_test"
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    return url

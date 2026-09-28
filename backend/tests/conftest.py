import os

os.environ.setdefault("DATA_SEED", "42")
os.environ.setdefault("DATA_REFERENCE_DATE", "2026-09-27")
os.environ.setdefault("FLOW_RUN_STEP_DELAY_MS", "0")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
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
    client = TestClient(app)
    admin = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    client.headers["Authorization"] = f"Bearer {auth.create_token(admin)}"
    return client

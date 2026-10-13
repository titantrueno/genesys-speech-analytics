"""API → servicio de ingesta real → PostgreSQL (FE011, T6).

Las respuestas reales cumplen los esquemas del OpenAPI de la API: si el servicio de ingesta cambia un campo, este test
falla aunque el doble de `tests/ingestion_stub.py` siga igual.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.ingestion_client import IngestionClient, get_ingestion_client
from app.main import app as api_app
from app.openapi import schemas as s
from ingestion.main import create_app
from ingestion.settings import Settings
from tests.ingestion_helpers import SECRET, client_factory, make_fake

pytestmark = pytest.mark.pg
TOKEN = "token-interno-de-prueba"
BODY = {"name": "Descarga del día", "interval": {"type": "relativo", "unit": "hoy"}, "channels": ["voz", "chat"],
        "schedule": {"type": "cada_horas", "hours": 6}, "active": True}


def _valid(model: type[BaseModel], response) -> dict:
    model.model_validate_json(response.text, strict=True)
    return response.json()


@pytest.fixture
def wired(pg_url):
    fake = make_fake()
    clock = lambda: datetime(2026, 10, 12, 23, 0, tzinfo=ZoneInfo("Europe/Madrid"))  # noqa: E731
    ingestion = create_app(Settings(database_url=pg_url, token=TOKEN, genesys_region="eu-west-1"),
                           client_factory=client_factory(fake), clock=clock, run_in_background=lambda job: job(),
                           scheduler=False)
    with TestClient(ingestion) as service:
        api_app.dependency_overrides[get_ingestion_client] = lambda: IngestionClient("http://testserver", TOKEN,
                                                                                     http=service)
        yield fake
    api_app.dependency_overrides.pop(get_ingestion_client, None)


def test_the_whole_chain_matches_the_documented_schemas(api, wired):
    flow = _valid(s.DownloadFlow, api.post("/api/download-flows", json=BODY))
    assert flow["timezone"] == "Europe/Madrid" and flow["next_run_at"]
    _valid(s.DownloadFlowList, api.get("/api/download-flows"))
    _valid(s.DownloadFlow, api.put(f"/api/download-flows/{flow['id']}", json={**BODY, "name": "Otra"}))
    run = _valid(s.DownloadRun, api.post(f"/api/download-flows/{flow['id']}/runs"))
    done = _valid(s.DownloadRun, api.get(f"/api/download-flows/{flow['id']}/runs/{run['id']}"))
    assert done["status"] == "completada_con_avisos" and done["counters"]["inserted"] == 10
    _valid(s.DownloadRunList, api.get(f"/api/download-flows/{flow['id']}/runs"))
    log = _valid(s.DownloadLog, api.get(f"/api/download-flows/{flow['id']}/runs/{run['id']}/log"))
    assert log["items"]
    text = api.get(f"/api/download-flows/{flow['id']}/runs/{run['id']}/log", params={"format": "text"})
    assert text.headers["content-type"].startswith("text/plain") and len(text.text.splitlines()) == len(log["items"])
    invalid = api.post("/api/download-flows", json={**BODY, "interval": {"type": "relativo", "unit": "horas"}})
    assert invalid.status_code == 422
    _valid(s.FieldErrors, invalid)
    assert api.post(f"/api/download-flows/{flow['id']}/runs").status_code == 202
    assert api.delete(f"/api/download-flows/{flow['id']}").status_code == 204


def test_the_connector_reports_counts_and_tests_the_credentials(api, wired):
    flow = api.post("/api/download-flows", json=BODY).json()
    api.post(f"/api/download-flows/{flow['id']}/runs")
    status = _valid(s.GenesysConnector, api.get("/api/config/connectors/genesys"))
    assert status["service"] == "disponible" and status["region"] == "eu-west-1"
    assert status["conversations"] == {"total": 10, "by_channel": {"voz": 4, "chat": 6},
                                       "by_quality": {"completa": 8, "parcial": 1, "sin_transcripcion": 1}}
    assert status["last_download"]["flow_id"] == flow["id"] and status["last_test"] is None
    tested = _valid(s.GenesysTest, api.post("/api/config/connectors/genesys/test"))
    assert tested["ok"] and tested["organization"] == "SGTO" and tested["region"] == "eu-west-1"
    assert api.get("/api/config/connectors/genesys").json()["last_test"]["ok"] is True


def test_wrong_credentials_are_reported_without_the_secret(api, pg_url):
    ingestion = create_app(Settings(database_url=pg_url, token=TOKEN, genesys_region="eu-west-1"),
                           client_factory=client_factory(make_fake(), secret="otro-secreto"),
                           run_in_background=lambda job: job(), scheduler=False)
    with TestClient(ingestion) as service:
        api_app.dependency_overrides[get_ingestion_client] = lambda: IngestionClient("http://testserver", TOKEN,
                                                                                     http=service)
        try:
            tested = _valid(s.GenesysTest, api.post("/api/config/connectors/genesys/test"))
        finally:
            api_app.dependency_overrides.pop(get_ingestion_client, None)
    assert tested["ok"] is False and tested["message"] == "Invalid Genesys credentials"
    assert "otro-secreto" not in str(tested) and SECRET not in str(tested)

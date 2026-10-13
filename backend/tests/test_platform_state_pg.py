"""Flujos de insights y configuración guardados en PostgreSQL a través del servicio de ingesta real (FE015).

Se reinician los dos procesos: la API (almacenes nuevos) y el servicio de ingesta (una aplicación nueva sobre la misma
base), como al parar y volver a levantar el entorno.
"""
import pytest
from fastapi.testclient import TestClient

from app.config.store import get_config, reset_config_store
from app.flows.store import reset_flow_store
from app.ingestion_client import IngestionClient
from app.state_backend import IngestionStateBackend
from ingestion.main import create_app
from ingestion.settings import Settings
from tests.test_flow_fields import BOTH_OUTPUT, BOTH_PROMPT, _flow

pytestmark = pytest.mark.pg
TOKEN = "token-interno-de-prueba"


class Platform:
    def __init__(self, pg_url):
        self.pg_url = pg_url
        self._service = None

    def start(self) -> TestClient:
        self.stop()
        self._service = TestClient(create_app(Settings(database_url=self.pg_url, token=TOKEN), scheduler=False))
        self._service.__enter__()  # aplica las migraciones
        backend = IngestionStateBackend(IngestionClient("http://testserver", TOKEN, http=self._service))
        reset_flow_store(backend)
        reset_config_store(backend)
        return self._service

    def stop(self):
        if self._service:
            self._service.__exit__(None, None, None)
            self._service = None


@pytest.fixture
def platform(api, pg_url):
    platform = Platform(pg_url)
    platform.start()
    yield platform
    platform.stop()
    reset_flow_store()
    reset_config_store()


def test_flows_and_the_data_origin_survive_restarting_both_processes(api, platform):
    # El origen primero: el estado de validación del flujo depende de él («Guardar en campos» solo con datos reales).
    assert api.put("/api/config/sources", json={"origin": "real"}).status_code == 200
    flow = api.post("/api/flows", json={"name": "Resumen diario"}).json()
    saved = api.put(f"/api/flows/{flow['id']}/graph", json=_flow(BOTH_PROMPT, BOTH_OUTPUT)).json()
    deleted = api.post("/api/flows", json={"name": "Se borra"}).json()
    assert api.delete(f"/api/flows/{deleted['id']}").status_code == 204

    platform.start()

    assert get_config().sources.origin == "real"
    assert [f["id"] for f in api.get("/api/flows").json()["items"]] == [flow["id"]]
    reloaded = api.get(f"/api/flows/{flow['id']}").json()
    assert {k: reloaded[k] for k in ("name", "graph", "author", "created_at", "updated_at", "status")} == \
        {k: saved[k] for k in ("name", "graph", "author", "created_at", "updated_at", "status")}


def test_the_service_only_accepts_well_formed_state(platform):
    service = platform.start()
    service.headers["Authorization"] = f"Bearer {TOKEN}"
    record = {"id": "1FL-00000000-0000-4000-8000-000000000001", "name": "Flujo", "graph": {"version": 1},
              "author": {"id": "1US-00000000-0000-4000-8000-000000000001", "name": "Ana"},
              "created_at": "2026-10-13T10:00:00+00:00", "updated_at": "2026-10-13T10:00:00+00:00"}

    assert service.put("/insight-flows/no-es-un-flujo", json={**record, "id": "no-es-un-flujo"}).status_code == 404
    other = "1FL-00000000-0000-4000-8000-000000000002"
    assert service.put(f"/insight-flows/{other}", json=record).status_code == 422
    assert service.put(f"/insight-flows/{record['id']}", json={**record, "extra": 1}).status_code == 422
    assert service.put("/settings/Clave-Rara", json={"value": {}}).status_code == 422
    assert service.put("/settings/sources", json={"value": "real"}).status_code == 422
    assert service.get("/settings").json() == {"items": {}}

    assert service.put(f"/insight-flows/{record['id']}", json=record).status_code == 200
    assert service.delete(f"/insight-flows/{record['id']}").status_code == 204
    assert service.delete(f"/insight-flows/{record['id']}").status_code == 204
    assert service.get("/insight-flows").json() == {"items": []}
    service.headers.pop("Authorization")
    assert service.get("/insight-flows").status_code == 401

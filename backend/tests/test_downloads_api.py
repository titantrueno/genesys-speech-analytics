"""Rutas de la API para los flujos de descarga y el conector de Genesys (FE011, T6; criterios 12, 20, 21 y 22).

La API comprueba la sesión y los permisos, añade la autoría y la zona horaria vigente y delega en el servicio de
ingesta (aquí, el doble en memoria de `tests/ingestion_stub.py`).
"""
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.ingestion_client import IngestionClient, get_ingestion_client
from app.main import app
from tests.ingestion_stub import ingestion_down, ingestion_stub  # noqa: F401 (fixtures)
from tests.roles import add_role

BODY = {"name": "Descarga diaria", "interval": {"type": "relativo", "unit": "hoy"}, "channels": ["voz", "chat"],
        "schedule": {"type": "desactivada"}, "active": True}


def _as(email: str) -> TestClient:
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {auth.create_token(auth.get_store().find_by_email(email))}"
    return client


def _with_role(api, permissions: set[str]) -> TestClient:
    add_role("rol_prueba", permissions)
    created = api.post("/api/users", json={"name": "Prueba", "email": "prueba@bancohorizonte.demo",
                                           "role": "rol_prueba"})
    assert created.status_code == 201, created.text
    return _as("prueba@bancohorizonte.demo")


def _flow(api) -> dict:
    response = api.post("/api/download-flows", json=BODY)
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_can_manage_and_run_download_flows(api, ingestion_stub):
    flow = _flow(api)
    assert api.get("/api/download-flows").json()["items"][0]["id"] == flow["id"]
    assert api.get(f"/api/download-flows/{flow['id']}").status_code == 200
    assert api.put(f"/api/download-flows/{flow['id']}", json={**BODY, "name": "Otra"}).json()["name"] == "Otra"
    run = api.post(f"/api/download-flows/{flow['id']}/runs")
    assert run.status_code == 202
    assert api.get(f"/api/download-flows/{flow['id']}/runs").json()["items"][0]["id"] == run.json()["id"]
    assert api.get(f"/api/download-flows/{flow['id']}/runs/{run.json()['id']}").status_code == 200
    assert api.get(f"/api/download-flows/{flow['id']}/runs/{run.json()['id']}/log").json()["items"]
    assert api.delete(f"/api/download-flows/{flow['id']}").status_code == 204


def test_the_api_sets_the_author_and_the_current_timezone(api, ingestion_stub):
    assert api.put("/api/config/general", json={"platform_name": "Speech & Text Analytics", "timezone": "UTC",
                                               "language": "es-ES"}).status_code == 200
    flow = api.post("/api/download-flows", json={**BODY, "timezone": "Asia/Tokyo",
                                                 "author": {"id": "1US-OTRA", "name": "Suplantación"}}).json()
    admin = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    _, _, sent = ingestion_stub.received[-1]
    assert sent["timezone"] == "UTC" and sent["author"] == {"id": admin.id, "name": admin.name}
    assert flow["author"]["id"] == admin.id
    api.put(f"/api/download-flows/{flow['id']}", json={**BODY, "author": {"id": "1US-OTRA", "name": "X"}})
    _, _, sent = ingestion_stub.received[-1]
    assert sent["timezone"] == "UTC" and "author" not in sent


def test_overwrite_reaches_the_service_when_creating_and_saving(api, ingestion_stub):
    # FE013, criterio 25: la casilla «Sobrescribir» no se pierde en el relevo de la API.
    flow = api.post("/api/download-flows", json={**BODY, "overwrite": True}).json()
    _, _, sent = ingestion_stub.received[-1]
    assert sent["overwrite"] is True and flow["overwrite"] is True
    api.put(f"/api/download-flows/{flow['id']}", json={**BODY, "overwrite": False})
    _, _, sent = ingestion_stub.received[-1]
    assert sent["overwrite"] is False


def test_the_person_who_launches_a_run_reaches_the_service(api, ingestion_stub):
    flow = _flow(api)
    run = api.post(f"/api/download-flows/{flow['id']}/runs").json()
    admin = auth.get_store().find_by_email("admin@bancohorizonte.demo")
    assert run["started_by"] == {"id": admin.id, "name": admin.name}


def test_validation_errors_come_back_per_field_without_the_input(api, ingestion_stub):
    response = api.post("/api/download-flows", json={**BODY, "name": " "})
    assert response.status_code == 422
    assert response.json() == {"detail": [{"loc": ["body", "name"], "msg": "El nombre no puede estar vacío",
                                           "type": "value_error"}]}


def test_not_found_and_conflict_are_relayed(api, ingestion_stub):
    assert api.get("/api/download-flows/1FL-00000000-0000-4000-8000-000000000000").status_code == 404
    flow = _flow(api)
    ingestion_stub.active = True
    response = api.post(f"/api/download-flows/{flow['id']}/runs")
    assert response.status_code == 409 and "en curso" in response.json()["detail"]


def test_the_log_downloads_as_text(api, ingestion_stub):
    flow = _flow(api)
    run = api.post(f"/api/download-flows/{flow['id']}/runs").json()
    response = api.get(f"/api/download-flows/{flow['id']}/runs/{run['id']}/log", params={"format": "text"})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"] == f'attachment; filename="log-{run["id"]}.txt"'
    assert "[aviso]" in response.text
    only_warnings = api.get(f"/api/download-flows/{flow['id']}/runs/{run['id']}/log", params={"level": "aviso"})
    assert {e["level"] for e in only_warnings.json()["items"]} == {"aviso"}


# Permisos --------------------------------------------------------------------------------------------------------------

def test_view_only_can_read_but_not_write(api, ingestion_stub):
    flow = _flow(api)
    run = api.post(f"/api/download-flows/{flow['id']}/runs").json()
    reader = _with_role(api, {"flows:view"})
    base = f"/api/download-flows/{flow['id']}"
    for path in ["/api/download-flows", base, f"{base}/runs", f"{base}/runs/{run['id']}", f"{base}/runs/{run['id']}/log"]:
        assert reader.get(path).status_code == 200, path
    assert reader.post("/api/download-flows", json=BODY).status_code == 403
    assert reader.put(base, json=BODY).status_code == 403
    assert reader.delete(base).status_code == 403
    assert reader.post(f"{base}/runs").status_code == 403
    assert len(ingestion_stub.flows) == 1 and len(ingestion_stub.runs) == 1  # nada llegó al servicio


def test_without_flow_permissions_nothing_is_visible(api, ingestion_stub):
    viewer = _as("viewer@bancohorizonte.demo")
    assert viewer.get("/api/download-flows").status_code == 403


def test_connector_status_needs_config_view_and_the_test_config_edit(api, ingestion_stub):
    supervisor, analyst = _as("supervisor@bancohorizonte.demo"), _as("analista@bancohorizonte.demo")
    status = supervisor.get("/api/config/connectors/genesys")
    assert status.status_code == 200 and status.json()["service"] == "disponible"
    assert status.json()["conversations"]["by_channel"] == {"voz": 7, "chat": 6}
    assert analyst.get("/api/config/connectors/genesys").status_code == 403
    assert supervisor.post("/api/config/connectors/genesys/test").status_code == 403
    tested = api.post("/api/config/connectors/genesys/test")
    assert tested.status_code == 200 and tested.json()["organization"] == "SGTO"


# Servicio de ingesta caído ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("method, path", [
    ("GET", "/api/download-flows"), ("POST", "/api/download-flows"),
    ("GET", "/api/download-flows/1FL-00000000-0000-4000-8000-000000000001"),
    ("POST", "/api/download-flows/1FL-00000000-0000-4000-8000-000000000001/runs"),
    ("POST", "/api/config/connectors/genesys/test"),
])
def test_an_unreachable_service_is_503_and_insight_flows_keep_working(api, ingestion_down, method, path):
    response = api.request(method, path, json=BODY if method == "POST" else None)
    assert response.status_code == 503
    assert response.json() == {"detail": "El servicio de ingesta no está disponible"}
    assert api.get("/api/flows").status_code == 200


def test_the_connector_status_reports_an_unreachable_service(api, ingestion_down):
    response = api.get("/api/config/connectors/genesys")
    assert response.status_code == 200
    assert response.json()["service"] == "no_disponible" and response.json()["conversations"] is None


def test_without_a_token_the_service_counts_as_unavailable(api):
    app.dependency_overrides[get_ingestion_client] = lambda: IngestionClient("http://localhost:1", None)
    try:
        assert api.get("/api/download-flows").status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_a_service_that_rejects_the_token_counts_as_unavailable(api, ingestion_stub):
    app.dependency_overrides[get_ingestion_client] = lambda: IngestionClient(
        "http://testserver", "otro-token", http=TestClient(ingestion_stub.app))
    assert api.get("/api/download-flows").status_code == 503

"""Flujos de insights y configuración que sobreviven a un reinicio de la API (FE015), con un almacén en memoria.

«Reiniciar» es crear almacenes nuevos sobre el mismo almacén persistente, como hace la API al arrancar.
"""
import copy

import pytest

from app.config import store as config_store
from app.config.store import get_config, reset_config_store
from app.flows.store import reset_flow_store
from app.state_backend import StateUnavailable
from tests.flow_fixtures import graph, node
from tests.test_flow_fields import BOTH_OUTPUT, BOTH_PROMPT, _flow


class MemoryBackend:
    """Doble del servicio de ingesta: guarda copias, como haría la base, y puede «caerse»."""

    def __init__(self):
        self.flows: dict[str, dict] = {}
        self.settings: dict[str, dict] = {}
        self.down = False
        self.loads = 0

    def _check(self):
        if self.down:
            raise StateUnavailable()

    def load_flows(self):
        self._check()
        return [copy.deepcopy(f) for f in self.flows.values()]

    def save_flow(self, record):
        self._check()
        self.flows[record["id"]] = copy.deepcopy(record)

    def delete_flow(self, flow_id):
        self._check()
        self.flows.pop(flow_id, None)

    def load_settings(self):
        self.loads += 1
        self._check()
        return copy.deepcopy(self.settings)

    def save_setting(self, key, value):
        self._check()
        self.settings[key] = copy.deepcopy(value)


@pytest.fixture
def backend(api):
    backend = MemoryBackend()
    reset_flow_store(backend)
    reset_config_store(backend)
    yield backend
    reset_flow_store()
    reset_config_store()


def restart(backend):
    reset_flow_store(backend)
    reset_config_store(backend)


def test_insight_flows_survive_a_restart_with_name_graph_and_author(api, backend):
    flow = api.post("/api/flows", json={"name": "Resumen diario"}).json()
    saved = api.put(f"/api/flows/{flow['id']}/graph", json=_flow(BOTH_PROMPT, BOTH_OUTPUT)).json()
    api.patch(f"/api/flows/{flow['id']}", json={"name": "Resumen semanal"})

    restart(backend)

    listed = api.get("/api/flows").json()["items"]
    assert [f["id"] for f in listed] == [flow["id"]]
    reloaded = api.get(f"/api/flows/{flow['id']}").json()
    assert reloaded["name"] == "Resumen semanal"
    assert reloaded["graph"] == saved["graph"]
    assert reloaded["author"] == flow["author"]
    assert reloaded["created_at"] == flow["created_at"]
    assert reloaded["status"] == saved["status"]


def test_duplicated_and_deleted_flows_are_kept_after_a_restart(api, backend):
    original = api.post("/api/flows", json={"name": "Original"}).json()
    copy_ = api.post(f"/api/flows/{original['id']}/duplicate").json()
    assert api.delete(f"/api/flows/{original['id']}").status_code == 204

    restart(backend)

    assert [f["id"] for f in api.get("/api/flows").json()["items"]] == [copy_["id"]]
    assert api.get(f"/api/flows/{original['id']}").status_code == 404


def test_a_change_that_cannot_be_saved_is_rejected_and_not_applied(api, backend):
    flow = api.post("/api/flows", json={"name": "Estable"}).json()
    backend.down = True

    assert api.patch(f"/api/flows/{flow['id']}", json={"name": "Perdido"}).status_code == 503
    assert api.put(f"/api/flows/{flow['id']}/graph", json=graph([node("tmp-s", "sampling", {})], [])).status_code == 503
    assert api.post("/api/flows", json={"name": "Nuevo"}).status_code == 503
    response = api.delete(f"/api/flows/{flow['id']}")
    assert response.status_code == 503
    assert response.json() == {"detail": "The ingestion service is not available"}

    backend.down = False
    current = api.get(f"/api/flows/{flow['id']}").json()
    assert current["name"] == "Estable" and current["graph"]["nodes"] == []
    assert [f["name"] for f in api.get("/api/flows").json()["items"]] == ["Estable"]


def test_flows_cannot_be_read_until_the_saved_ones_are_loaded(api, backend):
    api.post("/api/flows", json={"name": "Guardado"})
    backend.down = True
    restart(backend)

    # Sin la lista guardada, mostrar una vacía haría creer que se han perdido.
    assert api.get("/api/flows").status_code == 503

    backend.down = False
    assert [f["name"] for f in api.get("/api/flows").json()["items"]] == ["Guardado"]


def test_a_saved_flow_that_no_longer_fits_the_model_does_not_hide_the_others(api, backend):
    good = api.post("/api/flows", json={"name": "Bueno"}).json()
    broken = api.post("/api/flows", json={"name": "Roto"}).json()
    backend.flows[broken["id"]]["graph"] = {"version": 1, "nodes": [{"id": "x", "type": "desconocido"}]}

    restart(backend)

    assert [f["id"] for f in api.get("/api/flows").json()["items"]] == [good["id"]]


def test_the_data_origin_and_the_other_preferences_survive_a_restart(api, backend):
    assert api.put("/api/config/sources", json={"origin": "real"}).status_code == 200
    general = {"platform_name": "Analítica Horizonte", "timezone": "America/Bogota", "language": "es-ES"}
    assert api.put("/api/config/general", json=general).status_code == 200
    assert api.put("/api/config/privacy", json={"pii_masking": False}).status_code == 200

    restart(backend)

    config = get_config()
    assert config.sources.origin == "real"
    assert config.general.platform_name == "Analítica Horizonte"
    assert config.general.timezone == "America/Bogota"
    assert config.privacy.pii_masking is False
    assert backend.settings["sources"] == {"origin": "real"}


def test_a_preference_that_cannot_be_saved_is_rejected_and_not_audited(api, backend):
    backend.down = True
    response = api.put("/api/config/sources", json={"origin": "real"})
    assert response.status_code == 503

    backend.down = False
    assert get_config().sources.origin == "sintetico"
    assert all(e["section"] != "fuentes" for e in api.get("/api/config/audit").json()["items"])


def test_without_the_service_at_startup_the_defaults_are_used_and_loading_is_retried(api, backend, monkeypatch):
    backend.settings["sources"] = {"origin": "real"}
    backend.down = True
    clock = [100.0]
    monkeypatch.setattr(config_store.time, "monotonic", lambda: clock[0])
    restart(backend)

    assert get_config().sources.origin == "sintetico"
    attempts = backend.loads
    assert get_config().sources.origin == "sintetico"
    assert backend.loads == attempts  # no reintenta en cada lectura

    backend.down = False
    clock[0] += config_store.LOAD_RETRY_S
    assert get_config().sources.origin == "real"


def test_a_saved_section_that_is_no_longer_valid_is_ignored(api, backend):
    backend.settings["ai"] = {"provider": "proveedor-retirado", "model": "x"}
    backend.settings["sources"] = {"origin": "real"}
    default_ai = get_config().ai

    restart(backend)

    assert get_config().ai == default_ai
    assert get_config().sources.origin == "real"

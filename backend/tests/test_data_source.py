"""Origen de datos de la plataforma (FE012, criterio 1): valor por defecto, permisos, auditoría y propagación."""
from app.data.repository import SyntheticRepository, active_repository
from app.data.store import get_dataset
from tests.test_config_api import as_role, audit


def test_the_default_origin_is_synthetic(api):
    assert api.get("/api/config").json()["sources"] == {"origin": "sintetico"}
    assert isinstance(active_repository(), SyntheticRepository)


def test_switching_requires_config_edit(api):
    as_role(api, "supervisor")
    assert api.put("/api/config/sources", json={"origin": "real"}).status_code == 403
    assert api.get("/api/config").json()["sources"] == {"origin": "sintetico"}


def test_switching_is_audited_under_data_sources(api):
    response = api.put("/api/config/sources", json={"origin": "real"})
    assert response.status_code == 200
    assert response.json()["sources"] == {"origin": "real"}
    entry = audit(api, "fuentes")[0]
    assert (entry["before"], entry["after"]) == ({"origin": "sintetico"}, {"origin": "real"})
    assert entry["element"] == "Origen de datos"


def test_an_unknown_origin_is_rejected(api):
    response = api.put("/api/config/sources", json={"origin": "otro"})
    assert response.status_code == 422
    assert api.get("/api/config").json()["sources"] == {"origin": "sintetico"}


def test_the_same_origin_changes_and_audits_nothing(api):
    version = api.get("/api/config").json()["version"]
    assert api.put("/api/config/sources", json={"origin": "sintetico"}).json()["version"] == version
    assert audit(api, "fuentes") == []


def test_the_synthetic_origin_serves_the_generated_dataset(api):
    assert api.get("/api/conversations").json()["total"] <= len(get_dataset())
    assert len(active_repository().conversations()) == len(get_dataset())


def test_the_catalog_tells_the_active_origin(api):
    assert api.get("/api/catalog").json()["origin"] == "sintetico"

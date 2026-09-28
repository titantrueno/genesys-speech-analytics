"""Núcleo de configuración: lectura, permisos, validación por campo, auditoría y pestañas General, Fuentes de datos,
Privacidad y Modelos de IA (FE005, criterios 1–6, 10 y 11)."""
import pytest

from app import auth, ids
from app.data.store import get_dataset

GENERAL = {"platform_name": "Analítica Horizonte", "timezone": "America/Mexico_City", "language": "es-ES"}


def as_role(api, role: str):
    user = auth.get_store().find_by_email(f"{role}@bancohorizonte.demo")
    api.headers["Authorization"] = f"Bearer {auth.create_token(user)}"
    return api


def audit(api, section: str | None = None) -> list[dict]:
    response = api.get("/api/config/audit", params={"section": section} if section else None)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def field_errors(response) -> dict[str, str]:
    assert response.status_code == 422, response.text
    return {err["loc"][-1]: err["msg"] for err in response.json()["detail"]}


# --- Lectura y permisos ---

def test_config_returns_every_section_with_defaults(api):
    body = api.get("/api/config").json()
    assert body["general"] == {"platform_name": "Speech & Text Analytics", "timezone": "Europe/Madrid",
                               "language": "es-ES"}
    assert body["privacy"] == {"pii_masking": True}
    assert body["ai"] == {"provider": "simulado", "model": "mock-rapido", "simulated": True}
    assert isinstance(body["version"], int)
    assert {"languages", "providers", "timezones"} <= set(body["options"])
    assert "Europe/Madrid" in body["options"]["timezones"]


@pytest.mark.parametrize("role", ["admin", "supervisor"])
def test_admin_and_supervisor_can_read(api, role):
    as_role(api, role)
    assert api.get("/api/config").status_code == 200
    assert api.get("/api/config/connectors").status_code == 200
    assert api.get("/api/config/audit").status_code == 200


@pytest.mark.parametrize("role", ["analista", "viewer"])
def test_analyst_and_viewer_cannot_read(api, role):
    as_role(api, role)
    assert api.get("/api/config").status_code == 403
    assert api.get("/api/config/connectors").status_code == 403
    assert api.get("/api/config/audit").status_code == 403


def test_supervisor_gets_403_on_every_write_and_nothing_changes(api):
    connector = api.get("/api/config/connectors").json()["items"][0]
    before = api.get("/api/config").json()
    as_role(api, "supervisor")
    writes = [
        api.put("/api/config/general", json=GENERAL),
        api.put("/api/config/privacy", json={"pii_masking": False}),
        api.put("/api/config/ai", json={"provider": "simulado", "model": "mock-preciso"}),
        api.post(f"/api/config/connectors/{connector['id']}/sync"),
    ]
    assert [r.status_code for r in writes] == [403] * 4
    assert api.get("/api/config").json() == before
    assert audit(api) == []


def test_public_endpoint_only_exposes_name_timezone_and_language(api):
    """Sin sesión (login) y para todos los roles: la zona horaria y el nombre se aplican a toda la plataforma."""
    api.put("/api/config/general", json=GENERAL)
    api.headers.pop("Authorization")
    response = api.get("/api/config/public")
    assert response.status_code == 200
    assert response.json() == GENERAL


def test_new_prompt_nodes_take_the_default_model_from_the_flow_catalog(api):
    assert api.get("/api/flows/catalog").json()["default_model"] == "mock-rapido"
    api.put("/api/config/ai", json={"provider": "simulado", "model": "mock-preciso"})
    assert api.get("/api/flows/catalog").json()["default_model"] == "mock-preciso"


# --- General ---

def test_update_general_and_read_it_back(api):
    response = api.put("/api/config/general", json={**GENERAL, "platform_name": "  Analítica Horizonte  "})
    assert response.status_code == 200, response.text
    assert response.json()["general"] == GENERAL
    assert api.get("/api/config").json()["general"] == GENERAL


def test_every_change_increments_the_version(api):
    version = api.get("/api/config").json()["version"]
    api.put("/api/config/general", json=GENERAL)
    assert api.get("/api/config").json()["version"] == version + 1


@pytest.mark.parametrize("payload,field", [
    ({**GENERAL, "platform_name": "   "}, "platform_name"),
    ({**GENERAL, "platform_name": "x" * 61}, "platform_name"),
    ({**GENERAL, "timezone": "Europe/Atlantida"}, "timezone"),
    ({**GENERAL, "language": "en-US"}, "language"),
])
def test_invalid_general_returns_one_error_per_field(api, payload, field):
    errors = field_errors(api.put("/api/config/general", json=payload))
    assert field in errors and errors[field]


def test_all_invalid_fields_are_reported_together(api):
    errors = field_errors(api.put("/api/config/general",
                                  json={"platform_name": "", "timezone": "Nada/Nada", "language": "fr"}))
    assert set(errors) == {"platform_name", "timezone", "language"}


def test_unknown_fields_are_rejected(api):
    assert api.put("/api/config/general", json={**GENERAL, "tenant": "x"}).status_code == 422


# --- Privacidad y Modelos de IA ---

def test_update_privacy(api):
    response = api.put("/api/config/privacy", json={"pii_masking": False})
    assert response.status_code == 200, response.text
    assert api.get("/api/config").json()["privacy"] == {"pii_masking": False}


def test_update_ai_default_model(api):
    response = api.put("/api/config/ai", json={"provider": "simulado", "model": "mock-preciso"})
    assert response.status_code == 200, response.text
    assert api.get("/api/config").json()["ai"]["model"] == "mock-preciso"


@pytest.mark.parametrize("payload,field", [
    ({"provider": "openai", "model": "mock-rapido"}, "provider"),
    ({"provider": "simulado", "model": "gpt-5"}, "model"),
])
def test_invalid_ai_config_returns_field_error(api, payload, field):
    assert field in field_errors(api.put("/api/config/ai", json=payload))


def test_ai_models_match_the_flow_catalog(api):
    providers = api.get("/api/config").json()["options"]["providers"]
    flow_models = {m["value"] for m in api.get("/api/flows/catalog").json()["models"]}
    assert {m["value"] for p in providers for m in p["models"]} == flow_models


def test_ai_config_accepts_no_secrets(api):
    assert api.put("/api/config/ai", json={"provider": "simulado", "model": "mock-rapido",
                                           "api_key": "sk-xxx"}).status_code == 422


# --- Fuentes de datos ---

def test_connectors_show_status_last_sync_and_conversations_per_channel(api):
    items = api.get("/api/config/connectors").json()["items"]
    assert [c["name"] for c in items] == ["Genesys Cloud · voz transcrita", "Genesys Cloud · chat"]
    dataset = get_dataset()
    for connector in items:
        assert ids.is_valid(connector["id"], ids.CONNECTOR)
        assert connector["status"] == "conectado"
        assert connector["last_sync"]
        assert connector["conversations"] == sum(1 for c in dataset if c.channel == connector["channel"])


def test_sync_updates_the_date_without_changing_the_dataset(api):
    connector = api.get("/api/config/connectors").json()["items"][1]
    size = len(get_dataset())
    response = api.post(f"/api/config/connectors/{connector['id']}/sync")
    assert response.status_code == 200, response.text
    synced = response.json()
    assert synced["last_sync"] > connector["last_sync"]
    assert synced["conversations"] == connector["conversations"]
    assert len(get_dataset()) == size
    assert api.get("/api/config/connectors").json()["items"][1]["last_sync"] == synced["last_sync"]


@pytest.mark.parametrize("connector_id", [
    ids.stable_id(ids.CONNECTOR, "no-existe"),
    "basura",
    ids.stable_id(ids.FLOW, "genesys-chat"),
])
def test_unknown_malformed_or_foreign_connector_returns_404(api, connector_id):
    assert api.post(f"/api/config/connectors/{connector_id}/sync").status_code == 404


# --- Auditoría ---

def test_each_accepted_change_creates_an_audit_entry(api):
    api.put("/api/config/general", json=GENERAL)
    api.put("/api/config/privacy", json={"pii_masking": False})
    entries = audit(api)
    assert [e["section"] for e in entries] == ["privacidad", "general"]
    general = entries[1]
    assert ids.is_valid(general["id"], ids.AUDIT)
    assert general["user"] == {"id": ids.stable_id(ids.USER, "admin@bancohorizonte.demo"), "name": "Admin Demo"}
    assert general["at"]
    assert general["element"] == "General"
    assert general["before"]["platform_name"] == "Speech & Text Analytics"
    assert general["after"] == GENERAL
    assert entries[0]["before"] == {"pii_masking": True}
    assert entries[0]["after"] == {"pii_masking": False}


def test_audit_can_be_filtered_by_section(api):
    api.put("/api/config/general", json=GENERAL)
    api.put("/api/config/privacy", json={"pii_masking": False})
    assert [e["section"] for e in audit(api, "general")] == ["general"]
    assert api.get("/api/config/audit", params={"section": "inventada"}).status_code == 422


def test_sync_is_audited_under_data_sources(api):
    connector = api.get("/api/config/connectors").json()["items"][0]
    api.post(f"/api/config/connectors/{connector['id']}/sync")
    entry = audit(api, "fuentes")[0]
    assert entry["element"] == connector["name"]
    assert entry["before"] == {"last_sync": connector["last_sync"]}


def test_rejected_or_unchanged_writes_create_no_entry(api):
    field_errors(api.put("/api/config/general", json={**GENERAL, "timezone": "Nada/Nada"}))
    api.put("/api/config/privacy", json={"pii_masking": True})  # mismo valor: no es un cambio
    assert audit(api) == []


def test_state_is_reset_between_tests(api):
    assert api.get("/api/config").json()["general"]["platform_name"] == "Speech & Text Analytics"
    assert audit(api) == []

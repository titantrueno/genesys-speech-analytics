import base64
import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import auth, ids
from app.main import app

PUBLIC_ROUTES = {"/api/health", "/api/auth/login"}
AUTH_ONLY_ROUTES = {"/api/auth/me"}
DEMO_USERS = {
    "admin": "admin@bancohorizonte.demo",
    "supervisor": "supervisor@bancohorizonte.demo",
    "analista": "analista@bancohorizonte.demo",
    "viewer": "viewer@bancohorizonte.demo",
}
ALL_PERMISSIONS = {
    "dashboards:view", "conversations:view", "explorer:use", "search:use",
    "flows:view", "flows:edit", "config:view", "config:edit", "users:admin",
}
EXPECTED_MATRIX = {
    "admin": ALL_PERMISSIONS,
    "supervisor": ALL_PERMISSIONS - {"config:edit", "users:admin"},
    "analista": {"dashboards:view", "conversations:view", "explorer:use", "search:use", "flows:view", "flows:edit"},
    "viewer": {"dashboards:view", "conversations:view"},
}


@pytest.fixture
def client():
    auth.reset_store()
    return TestClient(app)


def login(client, role):
    response = client.post("/api/auth/login", json={"email": DEMO_USERS[role], "password": auth.DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_with_valid_credentials_returns_token_and_user(client):
    response = client.post("/api/auth/login", json={"email": DEMO_USERS["analista"], "password": auth.DEMO_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["role"] == "analista"
    assert ids.is_valid(body["user"]["id"], ids.USER)
    assert body["user"]["id"] == ids.stable_id(ids.USER, DEMO_USERS["analista"])
    assert set(body["user"]["permissions"]) == EXPECTED_MATRIX["analista"]


@pytest.mark.parametrize("email,password", [
    ("admin@bancohorizonte.demo", "incorrecta"),
    ("nadie@bancohorizonte.demo", "demo"),
    ("", ""),
])
def test_login_with_invalid_credentials_returns_401(client, email, password):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401


def test_me_returns_current_user_with_permissions(client):
    response = client.get("/api/auth/me", headers=bearer(login(client, "viewer")))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == DEMO_USERS["viewer"]
    assert set(body["permissions"]) == EXPECTED_MATRIX["viewer"]


def test_me_without_token_returns_401(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_tampered_token_returns_401(client):
    token = login(client, "viewer")
    payload_b64, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    payload["role"] = "admin"
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert client.get("/api/auth/me", headers=bearer(f"{forged}.{signature}")).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(token[:-2] + "xx")).status_code == 401
    assert client.get("/api/auth/me", headers=bearer("basura")).status_code == 401


def test_expired_token_returns_401(client):
    user = auth.get_store().find_by_email(DEMO_USERS["admin"])
    expired = auth.create_token(user, ttl_seconds=-1)
    assert client.get("/api/auth/me", headers=bearer(expired)).status_code == 401


def test_inactive_user_cannot_login_nor_use_previous_token(client):
    token = login(client, "analista")
    auth.get_store().find_by_email(DEMO_USERS["analista"]).active = False
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401
    response = client.post("/api/auth/login", json={"email": DEMO_USERS["analista"], "password": auth.DEMO_PASSWORD})
    assert response.status_code == 401


def test_role_permission_matrix_matches_spec():
    assert set(auth.ALL_PERMISSIONS) == ALL_PERMISSIONS
    auth.reset_store()
    for role, expected in EXPECTED_MATRIX.items():
        assert auth.get_store().permissions_for(role) == expected


@pytest.mark.parametrize("role", list(EXPECTED_MATRIX))
def test_require_permission_enforces_matrix(role):
    auth.reset_store()
    probe = FastAPI()
    for permission in sorted(ALL_PERMISSIONS):
        probe.add_api_route(f"/probe/{permission}", lambda: {"ok": True},
                            dependencies=[Depends(auth.require_permission(permission))])
    probe_client = TestClient(probe)
    token = login(TestClient(app), role)
    for permission in ALL_PERMISSIONS:
        status = probe_client.get(f"/probe/{permission}", headers=bearer(token)).status_code
        assert status == (200 if permission in EXPECTED_MATRIX[role] else 403), (role, permission)


def _api_operations():
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api"):
            for method in operations:
                yield method.upper(), path, path.replace("{", "").replace("}", "")


def test_every_non_public_api_route_requires_auth(client):
    protected = [op for op in _api_operations() if op[1] not in PUBLIC_ROUTES]
    assert protected, "debe existir al menos una ruta protegida"
    for method, path, url in protected:
        response = client.request(method, url)
        assert response.status_code == 401, (method, path, response.status_code)


def test_every_data_route_requires_a_permission(client):
    store = auth.get_store()
    store.roles["sin_permisos"] = set()
    store.users["u-sin-permisos"] = auth.User("u-sin-permisos", "Sin permisos", "sin@bancohorizonte.demo", "sin_permisos")
    token = auth.create_token(store.users["u-sin-permisos"])
    for method, path, url in _api_operations():
        if path in PUBLIC_ROUTES | AUTH_ONLY_ROUTES:
            continue
        response = client.request(method, url, headers=bearer(token))
        assert response.status_code == 403, (method, path, response.status_code)

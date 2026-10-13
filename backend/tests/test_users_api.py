"""FE006 T2: API de usuarios, roles, matriz de permisos y auditoría."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import auth, ids
from app.main import app

ADMIN = "admin@bancohorizonte.demo"
ANALISTA = "analista@bancohorizonte.demo"
SUPERVISOR = "supervisor@bancohorizonte.demo"
NEW_USER = {"name": "Lucía Pérez", "email": "lucia.perez@bancohorizonte.demo", "role": "analista"}


def user_id(email):
    return auth.get_store().find_by_email(email).id


def role_id(code):
    return ids.stable_id(ids.ROLE, code)


def login(email):
    return TestClient(app).post("/api/auth/login", json={"email": email, "password": auth.DEMO_PASSWORD})


def bearer(email):
    return {"Authorization": f"Bearer {login(email).json()['access_token']}"}


def users(api, **params):
    response = api.get("/api/users", params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def roles(api):
    response = api.get("/api/roles")
    assert response.status_code == 200, response.text
    return {r["code"]: r for r in response.json()["items"]}


def body_of(user, **changes):
    return {"name": user["name"], "email": user["email"], "role": user["role"], "active": user["active"], **changes}


def get_user(api, email):
    return next(u for u in users(api) if u["email"] == email)


def field(response):
    return [(tuple(e["loc"]), e["msg"]) for e in response.json()["detail"]]


def audit(api):
    return api.get("/api/users/audit").json()["items"]


# --- Usuarios ---

def test_list_has_name_email_role_status_and_last_access(api):
    items = users(api)
    assert {u["email"] for u in items} == {ADMIN, SUPERVISOR, ANALISTA, "viewer@bancohorizonte.demo"}
    analista = next(u for u in items if u["email"] == ANALISTA)
    assert analista == {"id": user_id(ANALISTA), "name": "Analista Demo", "email": ANALISTA, "role": "analista",
                        "role_name": "Analista", "active": True, "last_login": None}


def test_login_records_last_access(api):
    assert login(ANALISTA).status_code == 200
    last = get_user(api, ANALISTA)["last_login"]
    assert last is not None and datetime.fromisoformat(last).tzinfo is not None


@pytest.mark.parametrize("q,expected", [
    ("analista", {ANALISTA}),
    ("SUPERVISORA", {SUPERVISOR}),
    ("viewer@banco", {"viewer@bancohorizonte.demo"}),
    ("nadie", set()),
])
def test_search_by_name_or_email_ignoring_case(api, q, expected):
    assert {u["email"] for u in users(api, q=q)} == expected


def test_search_ignores_accents(api):
    api.post("/api/users", json=NEW_USER)
    assert [u["email"] for u in users(api, q="lucia perez")] == [NEW_USER["email"]]


def test_filter_by_role_and_status(api):
    analista = get_user(api, ANALISTA)
    api.put(f"/api/users/{analista['id']}", json=body_of(analista, active=False))
    assert [u["email"] for u in users(api, role="analista")] == [ANALISTA]
    assert [u["email"] for u in users(api, active="false")] == [ANALISTA]
    assert ANALISTA not in {u["email"] for u in users(api, active="true")}
    assert users(api, role="analista", active="true") == []
    assert api.get("/api/users", params={"role": "inventado"}).json()["items"] == []


def test_create_user(api):
    response = api.post("/api/users", json=NEW_USER)
    assert response.status_code == 201, response.text
    created = response.json()
    assert ids.is_valid(created["id"], ids.USER)
    assert {k: created[k] for k in NEW_USER} == NEW_USER
    assert created["active"] is True and created["last_login"] is None
    assert login(NEW_USER["email"]).status_code == 200


@pytest.mark.parametrize("email", [ADMIN, ADMIN.upper(), f"  {ADMIN}  "])
def test_duplicate_email_returns_409_on_the_email_field(api, email):
    response = api.post("/api/users", json={**NEW_USER, "email": email})
    assert response.status_code == 409
    assert field(response) == [(("body", "email"), "A user with that email already exists")]


def test_duplicate_email_when_editing_returns_409(api):
    analista = get_user(api, ANALISTA)
    response = api.put(f"/api/users/{analista['id']}", json=body_of(analista, email=SUPERVISOR))
    assert response.status_code == 409
    assert field(response)[0][0] == ("body", "email")
    assert get_user(api, ANALISTA)["email"] == ANALISTA


@pytest.mark.parametrize("payload,loc", [
    ({**NEW_USER, "name": " "}, "name"),
    ({**NEW_USER, "name": "x" * 81}, "name"),
    ({**NEW_USER, "email": "no-es-un-email"}, "email"),
    ({**NEW_USER, "role": "inventado"}, "role"),
    ({k: v for k, v in NEW_USER.items() if k != "role"}, "role"),
    ({**NEW_USER, "extra": 1}, "extra"),
])
def test_invalid_user_returns_422_per_field(api, payload, loc):
    response = api.post("/api/users", json=payload)
    assert response.status_code == 422
    assert ("body", loc) in [l for l, _ in field(response)]


def test_email_is_stored_trimmed_and_lowercase(api):
    created = api.post("/api/users", json={**NEW_USER, "email": " Lucia.Perez@BancoHorizonte.demo "}).json()
    assert created["email"] == NEW_USER["email"]


def test_edit_user(api):
    analista = get_user(api, ANALISTA)
    response = api.put(f"/api/users/{analista['id']}", json=body_of(analista, name="Ana Lista", role="viewer"))
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["role"], response.json()["role_name"]) == ("Ana Lista", "viewer",
                                                                                                "Consulta")


def test_unknown_user_returns_404(api):
    unknown = ids.stable_id(ids.USER, "nadie")
    assert api.put(f"/api/users/{unknown}", json={**NEW_USER, "active": True}).status_code == 404
    assert api.put(f"/api/users/{role_id('admin')}", json={**NEW_USER, "active": True}).status_code == 404


def test_deactivated_user_cannot_log_in_and_its_token_stops_working(api):
    headers = bearer(ANALISTA)
    analista = get_user(api, ANALISTA)
    assert api.put(f"/api/users/{analista['id']}", json=body_of(analista, active=False)).status_code == 200
    assert login(ANALISTA).status_code == 401
    assert TestClient(app).get("/api/auth/me", headers=headers).status_code == 401
    assert api.put(f"/api/users/{analista['id']}", json=body_of(analista, active=True)).status_code == 200
    assert login(ANALISTA).status_code == 200


def test_admin_cannot_deactivate_or_demote_self_through_the_api(api):
    admin = get_user(api, ADMIN)
    for changes in ({"active": False}, {"role": "supervisor"}):
        response = api.put(f"/api/users/{admin['id']}", json=body_of(admin, **changes))
        assert response.status_code == 409
        assert "your own" in response.json()["detail"]
    assert get_user(api, ADMIN) == admin
    assert audit(api) == []


def test_last_active_admin_is_protected_through_the_api(api):
    """Otra persona con `users:admin` en un rol personalizado no puede dejar la plataforma sin ningún `admin`."""
    api.post("/api/roles", json={"code": "superadmin", "name": "Superadmin", "permissions": auth.ALL_PERMISSIONS})
    api.post("/api/users", json={"name": "Otra", "email": "otra@bancohorizonte.demo", "role": "superadmin"})
    other = TestClient(app, headers=bearer("otra@bancohorizonte.demo"))
    admin = get_user(api, ADMIN)
    for changes in ({"active": False}, {"role": "viewer"}):
        response = other.put(f"/api/users/{admin['id']}", json=body_of(admin, **changes))
        assert response.status_code == 409
        assert "last active administrator" in response.json()["detail"]


# --- Roles y permisos ---

def test_roles_list_with_user_count_and_permission_catalog(api):
    response = api.get("/api/roles").json()
    assert [p["value"] for p in response["permissions"]] == auth.ALL_PERMISSIONS
    assert response["permissions"][-1] == {"value": "users:admin", "label": "Administrar usuarios y roles"}
    items = {r["code"]: r for r in response["items"]}
    assert list(items) == ["admin", "supervisor", "analista", "viewer"]
    assert items["viewer"] == {"id": role_id("viewer"), "code": "viewer", "name": "Consulta", "builtin": True,
                               "permissions": ["dashboards:view", "conversations:view"], "users": 1}
    api.post("/api/users", json=NEW_USER)
    assert roles(api)["analista"]["users"] == 2


def test_base_roles_cannot_be_deleted(api):
    for code in ("admin", "supervisor", "analista", "viewer"):
        response = api.delete(f"/api/roles/{role_id(code)}")
        assert response.status_code == 409, code
        assert "built-in" in response.json()["detail"]
    assert list(roles(api)) == ["admin", "supervisor", "analista", "viewer"]


def test_create_custom_role_assign_it_and_delete_it_once_unused(api):
    response = api.post("/api/roles", json={"code": "lector_flujos", "name": "Lector de flujos",
                                            "permissions": ["flows:view"]})
    assert response.status_code == 201, response.text
    role = response.json()
    assert role == {"id": role_id("lector_flujos"), "code": "lector_flujos", "name": "Lector de flujos",
                    "builtin": False, "permissions": ["flows:view"], "users": 0}
    created = api.post("/api/users", json={**NEW_USER, "role": "lector_flujos"}).json()
    lector = TestClient(app, headers=bearer(NEW_USER["email"]))
    assert lector.get("/api/flows").status_code == 200
    assert lector.get("/api/conversations").status_code == 403
    assert lector.get("/api/auth/me").json()["role_name"] == "Lector de flujos"

    in_use = api.delete(f"/api/roles/{role['id']}")
    assert in_use.status_code == 409 and "assigned users" in in_use.json()["detail"]
    api.put(f"/api/users/{created['id']}", json=body_of(created, role="viewer"))
    assert api.delete(f"/api/roles/{role['id']}").status_code == 204
    assert "lector_flujos" not in roles(api)


@pytest.mark.parametrize("payload,loc,status", [
    ({"code": "admin", "name": "Otro", "permissions": []}, "code", 409),
    ({"code": "nuevo", "name": "administrador", "permissions": []}, "name", 409),
    ({"code": "Con Espacios", "name": "X", "permissions": []}, "code", 422),
    ({"code": "nuevo", "name": "", "permissions": []}, "name", 422),
    ({"code": "nuevo", "name": "X", "permissions": ["inventado"]}, "permissions", 422),
])
def test_invalid_role_returns_error_per_field(api, payload, loc, status):
    response = api.post("/api/roles", json=payload)
    assert response.status_code == status
    assert any(l[:2] == ("body", loc) for l, _ in field(response))


def test_base_role_name_cannot_change(api):
    response = api.put(f"/api/roles/{role_id('viewer')}", json={"name": "Lectores", "permissions": ["dashboards:view"]})
    assert response.status_code == 422
    assert field(response)[0][0] == ("body", "name")


def test_custom_role_can_be_renamed(api):
    api.post("/api/roles", json={"code": "auditor", "name": "Auditor", "permissions": []})
    response = api.put(f"/api/roles/{role_id('auditor')}", json={"name": "Auditoría", "permissions": ["config:view"]})
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["permissions"]) == ("Auditoría", ["config:view"])


def test_permissions_are_returned_in_catalog_order_without_duplicates(api):
    response = api.put(f"/api/roles/{role_id('viewer')}",
                       json={"name": "Consulta", "permissions": ["search:use", "dashboards:view", "search:use"]})
    assert response.json()["permissions"] == ["dashboards:view", "search:use"]


def test_admin_cannot_remove_own_admin_permission_through_the_matrix(api):
    without = [p for p in auth.ALL_PERMISSIONS if p != "users:admin"]
    response = api.put(f"/api/roles/{role_id('admin')}", json={"name": "Administrador", "permissions": without})
    assert response.status_code == 409
    assert roles(api)["admin"]["permissions"] == auth.ALL_PERMISSIONS


def test_removing_a_permission_takes_effect_on_the_next_request_with_the_same_token(api):
    """Criterio 6, de extremo a extremo: menú (`/me`) y acciones (`403`) sin volver a iniciar sesión."""
    analista = TestClient(app, headers=bearer(ANALISTA))
    first = analista.get("/api/search/semantic", params={"q": "tarjeta"})
    assert first.status_code == 200
    version = first.headers["x-auth-version"]

    permissions = [p for p in roles(api)["analista"]["permissions"] if p != "search:use"]
    assert api.put(f"/api/roles/{role_id('analista')}", json={"name": "Analista", "permissions": permissions}).status_code == 200

    me = analista.get("/api/auth/me")
    assert "search:use" not in me.json()["permissions"]
    assert me.headers["x-auth-version"] != version
    assert analista.get("/api/search/semantic", params={"q": "tarjeta"}).status_code == 403
    assert analista.get("/api/conversations").status_code == 200


def test_auth_version_header_is_exposed_to_the_browser(api):
    response = api.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert "x-auth-version" in response.headers
    assert "x-auth-version" in response.headers["access-control-expose-headers"].lower()


def test_auth_version_does_not_change_without_user_or_role_changes(api):
    before = api.get("/api/health").headers["x-auth-version"]
    login(ANALISTA)
    api.put("/api/config/privacy", json={"pii_masking": False})
    assert api.get("/api/health").headers["x-auth-version"] == before


# --- Acceso y auditoría ---

def test_only_users_admin_can_use_the_section(api):
    supervisor = TestClient(app, headers=bearer(SUPERVISOR))
    some_user, some_role = user_id(ANALISTA), role_id("viewer")
    for method, url in [("GET", "/api/users"), ("POST", "/api/users"), ("PUT", f"/api/users/{some_user}"),
                        ("GET", "/api/roles"), ("POST", "/api/roles"), ("PUT", f"/api/roles/{some_role}"),
                        ("DELETE", f"/api/roles/{some_role}"), ("GET", "/api/users/audit")]:
        assert supervisor.request(method, url, json={}).status_code == 403, (method, url)


def test_each_user_and_role_change_is_audited(api):
    created = api.post("/api/users", json=NEW_USER).json()
    api.put(f"/api/users/{created['id']}", json=body_of(created, role="viewer"))
    api.put(f"/api/users/{created['id']}", json=body_of(created, role="viewer", active=False))
    api.post("/api/roles", json={"code": "auditor", "name": "Auditor", "permissions": ["config:view"]})
    api.put(f"/api/roles/{role_id('auditor')}", json={"name": "Auditor", "permissions": []})
    api.delete(f"/api/roles/{role_id('auditor')}")

    entries = list(reversed(audit(api)))
    assert [e["element"] for e in entries] == ["User “Lucía Pérez”"] * 3 + ["Role “Auditor”"] * 3
    assert all(e["section"] == "usuarios" and e["user"]["name"] == "Admin Demo" for e in entries)
    assert entries[0]["before"] is None and entries[0]["after"]["email"] == NEW_USER["email"]
    assert (entries[1]["before"]["role"], entries[1]["after"]["role"]) == ("analista", "viewer")
    assert (entries[2]["before"]["active"], entries[2]["after"]["active"]) == (True, False)
    assert (entries[4]["before"]["permissions"], entries[4]["after"]["permissions"]) == (["config:view"], [])
    assert entries[5]["after"] is None


def test_rejected_or_empty_changes_are_not_audited(api):
    analista = get_user(api, ANALISTA)
    api.put(f"/api/users/{analista['id']}", json=body_of(analista))
    api.post("/api/users", json={**NEW_USER, "email": ADMIN})
    api.delete(f"/api/roles/{role_id('viewer')}")
    assert audit(api) == []


def test_user_changes_stay_out_of_the_config_audit(api):
    api.post("/api/users", json=NEW_USER)
    assert api.get("/api/config/audit").json()["items"] == []


def test_concurrent_creations_with_the_same_email_create_only_one_user(api, monkeypatch):
    """La comprobación del email y el alta van bajo el mismo cerrojo: una ventana lenta no deja pasar dos altas."""
    import threading
    import time

    from app.routers import users as users_router

    original = users_router._validated_user

    def slow(*args):
        original(*args)
        time.sleep(0.05)

    monkeypatch.setattr(users_router, "_validated_user", slow)
    statuses = []
    threads = [threading.Thread(target=lambda: statuses.append(api.post("/api/users", json=NEW_USER).status_code))
               for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(statuses) == [201, 409, 409, 409]
    assert [u["email"] for u in users(api, q=NEW_USER["email"])] == [NEW_USER["email"]]


def test_auth_version_is_only_sent_to_requests_with_a_session():
    anonymous = TestClient(app)
    assert "x-auth-version" not in anonymous.get("/api/health").headers
    assert "x-auth-version" not in login(ANALISTA).headers


def test_last_access_is_recorded_on_the_current_user_even_if_it_was_replaced_meanwhile(api):
    """`authenticate` devuelve un objeto que otra escritura puede sustituir antes de anotar el acceso."""
    store = auth.get_store()
    stale = store.find_by_email(ANALISTA)
    analista = get_user(api, ANALISTA)
    api.put(f"/api/users/{analista['id']}", json=body_of(analista, name="Ana Lista"))
    store.touch_login(stale)
    assert get_user(api, ANALISTA)["last_login"] is not None

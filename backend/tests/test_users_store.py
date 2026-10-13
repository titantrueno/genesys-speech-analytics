"""FE006 T1: roles como entidades, escritura única con protecciones y auditoría compartida con FE005."""
from dataclasses import replace

import pytest

from app import auth, ids
from app.audit import get_audit_log, reset_audit_log

ADMIN = "admin@bancohorizonte.demo"
ANALISTA = "analista@bancohorizonte.demo"


@pytest.fixture
def store():
    auth.reset_store()
    reset_audit_log()
    return auth.get_store()


def user(store, email):
    return store.find_by_email(email)


def set_user(store, actor, target, **changes):
    def change(users, roles):
        old = users[target.id]
        new = replace(old, **changes)
        return old.audit_value(), new.audit_value(), {**users, new.id: new}, roles
    store.apply(actor, f"User “{target.name}”", change)


def set_permissions(store, actor, code, permissions):
    def change(users, roles):
        old = roles[code]
        new = replace(old, permissions=frozenset(permissions))
        return old.audit_value(), new.audit_value(), users, {**roles, code: new}
    store.apply(actor, f"Role “{roles_name(store, code)}”", change)


def roles_name(store, code):
    return store.roles[code].name


def test_base_roles_are_stable_entities_with_the_adr_003_matrix(store):
    assert list(store.roles) == ["admin", "supervisor", "analista", "viewer"]
    for code, role in store.roles.items():
        assert role.builtin
        assert role.code == code
        assert ids.is_valid(role.id, ids.ROLE)
        assert role.id == ids.stable_id(ids.ROLE, code)
        assert role.permissions == frozenset(auth.DEFAULT_ROLES[code])
    assert [r.name for r in store.roles.values()] == ["Administrador", "Supervisor", "Analista", "Consulta"]
    assert all(u.last_login is None for u in store.users.values())


def test_accepted_change_is_applied_versioned_and_audited(store):
    admin, analista = user(store, ADMIN), user(store, ANALISTA)
    set_user(store, admin, analista, role="viewer")
    assert user(store, ANALISTA).role == "viewer"
    assert store.version == 1
    [entry] = get_audit_log().entries({"usuarios"})
    assert (entry.user_id, entry.user_name, entry.section) == (admin.id, admin.name, "usuarios")
    assert entry.element == "User “Analista Demo”"
    assert entry.before["role"] == "analista" and entry.after["role"] == "viewer"
    assert ids.is_valid(entry.id, ids.AUDIT)


def test_change_without_effect_is_neither_versioned_nor_audited(store):
    admin, analista = user(store, ADMIN), user(store, ANALISTA)
    set_user(store, admin, analista, role="analista")
    assert store.version == 0
    assert get_audit_log().entries() == []


def assert_rejected(store, action, message):
    snapshot = (dict(store.users), dict(store.roles), store.version)
    with pytest.raises(auth.ProtectionError, match=message):
        action()
    assert (dict(store.users), dict(store.roles), store.version) == snapshot
    assert get_audit_log().entries() == []


def test_admin_cannot_remove_own_admin_permission_through_own_role(store):
    admin = user(store, ADMIN)
    assert_rejected(store, lambda: set_permissions(store, admin, "admin", set(auth.ALL_PERMISSIONS) - {"users:admin"}),
                    "your own")


def test_admin_cannot_move_self_to_a_role_without_admin_permission(store):
    admin = user(store, ADMIN)
    assert_rejected(store, lambda: set_user(store, admin, admin, role="supervisor"), "your own")


def test_admin_cannot_deactivate_self(store):
    admin = user(store, ADMIN)
    assert_rejected(store, lambda: set_user(store, admin, admin, active=False), "your own")


def _second_admin_in_custom_role(store):
    """Otro administrador con un rol personalizado que también tiene `users:admin`."""
    role = auth.Role(ids.stable_id(ids.ROLE, "superadmin"), "superadmin", "Superadmin", frozenset(auth.ALL_PERMISSIONS))
    other = auth.User(ids.stable_id(ids.USER, "otra@bancohorizonte.demo"), "Otra Admin", "otra@bancohorizonte.demo",
                      "superadmin")
    store.roles["superadmin"] = role
    store.users[other.id] = other
    return other


def test_last_active_admin_cannot_be_deactivated_or_demoted(store):
    other = _second_admin_in_custom_role(store)
    admin = user(store, ADMIN)
    assert_rejected(store, lambda: set_user(store, other, admin, active=False), "last active administrator")
    assert_rejected(store, lambda: set_user(store, other, admin, role="viewer"), "last active administrator")


def test_admin_role_keeps_admin_permission(store):
    other = _second_admin_in_custom_role(store)
    assert_rejected(store, lambda: set_permissions(store, other, "admin", {"dashboards:view"}), "administrator")


def test_an_admin_can_be_deactivated_while_another_admin_remains(store):
    admin = user(store, ADMIN)
    second = auth.User(ids.stable_id(ids.USER, "dos@bancohorizonte.demo"), "Dos", "dos@bancohorizonte.demo", "admin")
    store.users[second.id] = second
    set_user(store, admin, second, active=False)
    assert not store.get(second.id).active


def test_config_changes_keep_auditing_in_the_shared_log(api):
    store = auth.get_store()
    assert api.put("/api/config/privacy", json={"pii_masking": False}).status_code == 200
    set_user(store, user(store, ADMIN), user(store, ANALISTA), role="viewer")
    sections = [e.section for e in get_audit_log().entries()]
    assert sections == ["usuarios", "privacidad"]
    config_audit = api.get("/api/config/audit").json()["items"]
    assert [e["section"] for e in config_audit] == ["privacidad"]

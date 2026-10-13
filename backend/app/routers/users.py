"""API de usuarios, roles y permisos (FE006). Todas las rutas exigen `users:admin`."""
import random
from dataclasses import replace
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app import auth, ids
from app.audit import get_audit_log
from app.auth import ALL_PERMISSIONS, PERMISSION_LABELS, Role, User, require_permission, sorted_permissions
from app.config.model import parse_body
from app.text import normalize_text

ADMIN = require_permission("users:admin")

router = APIRouter(prefix="/api", tags=["users"])

_rng = random.SystemRandom()

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class UserIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=254,
                                            pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    role: str
    active: bool = True


class RoleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    permissions: list[str]

    @field_validator("permissions")
    @classmethod
    def _known_permissions(cls, value: list[str]) -> list[str]:
        unknown = [p for p in value if p not in ALL_PERMISSIONS]
        if unknown:
            raise ValueError(f"Unknown permission: {', '.join(unknown)}")
        return value


class NewRoleIn(RoleIn):
    code: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]


def _field_error(code: int, field: str, message: str) -> HTTPException:
    return HTTPException(code, detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}])


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=message)


def _apply(actor: User, element: str, change: auth.UserChange) -> None:
    try:
        auth.get_store().apply(actor, element, change)
    except auth.ProtectionError as exc:
        raise _conflict(str(exc)) from None


def _user_body(user: User) -> dict:
    role = auth.get_store().roles.get(user.role)
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "role_name": role.name if role else user.role, "active": user.active,
            "last_login": user.last_login.isoformat() if user.last_login else None}


def _role_body(role: Role) -> dict:
    users = sum(1 for u in auth.get_store().users.values() if u.role == role.code)
    return {"id": role.id, "code": role.code, "name": role.name, "builtin": role.builtin,
            "permissions": sorted_permissions(role.permissions), "users": users}


def _validated_user(data: UserIn, user_id: str, users: auth.Users, roles: auth.Roles) -> None:
    if data.role not in roles:
        raise _field_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "role", "Unknown role")
    if any(u.email.lower() == data.email and u.id != user_id for u in users.values()):
        raise _field_error(status.HTTP_409_CONFLICT, "email", "A user with that email already exists")


def _find_user(user_id: str) -> User:
    user = auth.get_store().get(ids.normalize(user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _find_role(role_id: str) -> Role:
    role = next((r for r in auth.get_store().roles.values() if r.id == ids.normalize(role_id)), None)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


def _gone(label: str) -> HTTPException:
    """Existía al buscarlo, pero otra persona lo ha borrado antes de escribir."""
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{label} not found")


# --- Usuarios ---

@router.get("/users", dependencies=[Depends(ADMIN)])
def list_users(q: str = Query("", max_length=100), role: str | None = None, active: bool | None = None) -> dict:
    needle = normalize_text(q.strip())
    items = [u for u in auth.get_store().users.values()
             if (not needle or needle in normalize_text(u.name) or needle in normalize_text(u.email))
             and (role is None or u.role == role) and (active is None or u.active == active)]
    return {"items": [_user_body(u) for u in sorted(items, key=lambda u: normalize_text(u.name))]}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: Any = Body(...), actor: User = Depends(ADMIN)) -> dict:
    data = parse_body(UserIn, payload)
    user = User(ids.new_id(ids.USER, _rng), data.name, data.email, data.role, data.active)

    def change(users: auth.Users, roles: auth.Roles):
        _validated_user(data, user.id, users, roles)
        return None, user.audit_value(), {**users, user.id: user}, roles

    _apply(actor, f"User “{user.name}”", change)
    return _user_body(user)


@router.put("/users/{user_id}")
def update_user(user_id: str, payload: Any = Body(...), actor: User = Depends(ADMIN)) -> dict:
    current = _find_user(user_id)
    data = parse_body(UserIn, payload)

    def change(users: auth.Users, roles: auth.Roles):
        if current.id not in users:
            raise _gone("User")
        _validated_user(data, current.id, users, roles)
        old = users[current.id]
        new = replace(old, name=data.name, email=data.email, role=data.role, active=data.active)
        return old.audit_value(), new.audit_value(), {**users, new.id: new}, roles

    _apply(actor, f"User “{current.name}”", change)
    return _user_body(auth.get_store().users[current.id])


@router.get("/users/audit", dependencies=[Depends(ADMIN)])
def list_audit() -> dict:
    return {"items": [e.to_dict() for e in get_audit_log().entries([auth.AUDIT_SECTION])]}


# --- Roles y permisos ---

def _check_unique_role_name(roles: auth.Roles, name: str, code: str) -> None:
    if any(normalize_text(r.name) == normalize_text(name) and r.code != code for r in roles.values()):
        raise _field_error(status.HTTP_409_CONFLICT, "name", "A role with that name already exists")


@router.get("/roles", dependencies=[Depends(ADMIN)])
def list_roles() -> dict:
    return {"items": [_role_body(r) for r in auth.get_store().roles.values()],
            "permissions": [{"value": p, "label": PERMISSION_LABELS[p]} for p in ALL_PERMISSIONS]}


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(payload: Any = Body(...), actor: User = Depends(ADMIN)) -> dict:
    data = parse_body(NewRoleIn, payload)
    role = Role(ids.stable_id(ids.ROLE, data.code), data.code, data.name, frozenset(data.permissions))

    def change(users: auth.Users, roles: auth.Roles):
        if role.code in roles:
            raise _field_error(status.HTTP_409_CONFLICT, "code", "A role with that code already exists")
        _check_unique_role_name(roles, role.name, role.code)
        return None, role.audit_value(), users, {**roles, role.code: role}

    _apply(actor, f"Role “{role.name}”", change)
    return _role_body(role)


@router.put("/roles/{role_id}")
def update_role(role_id: str, payload: Any = Body(...), actor: User = Depends(ADMIN)) -> dict:
    current = _find_role(role_id)
    data = parse_body(RoleIn, payload)
    if current.builtin and data.name != current.name:
        raise _field_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "name", "The name of a built-in role cannot be changed")

    def change(users: auth.Users, roles: auth.Roles):
        if current.code not in roles:
            raise _gone("Role")
        _check_unique_role_name(roles, data.name, current.code)
        old = roles[current.code]
        new = replace(old, name=data.name, permissions=frozenset(data.permissions))
        return old.audit_value(), new.audit_value(), users, {**roles, new.code: new}

    _apply(actor, f"Role “{current.name}”", change)
    return _role_body(auth.get_store().roles[current.code])


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: str, actor: User = Depends(ADMIN)) -> Response:
    role = _find_role(role_id)
    if role.builtin:
        raise _conflict("It is a built-in role: it cannot be deleted")

    def change(users: auth.Users, roles: auth.Roles):
        if role.code not in roles:
            raise _gone("Role")
        if any(u.role == role.code for u in users.values()):
            raise _conflict("It has assigned users: change their role before deleting it")
        remaining = dict(roles)
        removed = remaining.pop(role.code)
        return removed.audit_value(), None, users, remaining

    _apply(actor, f"Role “{role.name}”", change)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

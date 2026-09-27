"""Autenticación mock para demo: usuarios en memoria, token HMAC firmado y permisos por rol.

No apto para producción (ver vault/decisiones/adr-003-auth-mock-por-roles.md).
"""
import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

DEMO_PASSWORD = "demo"
TOKEN_TTL_SECONDS = int(os.environ.get("AUTH_TOKEN_TTL_SECONDS", 8 * 3600))
_SECRET = os.environ.get("AUTH_SECRET", "dev-only-insecure-secret").encode()

ALL_PERMISSIONS = [
    "dashboards:view",
    "conversations:view",
    "explorer:use",
    "search:use",
    "flows:view",
    "flows:edit",
    "config:view",
    "config:edit",
    "users:admin",
]

DEFAULT_ROLES = {
    "admin": set(ALL_PERMISSIONS),
    "supervisor": set(ALL_PERMISSIONS) - {"config:edit", "users:admin"},
    "analista": {"dashboards:view", "conversations:view", "explorer:use", "search:use", "flows:view", "flows:edit"},
    "viewer": {"dashboards:view", "conversations:view"},
}

DEMO_USERS = [
    ("u-admin", "Admin Demo", "admin@bancohorizonte.demo", "admin"),
    ("u-supervisor", "Supervisora Demo", "supervisor@bancohorizonte.demo", "supervisor"),
    ("u-analista", "Analista Demo", "analista@bancohorizonte.demo", "analista"),
    ("u-viewer", "Viewer Demo", "viewer@bancohorizonte.demo", "viewer"),
]


@dataclass
class User:
    id: str
    name: str
    email: str
    role: str
    active: bool = True


@dataclass
class UserStore:
    users: dict[str, User] = field(default_factory=dict)
    roles: dict[str, set[str]] = field(default_factory=dict)

    def find_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email.lower() == email.lower()), None)

    def get(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def permissions_for(self, role: str) -> set[str]:
        return set(self.roles.get(role, set()))


def _new_store() -> UserStore:
    store = UserStore(roles={role: set(perms) for role, perms in DEFAULT_ROLES.items()})
    for user_id, name, email, role in DEMO_USERS:
        store.users[user_id] = User(user_id, name, email, role)
    return store


_store = _new_store()


def get_store() -> UserStore:
    return _store


def reset_store() -> None:
    global _store
    _store = _new_store()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload_b64: str) -> str:
    return _b64encode(hmac.new(_SECRET, payload_b64.encode(), hashlib.sha256).digest())


def create_token(user: User, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    payload = {"sub": user.id, "exp": int(time.time()) + ttl_seconds}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def _user_from_token(token: str) -> User:
    try:
        payload_b64, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(payload_b64)):
            raise ValueError("firma inválida")
        payload = json.loads(_b64decode(payload_b64))
    except ValueError:
        raise _unauthorized("Token inválido") from None
    if payload.get("exp", 0) <= time.time():
        raise _unauthorized("Token caducado")
    user = get_store().get(payload.get("sub", ""))
    if user is None or not user.active:
        raise _unauthorized("Usuario no válido")
    return user


def authenticate(email: str, password: str) -> User | None:
    user = get_store().find_by_email(email)
    if user is None or not user.active:
        return None
    if not hmac.compare_digest(password.encode(), DEMO_PASSWORD.encode()):
        return None
    return user


_bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Falta el token")
    return _user_from_token(credentials.credentials)


def require_permission(permission: str):
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"Permiso desconocido: {permission}")

    def dependency(user: User = Depends(current_user)) -> User:
        if permission not in get_store().permissions_for(user.role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=f"Falta el permiso {permission}")
        return user

    dependency.permission = permission
    return dependency

"""Autenticación mock para demo: usuarios en memoria, token HMAC firmado y permisos por rol.

No apto para producción (ver vault/decisiones/adr-003-auth-mock-por-roles.md).
"""
import base64
import hashlib
import hmac
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import ids
from app.audit import get_audit_log
from app.clock import now

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

PERMISSION_LABELS = {
    "dashboards:view": "Ver dashboards",
    "conversations:view": "Ver conversaciones",
    "explorer:use": "Usar el explorador",
    "search:use": "Usar la búsqueda semántica",
    "flows:view": "Ver flujos",
    "flows:edit": "Editar y ejecutar flujos",
    "config:view": "Ver configuración",
    "config:edit": "Editar configuración",
    "users:admin": "Administrar usuarios y roles",
}

ADMIN_PERMISSION = "users:admin"
ADMIN_ROLE = "admin"
AUDIT_SECTION = "usuarios"

DEFAULT_ROLES = {
    "admin": set(ALL_PERMISSIONS),
    "supervisor": set(ALL_PERMISSIONS) - {"config:edit", "users:admin"},
    "analista": {"dashboards:view", "conversations:view", "explorer:use", "search:use", "flows:view", "flows:edit"},
    "viewer": {"dashboards:view", "conversations:view"},
}

ROLE_NAMES = {"admin": "Administrador", "supervisor": "Supervisor", "analista": "Analista", "viewer": "Consulta"}

DEMO_USERS = [
    ("Admin Demo", "admin@bancohorizonte.demo", "admin"),
    ("Supervisora Demo", "supervisor@bancohorizonte.demo", "supervisor"),
    ("Analista Demo", "analista@bancohorizonte.demo", "analista"),
    ("Viewer Demo", "viewer@bancohorizonte.demo", "viewer"),
]


def sorted_permissions(permissions: set[str] | frozenset[str]) -> list[str]:
    return [p for p in ALL_PERMISSIONS if p in permissions]


@dataclass(frozen=True)
class Role:
    """Rol: el código es la clave en los usuarios y no cambia; el identificador `1RO` se deriva de él."""
    id: str
    code: str
    name: str
    permissions: frozenset[str]
    builtin: bool = False

    def audit_value(self) -> dict:
        return {"name": self.name, "permissions": sorted_permissions(self.permissions)}


@dataclass
class User:
    id: str
    name: str
    email: str
    role: str
    active: bool = True
    last_login: datetime | None = None

    def audit_value(self) -> dict:
        return {"name": self.name, "email": self.email, "role": self.role, "active": self.active}


class ProtectionError(Exception):
    """El cambio dejaría la plataforma sin administración (FE006, criterio 7)."""


Users = dict[str, User]
Roles = dict[str, Role]
UserChange = Callable[[Users, Roles], tuple[object, object, Users, Roles]]


def _check_protections(actor: User, users: Users, roles: Roles) -> None:
    def can_admin(user: User | None) -> bool:
        return bool(user and user.active and user.role in roles and ADMIN_PERMISSION in roles[user.role].permissions)

    if not can_admin(users.get(actor.id)):
        raise ProtectionError("No puedes quitarte a ti mismo el permiso de administrar usuarios y roles")
    if ADMIN_PERMISSION not in roles[ADMIN_ROLE].permissions:
        raise ProtectionError("El rol de administrador no puede perder el permiso de administrar usuarios y roles")
    if not any(u.active and u.role == ADMIN_ROLE for u in users.values()):
        raise ProtectionError("No se puede desactivar ni cambiar de rol al último administrador activo")


class UserStore:
    """Usuarios y roles en memoria. Toda escritura de la gestión pasa por `apply` (ver su docstring)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.users: Users = {}
        self.roles: Roles = {}
        self.version = 0

    def find_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email.lower() == email.lower()), None)

    def get(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def permissions_for(self, role: str) -> set[str]:
        found = self.roles.get(role)
        return set(found.permissions) if found else set()

    def apply(self, actor: User, element: str, change: UserChange) -> None:
        """Aplica `change` y lo audita bajo el cerrojo.

        `change` recibe copias de usuarios y roles y devuelve el valor anterior y el nuevo (para la auditoría) y los
        usuarios y roles resultantes. Antes de confirmar se comprueban las protecciones sobre el estado resultante: un
        cambio rechazado no deja estado, versión ni entrada. Si el valor no cambia, no se guarda ni se audita.
        """
        with self._lock:
            before, after, users, roles = change(dict(self.users), dict(self.roles))
            if before == after:
                return
            _check_protections(actor, users, roles)
            self.users, self.roles = users, roles
            self.version += 1
            get_audit_log().record(actor, AUDIT_SECTION, element, before, after)

    def touch_login(self, user: User) -> None:
        with self._lock:
            user.last_login = now()


def _new_store() -> UserStore:
    store = UserStore()
    store.roles = {code: Role(ids.stable_id(ids.ROLE, code), code, ROLE_NAMES[code], frozenset(perms), builtin=True)
                   for code, perms in DEFAULT_ROLES.items()}
    for name, email, role in DEMO_USERS:
        user_id = ids.stable_id(ids.USER, email)
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
        if not hmac.compare_digest(signature.encode(), _sign(payload_b64).encode()):
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


def require_permission(*permissions: str):
    """Exige al menos uno de los permisos indicados."""
    unknown = [p for p in permissions if p not in ALL_PERMISSIONS]
    if not permissions or unknown:
        raise ValueError(f"Permisos desconocidos: {unknown}")

    def dependency(user: User = Depends(current_user)) -> User:
        if not get_store().permissions_for(user.role) & set(permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=f"Falta el permiso {' o '.join(permissions)}")
        return user

    dependency.permissions = permissions
    return dependency

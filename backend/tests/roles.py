"""Roles de prueba creados directamente en el store, sin pasar por la API de FE006."""
from app import auth, ids


def add_role(code: str, permissions: set[str]) -> auth.Role:
    role = auth.Role(ids.stable_id(ids.ROLE, code), code, code, frozenset(permissions))
    auth.get_store().roles[code] = role
    return role

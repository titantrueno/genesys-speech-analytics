---
title: "ADR-003 — Autenticación mock con permisos por rol"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, auth, seguridad, roles, mock]
created: 2026-09-27
updated: 2026-09-27
---

# ADR-003 — Autenticación mock con permisos por rol

## Contexto

La plataforma necesita que el acceso a cada sección dependa del rol del usuario (FE001 y FE006), pero en esta fase no hay proveedor de identidad y todos los datos son mock. Hay que poder demostrar el control de acceso de extremo a extremo sin coste de infraestructura.

## Decisión

- Hay usuarios demo en memoria, uno por rol base (`admin`, `supervisor`, `analista`, `viewer`), con una contraseña demo compartida documentada solo en el código y el README del backend.
- El token es propio: payload JSON con `sub` y `exp` en base64url, firmado con HMAC-SHA256. El secreto sale de `AUTH_SECRET` (por defecto, un valor solo para desarrollo) y la caducidad de `AUTH_TOKEN_TTL_SECONDS` (8 h por defecto).
- En cada petición se vuelve a leer el usuario, así que desactivarlo o cambiar los permisos de su rol surte efecto sin emitir un token nuevo.
- Los permisos son granulares: `dashboards:view`, `conversations:view`, `explorer:use`, `search:use`, `flows:view`, `flows:edit`, `config:view`, `config:edit` y `users:admin`.
- Toda ruta de datos usa la dependencia única `require_permission(...)`. Dos tests recorren el esquema OpenAPI:
  - uno exige `401` sin token en toda ruta no pública;
  - el otro exige `403` con un rol sin permisos en toda ruta de datos.

| Rol | Permisos |
|---|---|
| `admin` | Todos |
| `supervisor` | Todos salvo `config:edit` y `users:admin` |
| `analista` | Dashboards, conversaciones, explorador, búsqueda, `flows:view` y `flows:edit` |
| `viewer` | Dashboards y conversaciones |

## Alternativas

- **JWT con librería (PyJWT):** pospuesto. No aporta valor mientras no haya un emisor externo, y el formato propio es trivial de sustituir.
- **OAuth2 o SSO corporativo:** fuera de alcance (FE006), pero es el destino natural para un entorno real.
- **Selector de rol sin login:** descartado por decisión de producto; se quiere un login real, aunque sea mock.

## Consecuencias

- **Riesgo aceptado (solo demo):** la contraseña compartida, el secreto por defecto, la falta de revocación de tokens y la ausencia de rate limiting hacen que este mecanismo no sea apto para producción.
- Antes de cualquier despliegue fuera de local hay que fijar `AUTH_SECRET` y sustituir la autenticación por un proveedor real.
- Las rutas nuevas quedan protegidas por defecto gracias a los tests de recorrido; una ruta sin permiso rompe la suite.

## Fuentes

- [Spec FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/spec.md)
- [Spec FE006](../../features/FE006-gestion-de-usuarios-y-roles/spec.md)
- [Implementación de auth](../../backend/app/auth.py)
- [Tests de auth](../../backend/tests/test_auth.py)

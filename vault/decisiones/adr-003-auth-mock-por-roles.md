---
title: "ADR-003 — Autenticación mock con permisos por rol"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, auth, seguridad, roles, mock]
created: 2026-09-27
updated: 2026-10-02
---

# ADR-003 — Autenticación mock con permisos por rol

## Contexto

La plataforma necesita que el acceso a cada sección dependa del rol del usuario (FE001 y FE006), pero en esta fase no hay proveedor de identidad y todos los datos son mock. Hay que poder demostrar el control de acceso de extremo a extremo sin coste de infraestructura.

## Decisión

- Hay usuarios demo en memoria, uno por rol base (`admin`, `supervisor`, `analista`, `viewer`), con una contraseña demo compartida documentada solo en el código y el README del backend.
- El token es propio: payload JSON con `sub` (identificador `1US-UUID` del usuario, ver [ADR-004](adr-004-identificadores-con-prefijo-y-uuid.md)) y `exp` en base64url, firmado con HMAC-SHA256. El secreto sale de `AUTH_SECRET` (por defecto, un valor solo para desarrollo) y la caducidad de `AUTH_TOKEN_TTL_SECONDS` (8 h por defecto).
- En cada petición se vuelve a leer el usuario, así que desactivarlo o cambiar los permisos de su rol surte efecto sin emitir un token nuevo.
- Los permisos son granulares: `dashboards:view`, `conversations:view`, `explorer:use`, `search:use`, `flows:view`, `flows:edit`, `config:view`, `config:edit` y `users:admin`.
- Toda ruta de datos usa la dependencia única `require_permission(...)`, que acepta uno o varios permisos alternativos (por ejemplo, el catálogo de filtros sirve con `dashboards:view` o con `conversations:view`). Dos tests recorren el esquema OpenAPI:
  - uno exige `401` sin token en toda ruta no pública;
  - el otro exige `403` con un rol sin permisos en toda ruta de datos.

| Rol | Permisos |
|---|---|
| `admin` | Todos |
| `supervisor` | Todos salvo `config:edit` y `users:admin` |
| `analista` | Dashboards, conversaciones, explorador, búsqueda, `flows:view` y `flows:edit` |
| `viewer` | Dashboards y conversaciones |

### Ampliación de FE006 (2026-10-02): gestión de usuarios, roles y permisos

- **La tabla anterior es el estado inicial**, no una regla fija: desde la pestaña Roles se cambian los permisos de cualquier rol, incluidos los base. Un test sigue comprobando ese estado inicial.
- **Roles como entidades:** código inmutable (clave en los usuarios), nombre e identificador `1RO` v5 derivado del código, como los main topics de FE005. Los cuatro roles base no se borran ni se renombran; un rol personalizado solo se borra sin usuarios (`409`).
- **Escritura única con protecciones** (`UserStore.apply`): bajo un cerrojo se calcula el estado resultante, se validan las protecciones y solo entonces se guarda, se sube la versión y se audita en el registro `1AU` compartido con FE005. Protecciones, todas con `409`:
  - nadie se quita a sí mismo `users:admin`, ni por los permisos de su rol ni cambiándose de rol o desactivándose;
  - debe quedar al menos un usuario activo con el rol `admin`;
  - el rol `admin` conserva `users:admin`.
- **Errores por campo:** `422` de validación y `409` por email (sin distinguir mayúsculas), código o nombre de rol duplicados, con el formato `loc`/`msg` de FastAPI para que la UI los muestre junto al campo.
- **Refresco en el front:** cabecera `X-Auth-Version` en cada respuesta a una petición con sesión (expuesta por CORS; sin sesión no se envía, para no revelar la actividad de la gestión). Si cambia, el front recarga `/api/auth/me`; menú y guardas cambian en la siguiente petición. Desactivar a un usuario invalida su token en su siguiente petición (`401`).
- **Último acceso:** se guarda al iniciar sesión; se pierde al reiniciar, como el resto del estado.

## Alternativas

- **JWT con librería (PyJWT):** pospuesto. No aporta valor mientras no haya un emisor externo, y el formato propio es trivial de sustituir.
- **OAuth2 o SSO corporativo:** fuera de alcance (FE006), pero es el destino natural para un entorno real.
- **Refrescar permisos solo al recargar o al iniciar sesión (FE006):** descartado, porque la spec exige el cambio en la siguiente petición. También se descartó consultar `/me` en cada navegación: una cabecera de versión cuesta un entero por respuesta y solo dispara la recarga cuando algo cambia.
- **Roles con identificador v4 (FE006):** descartado. El código ya es la clave estable y único, y así base y personalizados siguen la misma regla que la taxonomía de FE005.
- **Selector de rol sin login:** descartado por decisión de producto; se quiere un login real, aunque sea mock.

## Consecuencias

- **Riesgo aceptado (solo demo):** la contraseña compartida, el secreto por defecto, la falta de revocación de tokens y la ausencia de rate limiting hacen que este mecanismo no sea apto para producción.
- Antes de cualquier despliegue fuera de local hay que fijar `AUTH_SECRET` y sustituir la autenticación por un proveedor real.
- Las rutas nuevas quedan protegidas por defecto gracias a los tests de recorrido; una ruta sin permiso rompe la suite. Las de FE006 (`/api/users`, `/api/roles`) exigen `users:admin` y los dos recorridos las cubren sin cambios.
- **FE006:** los usuarios creados comparten la contraseña demo, y usuarios y roles se pierden al reiniciar. La versión de `X-Auth-Version` también vuelve a 0 al reiniciar; si difiere de la última vista, el front recarga `/me` una vez, sin efectos visibles.

## Fuentes

- [Spec FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/spec.md)
- [Spec FE006](../../features/FE006-gestion-de-usuarios-y-roles/spec.md)
- [Implementación de auth](../../backend/app/auth.py)
- [Tests de auth](../../backend/tests/test_auth.py)
- [Plan FE006](../../features/FE006-gestion-de-usuarios-y-roles/plan.md)
- [API de usuarios y roles](../../backend/app/routers/users.py)

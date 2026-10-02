# FE006 — Ship

> Fase `/ship`. Fecha: 2026-10-02. Entrega: [Plataforma v0.6.0](../../vault/entregas/2026-10-02-plataforma-v0-6-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada el 2026-10-02 |
| [plan.md](plan.md) | T1–T6 hechas, con evidencia, mutaciones y recorrido en Chrome |
| [VERIFY.md](VERIFY.md) | Verde; dos fallos encontrados y corregidos con regresión |
| [REVIEW.md](REVIEW.md) | Aprobado; sin critical ni major abiertos |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.5.1` a `v0.6.0`:

- **Backend:**
  - **modelo** (`app/auth.py`): roles como entidades (`1RO`, v5 derivado del código) con nombre y marca de rol base; usuarios con último acceso; escritura única `UserStore.apply` con protecciones, versión y auditoría bajo cerrojo;
  - **auditoría** (`app/audit.py`): registro `1AU` compartido; la configuración lo usa, y `/api/config/audit` solo ve sus secciones;
  - **API** (`app/routers/users.py`): `/api/users`, `/api/roles` y `/api/users/audit` con `users:admin`; `role_name` en el login y en `/me`; cabecera `X-Auth-Version` (con sesión, expuesta por CORS);
  - `parse_body` compartido con la configuración.
- **Front:**
  - `/usuarios` en diferido con las pestañas Usuarios (búsqueda, filtros, alta, edición, desactivar y reactivar, errores junto al campo) y Roles (roles personalizados y matriz de permisos), más el registro de cambios;
  - recarga de `/me` cuando cambia `X-Auth-Version`, para que menú y guardas sigan a los permisos sin recargar;
  - nombre del rol en la barra lateral;
  - pestañas y registro compartidos con Configuración; fuera `ComingSoonPage`, porque ya no quedan secciones pendientes.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault (45 archivos, 0 errores);
- 723 tests de backend con la combinación de `conftest.py` y con semilla 7 y referencia 2026-11-10;
- 289 tests de front, lint y build;
- `npm audit` y `pip-audit` sin vulnerabilidades.

Sin dependencias nuevas. `.github/workflows/ci.yml` sigue preparado y sin ejecutar, porque no hay remoto.

## Observabilidad

- `GET /api/users/audit` (y el registro de la sección) recoge cada alta, baja, cambio de rol o de permisos, con quién, cuándo, antes y después.
- `X-Auth-Version` cuenta los cambios aceptados de usuarios y roles. Es la señal que mueve el refresco del front, y sirve para comprobar desde fuera que un cambio se ha aplicado.
- Códigos HTTP explícitos: `409` con motivo para las protecciones y con campo para los duplicados; `422` por campo; `404` y `403`.
- **Pendiente con despliegue real:** logs estructurados y alertas para los cambios de `users:admin` y las desactivaciones.

## Rollout y rollback

- **Rollout:** etiqueta local `v0.6.0`. Los recorridos del OpenAPI de FE001 siguen protegiendo todas las rutas, y las suites de FE001–FE005 pasan con los roles convertidos en entidades.
- **Rollback:** `git checkout v0.5.1`. No hay datos persistentes: al reiniciar la API vuelven los cuatro usuarios y roles demo.

## Pendiente tras la entrega

- Etiquetas legibles de los permisos en el registro de cambios (R10).
- Con un proveedor de identidad real (fuera de alcance), sustituir la contraseña demo compartida y añadir limitación de intentos (R6, ADR-003).

# FE006 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-10-02 (petición del usuario de implementarla). Siguiente paso: `/build`, en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| [ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md) y `app/auth.py` | Usuarios y roles en memoria (`UserStore` con `dict[str, set[str]]`), permisos granulares ya definidos, `require_permission` único, el usuario se relee en cada petición | Los roles pasan a ser entidades (`Role`: id, código, nombre, permisos, base o no). El modelo de permisos no cambia; se amplía el ADR con la gestión, las protecciones y el refresco del front (T1, T2, T6). |
| [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md) | `1RO` reservado para FE006 y ya en `PREFIXES`, sin constante | Se añade `ids.ROLE` y pasa a activo. Como los main topics de FE005, el identificador es v5 derivado del **código**, que no cambia (T1). `1AU` se reutiliza para la auditoría. |
| `app/config/store.py` ([ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md)) | El registro de auditoría vive dentro de `ConfigStore` | Se extrae a `app/audit.py` (registro compartido). `ConfigStore.apply_change` sigue auditando bajo su cerrojo; `/api/config/audit` solo devuelve secciones de configuración, para no enseñar cambios de usuarios a quien solo tiene `config:view` (T1). |
| `tests/test_auth.py` | Dos recorridos del OpenAPI: `401` sin token y `403` con un rol sin permisos | Cubren las rutas nuevas sin cambios (riesgo de la spec). El test que crea un rol sin permisos se adapta a `Role` (T1). |
| `frontend/src/auth/AuthContext.tsx` | `/api/auth/me` solo se pide al arrancar | Hay que refrescar el usuario cuando cambian sus permisos (criterio 6): cabecera `X-Auth-Version` en cada respuesta y recarga de `/me` cuando cambia (T2, T5). |
| `frontend/src/router.tsx`, `layout/navigation.ts`, `pages/ComingSoonPage.tsx` | `/usuarios` muestra «Próximamente»; es la última sección sin implementar | Se sustituye por la sección; `ComingSoonPage` queda sin uso y se elimina, igual que su test (T3). |
| `frontend/src/layout/AppLayout.tsx` | `ROLE_LABELS` fijo para los cuatro roles base | Un rol personalizado se vería por su código: `/me` devuelve `role_name` (T2, T5). |
| `frontend/src/config/AuditLog.tsx` y pestañas de `ConfigPage` | Registro y pestañas ligados a la configuración | Se reutilizan: el registro recibe el resultado de la consulta y las pestañas se extraen a `components/Tabs.tsx` (T3). |
| [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md) | 28 lecciones | Se aplican: rutas vía OpenAPI (1), tres estados de datos remotos (6), rojo demostrado y mutaciones (22, 23), gate por código de salida (10, 21, 24), tests independientes del dataset (28) y comprobación con la API real. |

## Decisiones de diseño

- **Modelo** (`app/auth.py`): `Role(id, code, name, permissions, builtin)` y `User(id, name, email, role, active, last_login)`. Los cuatro roles base tienen nombre legible («Administrador», «Supervisor», «Analista», «Consulta»), no se borran y su nombre no cambia; sus permisos sí.
- **Escritura única** `UserStore.apply(actor, element, change)`: bajo un cerrojo calcula el estado resultante sobre copias, comprueba las protecciones, lo confirma, incrementa la **versión** y audita en el registro compartido. Un cambio rechazado no deja estado ni entrada; uno sin efecto tampoco.
- **Protecciones** (criterio 7), sobre el estado resultante, `409` con mensaje:
  - quien hace el cambio debe seguir activo y con `users:admin`;
  - debe quedar al menos un usuario activo con el rol `admin`, y el rol `admin` conserva `users:admin`.
- **Errores:** `422` por campo (formato de FastAPI) para validación; `409` por campo para email, código o nombre duplicados (la UI lo muestra junto al campo); `409` con texto para protecciones, roles base y roles en uso.
- **Refresco de permisos** (criterio 6): el backend ya relee el usuario y su rol en cada petición. Un middleware añade `X-Auth-Version` (versión del `UserStore`) a cada respuesta y CORS la expone; el cliente del front avisa cuando cambia y `AuthProvider` vuelve a pedir `/api/auth/me` sin pantalla de carga.
- **Último acceso:** se guarda al iniciar sesión; los usuarios demo empiezan sin accesos.

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Backend: modelo de roles, escritura única, protecciones y auditoría compartida | — | 4, 7, 9 |
| T2 | Backend: API de usuarios, roles y auditoría; refresco y último acceso | T1 | 2, 3, 4, 5, 6, 8, 9 |
| T3 | Front: sección y pestaña Usuarios | T2 | 1, 2, 3, 8, 9 |
| T4 | Front: pestaña Roles y matriz de permisos | T3 | 4, 5, 7, 9 |
| T5 | Front: menú y acciones actualizados en la siguiente petición | T2 | 6 |
| T6 | Conocimiento, CI y comprobación con la app real | T1–T5 | Conocimiento afectado |

### T1 — Modelo, protecciones y auditoría compartida

- **Qué:** `ids.ROLE`; `Role` y roles base; `UserStore` con cerrojo, versión y `apply`; protecciones; `app/audit.py` con el registro compartido (`ConfigStore` lo usa); `reset_audit_log()` en el fixture `api`.
- **Hecho cuando:** hay tests para el estado inicial (cuatro roles base con `1RO` estable y la matriz de ADR-003), cada protección (quitarse `users:admin` por rol o por cambio de rol, desactivarse, desactivar o degradar al último `admin`, quitar `users:admin` al rol `admin`), que un cambio rechazado no altera el estado ni la versión ni audita, que uno aceptado audita con usuario, sección `usuarios`, elemento, antes y después, y que la auditoría de configuración de FE005 sigue igual.

### T2 — API

- **Qué:** `app/routers/users.py` con `users:admin` en todas las rutas:
  - `GET /api/users?q=&role=&active=`, `POST /api/users`, `PUT /api/users/{id}` (nombre, email, rol y activo);
  - `GET /api/roles` (roles con nº de usuarios y catálogo de permisos con etiqueta), `POST /api/roles`, `PUT /api/roles/{id}` (nombre y permisos), `DELETE /api/roles/{id}`;
  - `GET /api/users/audit`;
  - `role_name` en `/api/auth/me` y en el login; `last_login` al iniciar sesión; cabecera `X-Auth-Version`.
- **Hecho cuando:** hay tests para búsqueda por nombre o email (sin tildes ni mayúsculas) y filtros por rol y estado; alta, edición, desactivación y reactivación; `409` con `loc` en `email` por duplicado (sin distinguir mayúsculas), también al editar; `422` por campo; un usuario desactivado no inicia sesión y su token deja de valer; roles: nº de usuarios, `409` al borrar uno base o en uso, crear uno personalizado y borrarlo; permisos desconocidos `422`; **end-to-end:** retirar `search:use` al rol de la analista hace que su `/me` ya no lo incluya y que la búsqueda responda `403` con el mismo token, y la cabecera cambia; `403` para `supervisor` en cada ruta nueva; auditoría de altas, bajas, cambios de rol y de permisos.

### T3 — Front: sección y Usuarios

- **Qué:** `components/Tabs.tsx` (extraída de `ConfigPage`), `AuditLog` reutilizable, `users/api.ts`, `users/UsersPage.tsx` en `/usuarios` con pestañas en la URL, `users/UsersTab.tsx` (listado, búsqueda, filtros, alta, edición, desactivar con confirmación y reactivar, errores junto al campo, error de protección visible), registro de cambios.
- **Hecho cuando:** hay tests para el listado con sus columnas, la búsqueda y los filtros (parámetros enviados), crear, el `409` de email junto al campo sin perder lo escrito, editar, desactivar con confirmación y reactivar, el `409` de protección, cargando y error, y el `403` del menú para `supervisor`.

### T4 — Front: Roles y matriz

- **Qué:** `users/RolesTab.tsx`: roles con nº de usuarios, marca de rol base, alta de rol personalizado, borrar con confirmación (no en base ni en uso) y la matriz (permisos en filas, roles en columnas) con casillas que guardan al cambiar.
- **Hecho cuando:** hay tests para la tabla, la matriz (casilla marcada según permisos, desmarcar envía los permisos sin ese), crear rol con error por campo, borrar solo en personalizados sin usuarios, y el error de protección al quitar `users:admin`.

### T5 — Front: refresco de permisos

- **Qué:** `api/client.ts` vigila `X-Auth-Version`; `AuthProvider` recarga `/me` cuando cambia; `AppLayout` muestra `role_name`.
- **Hecho cuando:** un test cambia la cabecera en una respuesta y el menú pierde la sección retirada sin recargar; otro comprueba que sin cambio de versión no se vuelve a pedir `/me`; el nombre de un rol personalizado aparece en la barra lateral.

### T6 — Conocimiento y comprobación

- **Qué:** ADR-003 ampliado (gestión, protecciones, refresco), registro de identificadores (`1RO` activo, `1AU` compartido), glosario («rol», «permiso» y la lista de permisos), arquitectura, READMEs y lecciones si aparecen.
- **Hecho cuando:** `python scripts/audit_vault.py` y `./scripts/ci.sh` terminan con código 0, y el recorrido con la API y la web reales (uvicorn y Vite) funciona.

## Progreso

| Tarea | Estado | Evidencia |
|---|---|---|
| T1 | Pendiente | — |
| T2 | Pendiente | — |
| T3 | Pendiente | — |
| T4 | Pendiente | — |
| T5 | Pendiente | — |
| T6 | Pendiente | — |

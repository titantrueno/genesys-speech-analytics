# FE006 — Verificación

> Fase `/test`. Fecha: 2026-10-02. Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde.** Los 9 criterios de aceptación tienen evidencia automatizada y se recorrieron en Chrome con la API y la web reales. La verificación encontró dos fallos reales, ya corregidos con su test de regresión (ver «Bugs encontrados»):

- la casilla de la matriz no reflejaba el clic hasta terminar el guardado (lo vio Chrome, no los tests);
- la versión de usuarios y roles vista por el front sobrevivía a una sesión nueva (lo vio un test de T5).

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `cd backend && .venv/bin/pytest` | **721 passed** (55 de FE006 en `test_users_store.py` y `test_users_api.py`, más los de FE001–FE005 adaptados a `Role`) |
| Segunda combinación de dataset (`DATA_SEED=7`, `DATA_REFERENCE_DATE=2026-11-10`) | 721 passed (lo ejecuta `ci.sh`) |
| `cd frontend && npm test` | **289 passed** (26 ficheros; 22 de FE006 en `UsersPage.test.tsx`, `RolesTab.test.tsx` y `PermissionRefresh.test.tsx`) |
| `npm run lint` / `npm run build` | Código 0 / código 0. Carga inicial de 314 kB, sin cambios; `UsersPage` en un chunk diferido de 12,8 kB |
| `python3 scripts/audit_vault.py` | **Código 0**: 44 archivos, 0 errores |
| `npm audit` / `pip-audit` | 0 vulnerabilidades |
| `./scripts/ci.sh` | **Código 0** |
| Mutaciones (Python sin caché de bytecode, lección 23) | Backend: 16 de 17 detectadas (6 de protecciones, 10 de la API y la de concurrencia); la superviviente (`email.lower()` en la comprobación de duplicados) es equivalente, porque el email se guarda ya normalizado. Front: 13 de 13 detectadas |
| Concurrencia (4 altas simultáneas con el mismo email y la ventana ensanchada) | Una `201` y tres `409`. **Falla si la validación sale del cerrojo** |
| Fuzzing de usuarios y roles (4.000 peticiones con cuerpos inválidos y plausibles, actores variados: admin, admin de rol personalizado, sin permiso) | **0 respuestas `5xx`** (494 `200`, 57 `201`, 23 `204`, 2.152 `403`, 58 `404`, 519 `409`, 697 `422`). Todo `422` lleva `loc` y `msg`. **Versión = entradas de auditoría (190)**. Al terminar queda un `admin` activo, y el rol `admin` conserva `users:admin` |
| API real (uvicorn) | `X-Auth-Version` en cada respuesta y `Access-Control-Expose-Headers: X-Auth-Version` con el origen del front |
| Navegador (Chrome headless, dos sesiones) | Ver «Recorrido en Chrome» |

### Recorrido en Chrome

La API se levantó en el puerto 8010 y Vite en el 5180 (`VITE_API_URL` y `CORS_ORIGINS`), porque el 8000 y el 5173 estaban ocupados por otros procesos del usuario. Se abrieron dos sesiones, una de admin y otra de analista:

1. **Usuarios:** el listado muestra columnas, rol legible, estado y último acceso (los que no han entrado salen como «Nunca»). Al buscar «ANALISTA» aparece una fila.
2. **Email duplicado:** dar de alta `ADMIN@bancohorizonte.demo` devuelve `409`; el mensaje sale bajo el campo con `aria-invalid` y lo escrito se conserva. Después, el alta de Lucía Pérez funciona.
3. **Protección:** el admin no puede desactivarse a sí mismo; aparece «No puedes quitarte a ti mismo el permiso de administrar usuarios y roles».
4. **Matriz:** se desmarca «Usar la búsqueda semántica · Analista».
5. **Criterio 6:** la analista pulsa «Conversaciones» y su menú pierde «Búsqueda semántica» sin recargar la página.
6. **Desactivación:** el admin desactiva a la analista. En su siguiente clic, ella vuelve a `/login` y su nuevo intento de entrar recibe «Credenciales incorrectas».
7. **Auditoría:** el registro muestra el alta, el cambio de permisos y la desactivación, con el antes y el después.
8. **Consola:** solo aparecen los `409` y `401` esperados; ningún error de JavaScript.

## Matriz de trazabilidad

| Criterio | Evidencia |
|---|---|
| 1. Sección con pestañas Usuarios y Roles | `UsersPage.test.tsx` (pestañas y `?tab=roles`); Chrome |
| 2. Listado, búsqueda y filtros | `test_list_has_name_email_role_status_and_last_access`, `test_search_*`, `test_filter_by_role_and_status`, `test_login_records_last_access`; `UsersPage.test.tsx` (columnas, parámetros enviados); Chrome |
| 3. Crear, editar, desactivar y reactivar; `409` junto al campo; desactivado sin login | `test_create_user`, `test_edit_user`, `test_duplicate_email_*` (también al editar y sin distinguir mayúsculas), `test_invalid_user_returns_422_per_field`, `test_deactivated_user_cannot_log_in_and_its_token_stops_working`, concurrencia; `UsersPage.test.tsx`; Chrome |
| 4. Roles con nº de usuarios, base no borrables, personalizados | `test_roles_list_with_user_count_and_permission_catalog`, `test_base_roles_cannot_be_deleted`, `test_create_custom_role_assign_it_and_delete_it_once_unused`, `test_invalid_role_returns_error_per_field`, `test_base_role_name_cannot_change`; `RolesTab.test.tsx` |
| 5. Matriz con los 9 permisos | `test_roles_list_*` (catálogo con etiquetas), `test_permissions_are_returned_in_catalog_order_without_duplicates`; `RolesTab.test.tsx` (filas, columnas, estado, guardado, casilla pendiente) |
| 6. Cambio en la siguiente petición y `403` (end-to-end de API) | `test_removing_a_permission_takes_effect_on_the_next_request_with_the_same_token`, `test_auth_version_*`; `PermissionRefresh.test.tsx`; Chrome |
| 7. Protecciones | `test_users_store.py` (6 casos: quitarse el permiso por rol o por cambio de rol, desactivarse, desactivar o degradar al último `admin`, quitar el permiso al rol `admin`; un rechazo no deja estado, versión ni entrada); `test_admin_cannot_*_through_the_api`, `test_last_active_admin_is_protected_through_the_api`; fuzzing; Chrome |
| 8. Solo con `users:admin`; `403` en la API | `test_only_users_admin_can_use_the_section` (8 rutas con `supervisor`); recorridos del OpenAPI de `test_auth.py` (`401` sin token y `403` sin permisos en las rutas nuevas, sin cambios en los tests); `UsersPage.test.tsx` (menú y «Sin acceso») |
| 9. Auditoría compartida con FE005 | `test_each_user_and_role_change_is_audited`, `test_rejected_or_empty_changes_are_not_audited`, `test_user_changes_stay_out_of_the_config_audit`, `test_config_changes_keep_auditing_in_the_shared_log`; tests de auditoría de FE005 sin cambios; Chrome |

## Fundamentación

| Decisión | Fuente |
|---|---|
| `expose_headers` en `CORSMiddleware` para que el navegador lea `X-Auth-Version` (por defecto, `[]`) | [FastAPI — CORS](https://fastapi.tiangolo.com/tutorial/cors/) y [MDN — Access-Control-Expose-Headers](https://developer.mozilla.org/docs/Web/HTTP/Headers/Access-Control-Expose-Headers); además, un test lo comprueba |
| Middleware HTTP que añade la cabecera tras `call_next` | [FastAPI — Middleware](https://fastapi.tiangolo.com/tutorial/middleware/) |
| La mutación sigue pendiente hasta que termina la recarga lanzada en `onSuccess` | [TanStack Query — Mutations](https://tanstack.com/query/latest/docs/framework/react/guides/mutations): «When returning a promise in any of the callback functions it will first be awaited before the next callback is called». La referencia de `useMutation` no aclara si `isPending` sigue activo, así que se comprobó en el código instalado: en `@tanstack/query-core` 5.104.0, `mutation.ts` espera `onSuccess` (línea 357) antes de despachar `success` (línea 382) |
| `StringConstraints(strip_whitespace, to_lower, pattern)` para normalizar el email | [Pydantic — types](https://pydantic.dev/docs/validation/latest/api/pydantic/types/). **No documenta el orden** en que se aplican; se trata como hipótesis respaldada por tests: `" Lucia.Perez@BancoHorizonte.demo "` se guarda normalizado y `"  admin@…  "` da `409` |
| `409 Conflict` para duplicados y protecciones | [RFC 9110 §15.5.10](https://www.rfc-editor.org/rfc/rfc9110#section-15.5.10): conflicto con el estado actual del recurso |
| Pestañas | [WAI-ARIA APG — Tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) (patrón ya usado en FE005; solo se extrae) |

## Registro de duda

- **CLAIM:** «último admin activo» queda protegido.
  **Asunción:** «admin» significa el rol `admin`.
  **Duda:** ¿y si significa «cualquiera con `users:admin`»?
  **Reconciliación:** se cumplen las dos lecturas. Como quien hace el cambio debe conservar `users:admin`, siempre queda al menos una persona activa con ese permiso. Además, debe quedar al menos un usuario activo con el rol `admin`, y ese rol no puede perder `users:admin`. Hay tests de las dos.
  **STOP.**
- **CLAIM:** los permisos cambian «en la siguiente petición».
  **Asunción:** el backend relee usuario y rol en cada petición (ADR-003), y el front se entera por la cabecera.
  **Duda:** en un despliegue con otro origen el navegador oculta las cabeceras no simples, y una respuesta `401` podría no llevarla.
  **Reconciliación:** CORS la expone (test y API real), y el middleware envuelve todas las respuestas, también las de error. Con `401`, la sesión se cierra igualmente.
  **STOP.**
- **CLAIM:** ningún cambio aceptado queda sin auditar, y ningún rechazo deja rastro.
  **Asunción:** `apply` valida y protege antes de confirmar, todo bajo el cerrojo.
  **Duda:** con escrituras concurrentes, ¿podría colarse un duplicado o perderse una entrada?
  **Reconciliación:** el test de concurrencia con la ventana ensanchada falla si la validación sale del cerrojo, y el fuzzing termina con versión igual a entradas de auditoría.
  **STOP.**
- **CLAIM:** `/api/config/audit` no enseña cambios de usuarios a quien solo tiene `config:view`.
  **Duda:** el registro ahora es compartido.
  **Reconciliación:** `ConfigStore.audit` filtra por las secciones de configuración, y lo prueba `test_user_changes_stay_out_of_the_config_audit`.
  **STOP.**
- **CLAIM:** las lecturas sin cerrojo (listados, `_user_from_token`) son seguras.
  **Asunción:** `apply` sustituye los diccionarios completos en lugar de mutarlos.
  **Duda:** usuarios y roles se asignan en una sola sentencia, pero no de forma atómica para un lector.
  **Reconciliación:** en el peor caso, un lector ve usuarios nuevos con roles anteriores durante una instrucción. Un rol en uso no se puede borrar, así que nadie queda con un rol inexistente; el riesgo se acepta (demo en memoria, ADR-002).
  **STOP.**

## Bugs encontrados

| Bug | Causa raíz | Regresión |
|---|---|---|
| En Chrome, una casilla de la matriz no cambiaba al pulsarla hasta que terminaban el guardado y la recarga: parecía que el clic no había hecho nada | El control es controlado y su valor salía de los datos del servidor; en jsdom la respuesta simulada llega antes de comprobar el estado | `la casilla refleja el clic mientras se guarda, sin esperar a la respuesta` (guardado lento): rojo antes del arreglo y verde después. En Chrome, el cambio se ve en unos 15 ms. Lección 29 |
| La primera respuesta de una sesión nueva podía forzar una recarga de `/me` de más | La versión vista vivía en el módulo `api/client.ts` y sobrevivía a la sesión anterior | `sin cambio de versión no vuelve a pedir el usuario`, y `resetAuthVersion` al cargar, iniciar y cerrar la sesión (mutación detectada). Lección 30 |

## Deuda encontrada (fuera de alcance)

- La auditoría muestra los permisos por su código (`search:use`) y no por su etiqueta. Es legible para un administrador; se deja como mejora.
- El sidebar `sticky h-screen` no cubre toda la altura en capturas de página completa. Ya ocurría antes de FE006 y no se ve al navegar.

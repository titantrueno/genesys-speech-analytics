# FE006 — Revisión

> Fase `/review`. Fecha: 2026-10-02. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Siguiente paso: `/ship`.

## Resultado

**Aprobado.** No hay hallazgos critical ni major abiertos.

- **Resueltos en `/build` y `/test`:** dos minor de corrección (R1, R2).
- **Resueltos en esta revisión:** un minor de seguridad (R3) y uno de corrección (R4), cada uno con su test de regresión en rojo antes del arreglo.
- **Aceptados de forma justificada:** cinco minor y un nit.

## Tamaño del cambio

El diff de código desde `v0.5.1` ocupa unos 35 ficheros y unas 1.350 líneas, por encima de las ~100 recomendadas. Se entregó en commits atómicos: plan, T1–T6, el arreglo encontrado en Chrome, la verificación y esta revisión. Cada uno tiene su evidencia de rojo a verde y sus mutaciones en el [plan](plan.md#progreso). `VERIFY.md` incluye la auditoría del vault en verde.

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Corrección | minor | En Chrome, una casilla de la matriz no reflejaba el clic hasta terminar el guardado y la recarga | **Resuelto en T6**: la columna muestra los permisos pendientes y se deshabilita mientras se guarda; test con guardado lento (lección 29) |
| R2 | Corrección | minor | La versión de usuarios y roles vista por el front sobrevivía a una sesión nueva y forzaba una recarga de `/me` de más | **Resuelto en T5**: `resetAuthVersion` al cargar, iniciar y cerrar la sesión; test y mutación (lección 30) |
| R3 | Seguridad | minor | `X-Auth-Version` salía también en respuestas sin sesión (`/api/health`, login): cualquiera podía contar los cambios de usuarios y roles | **Resuelto**: solo se envía a peticiones con `Authorization`; test `test_auth_version_is_only_sent_to_requests_with_a_session` (rojo antes del arreglo) |
| R4 | Corrección | minor | `touch_login` anotaba el acceso en el objeto que devolvió `authenticate`; si otra escritura lo sustituía entre medias, el último acceso se perdía | **Resuelto**: busca el usuario vigente bajo el cerrojo; test `test_last_access_is_recorded_on_the_current_user_even_if_it_was_replaced_meanwhile` (rojo antes del arreglo) |
| R5 | Seguridad | minor | Pendiente de FE005 (R4): un check por frases sobre el texto original podría servir de oráculo de datos personales, y ahora `config:edit` se puede dar a cualquier rol | **Aceptado**: dar `config:edit` es una decisión de quien tiene `users:admin` y queda auditada en `usuarios`. Además, `config:edit` ya permite desactivar el enmascarado, que es una exposición mayor. La matriz muestra el permiso con su nombre («Editar configuración») |
| R6 | Seguridad | minor | Los usuarios nuevos comparten la contraseña demo y no hay limitación de intentos de login | **Aceptado** (ADR-003 y fuera de alcance de la spec: SSO, OAuth, MFA y recuperación de contraseña); documentado en ADR-003, arquitectura y README del backend |
| R7 | Corrección | minor | Las lecturas (listados y validación del token) no toman el cerrojo; `apply` sustituye usuarios y roles en una sola sentencia, pero no de forma atómica para un lector | **Aceptado**: en el peor caso, un lector ve un instante usuarios nuevos con roles anteriores. Un rol en uso no se borra, así que nadie se queda con un rol inexistente; es el mismo modelo en memoria de ADR-002 |
| R8 | Simplicidad | minor | `routers/users.py` repite dos ayudas cortas del router de configuración (`_gone` y el error por campo) | **Aceptado**: son 6 líneas, y compartirlas exigiría un módulo de errores HTTP para dos routers. `parse_body` sí se extrajo, porque era lógica, no un mensaje |
| R9 | Adherencia a la spec | minor | «El último `admin` activo» admite dos lecturas: el rol `admin` o cualquiera con `users:admin` | **Resuelto por diseño**: se cumplen las dos (ver el registro de duda en VERIFY) y está documentado en ADR-003 |
| R10 | Conocimiento | nit | El registro de cambios muestra los permisos por su código (`search:use`), no por su etiqueta | **Aceptado**: es legible para quien administra; anotado como mejora en VERIFY |
| R11 | Seguridad | — | Todas las rutas nuevas exigen `users:admin`, y los dos recorridos del OpenAPI las cubren sin tocar sus tests. El rechazo de protecciones se aplica sobre el estado resultante y bajo cerrojo. Los cuerpos usan `extra="forbid"` con longitudes y patrones. El email se normaliza y es único sin distinguir mayúsculas, también con escrituras concurrentes. Un usuario desactivado pierde su sesión en la siguiente petición. El fuzzing de 4.000 peticiones no dio ninguna `5xx`. React escapa los textos (sin `innerHTML`). El registro de configuración no expone los cambios de usuarios a quien solo tiene `config:view` | Correcto |
| R12 | Rendimiento | — | El middleware lee un entero por respuesta. Los listados recorren unos pocos usuarios en memoria. `/usuarios` va en diferido (12,8 kB) y la carga inicial no cambia (314 kB). La recarga de `/me` solo se dispara cuando cambia la versión (hay test) | Correcto |
| R13 | Conocimiento | — | ADR-003 ampliado con las alternativas descartadas, arquitectura (sección y límites), registro de identificadores (`1RO` activo, `1AU` compartido), glosario (rol, permiso con la lista completa, matriz), patrones de interfaz, lecciones 29–31 y READMEs; auditoría del vault con código 0 | Correcto |

## Revisión por ejes

- **Corrección:**
  - ver R1, R2, R4 y R7;
  - mutaciones: 16 de 17 en el backend (la superviviente es equivalente) y 13 de 13 en el front;
  - concurrencia con la ventana ensanchada;
  - fuzzing con versión igual a entradas de auditoría.
- **Adherencia a la spec:** los 9 criterios están trazados en [VERIFY](VERIFY.md#matriz-de-trazabilidad); ver R9. El fuera de alcance se respeta: sin SSO, OAuth, MFA ni recuperación de contraseña, sin ámbito de datos por cola o equipo, sin invitaciones por email y sin persistencia. La asunción de la spec (los permisos controlan secciones y acciones, no qué conversaciones se ven) se mantiene.
- **Simplicidad:** ver R8.
  - Una sola vía de escritura (`UserStore.apply`), con el mismo contrato que `ConfigStore.apply_change` de FE005.
  - El front reutiliza las pestañas (ahora en `components/`), `ConfigField`, `ConfirmAction` y `AuditLog`.
  - `ComingSoonPage` se elimina porque ya no queda ninguna sección pendiente.
  - Pendiente de FE005 (R6), el tamaño del router de configuración: FE006 va en su propio router, así que no lo agranda.
- **Seguridad:** ver R3, R5, R6 y R11.
- **Rendimiento:** ver R12.
- **Conocimiento:** ver R10 y R13.

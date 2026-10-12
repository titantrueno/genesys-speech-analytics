# FE011 — Revisión

> Fase `/review`. Fecha: 2026-10-12. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Siguiente paso: `/ship`.

## Resultado

**Aprobado.** No quedan hallazgos critical ni major abiertos.

- **Resueltos en esta revisión:** dos major (R1, privacidad del log, y R2, ejecución bloqueada) y un minor (R3). Los tres con su test en rojo antes del arreglo y una mutación que el test detecta.
- **Resueltos en `/test`:** un major (R4, pérdida silenciosa por el tope de resultados) y un minor (R5, `xmax`).
- **Aceptados de forma justificada:** cinco minor y seis nit.

## Tamaño del cambio

Desde `v0.7.0`, el código, los tests, los scripts y la CI suman unas 4.700 líneas en 48 ficheros, más las fixtures de Genesys (952 kB de JSON) y la documentación. Es muy superior a las ~100 líneas recomendadas, pero se entregó en 13 commits atómicos: spec y plan, T1 a T9 (la T7 en dos), `/test` y esta revisión. Cada tarea tiene su rojo a verde y sus mutaciones en el [plan](plan.md#progreso). El cambio de origen de datos, que lo habría duplicado, se separó en [FE012](../FE012-switch-entre-datos-sinteticos-reales/spec.md). `VERIFY.md` incluye la auditoría del vault en verde (código 0).

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Seguridad (privacidad) | **major** | Un error de PostgreSQL al cargar (por ejemplo, un `CHECK` que falla) trae en su `DETAIL` la fila entera («Failing row contains …»). Si es un turno, incluye **el texto de la transcripción**, y acababa en el log de la ejecución, en contra del criterio 18 y del [gobierno del vault](../../vault/Governance.md) | **Resuelto**: `describe_error` usa solo `diag.message_primary` en los errores de base de datos ([psycopg — Diagnostic](https://www.psycopg.org/psycopg3/docs/api/errors.html#psycopg.errors.Diagnostic)). El test `test_a_database_error_never_puts_turn_text_in_the_log` fallaba con el texto «…tengo un movimiento de tarjeta…» en el log; la mutación que vuelve a usar el error completo se detecta |
| R2 | Corrección | **major** | Si una ejecución fallaba fuera de sus manejadores (al escribir la primera línea del log o al cerrar la ejecución), quedaba `en_curso` y su flujo respondía `409` hasta reiniciar el servicio, porque el *future* del pool se traga la excepción | **Resuelto**: `RunExecutor.execute` registra el fallo (`logger.exception`) y marca la ejecución `error` («Fallo inesperado del servicio de ingesta») con una conexión nueva. Test `test_a_run_that_crashes_outside_its_handlers_ends_in_error` (rojo antes; mutación detectada) |
| R3 | Corrección (operación) | minor | El bucle del programador tragaba cualquier excepción sin dejar rastro: con PostgreSQL caído, las descargas programadas dejaban de lanzarse en silencio | **Resuelto**: `safe_tick` registra el fallo y sigue en el siguiente tic. Test `test_a_failing_tick_is_logged_and_the_scheduler_keeps_going` (rojo antes; mutación detectada) |
| R4 | Corrección | **major** | La búsqueda confiaba en `totalHits`, pero Genesys deja de paginar a partir de un tope de resultados | **Resuelto en `/test`**: el tramo se parte hasta que cabe. Ver el registro de duda en [VERIFY](VERIFY.md) |
| R5 | Corrección | minor | «Insertada o actualizada» dependía de `xmax`, un detalle interno no documentado | **Resuelto en `/test`**: `ON CONFLICT DO NOTHING RETURNING` más `UPDATE` |
| R6 | Seguridad | — | Autenticación entre procesos | **Correcto**: token interno comparado como `bytes` con `hmac.compare_digest`; servicio sin CORS y, por defecto, en `127.0.0.1` (uvicorn); `/docs` y `/openapi.json` sin token solo describen rutas. La API reenvía la sesión del usuario como datos (autoría y quién lanza), nunca como credencial |
| R7 | Seguridad (inyección) | — | SQL | **Correcto**: todos los valores van parametrizados. Las f-strings solo componen nombres de tabla y columna fijos del código. Los identificadores que llegan por URL se validan (`is_valid`) o se escapan (`quote`) antes de reenviarse |
| R8 | Seguridad (secretos) | — | Credenciales de Genesys | **Correcto**: solo las lee el servicio de ingesta (lista blanca y test estructural). Se comprueba que no aparecen en errores (6 caminos), log, respuestas ni filas de la base de datos (test de `/test`). `.env` ignorado; `.env.example` sin valores |
| R9 | Seguridad (datos personales) | minor | Las fixtures versionadas llevan ANI, `externalTag` y texto real (con nombres) de la cuenta del laboratorio | **Aceptado**: decisión explícita de la persona usuaria para este desarrollo ([spec](spec.md), [ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)). Sin organización, URL firmadas ni tokens (test). Para producción, revisarlo |
| R10 | Seguridad | nit | `get_signed` descarga la URL que devuelve Genesys | **Aceptado**: la URL viene de la API de Genesys por TLS y con el token, y se pide sin credenciales. No la puede fijar ningún usuario de la plataforma |
| R11 | Corrección | minor | La API comparte un `httpx.Client` entre los hilos de FastAPI | **Aceptado**: httpx gestiona un pool de conexiones para uso concurrente. Solo [una copia de su documentación](https://tessl.io/registry/tessl/pypi-httpx/files/docs/sync-client.md) lo afirma explícitamente; la oficial no se pudo confirmar. Las peticiones son cortas y la prueba real con varias pestañas no dio errores. Si aparecieran, la solución es un cliente por petición |
| R12 | Corrección | nit | Un sentimiento fuera de `[-1, 1]` hace fallar la conversación entera (por el `CHECK`) | **Aceptado**: Genesys solo da `-1` y `1`. El fallo queda en el log, sin datos tras R1, y la ejecución sigue con las demás |
| R13 | Rendimiento | minor | Contra Genesys real, la descarga es secuencial: unos 1 s por conversación (13 en 13–14 s), así que 90 días con mucho volumen tardarían horas | **Aceptado**: el *rate limit* de Genesys (300 peticiones por minuto por token, según su foro) limita el paralelismo útil. Mejora futura: descargar varias conversaciones a la vez respetando ese límite |
| R14 | Rendimiento | — | Carga y lecturas | **Correcto**: 1.000 conversaciones del Genesys falso en unos 10 s (criterio 25), lecturas sin bloqueos durante una ejecución (test), y la consulta de cada conversación usa índices (`genesys_id` único y claves primarias compuestas) |
| R15 | Simplicidad | nit | `normalize.py` tiene unas 530 líneas con funciones anidadas | **Aceptado**: son funciones puras con 23 tests sobre fixtures reales. Se trocea si FE012 o la fase con LLM la hacen crecer |
| R16 | Simplicidad | nit | `_iso` aparece en varios módulos | **Aceptado**: una línea, sin lógica que pueda divergir |
| R17 | Corrección | nit | «Descargar log» usa `fetch` directo: con la sesión caducada muestra «No se ha podido descargar el log» en lugar de cerrar la sesión | **Aceptado**: la app cierra la sesión en su siguiente petición propia (cada 2 s en una ejecución activa) |
| R18 | Corrección | nit | El lector de `.env` no admite `export` ni comentarios al final de una línea | **Aceptado**: el formato está documentado en `.env.example`. Las claves que faltan dan un error claro al arrancar |
| R19 | Mantenibilidad | minor | El gate depende ahora de Docker | **Aceptado**: [ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md). `ci.sh` falla con un mensaje claro (`colima start`), y `REQUIRE_PG=1` impide un verde sin los tests de base de datos |
| R20 | Adherencia a la spec | — | 28 de 28 criterios con evidencia (matriz en VERIFY), y se respeta el fuera de alcance: sin cambio de origen ni uso de los datos reales en la plataforma (FE012), sin LLM, sin audio | **Correcto**. Desviaciones documentadas en el plan: T7 dividida, `409` al borrar con una ejecución activa, «cada N horas» alineado a medianoche, tarjeta del conector como lista de definición |
| R21 | Conocimiento | — | ADR-008, datos de Genesys para STA, runbook, arquitectura, contrato (69 operaciones), registro de identificadores, ADR-002, estado operativo, glosario y lecciones 34–40; auditoría del vault con código 0 | **Correcto**. La tabla de estado del `README` la actualiza `/ship` |

## Revisión por ejes

- **Corrección:**
  - ver R2, R3, R4, R5, R11, R12, R17 y R18;
  - 130 de 130 mutaciones detectadas (127 de `/test` y las 3 de esta revisión);
  - estados intermedios observados con un gancho y con un servidor real;
  - arranque concurrente probado con una barrera.
- **Adherencia a la spec:** ver R20.
- **Simplicidad:**
  - ver R15 y R16;
  - sin ORM ni colas;
  - un único `launch` para la ejecución manual y la programada;
  - el Genesys falso reutiliza `RawConversation`;
  - el front reutiliza `ConfigField`, `StatusBadge` y `useRowNavigation`.
- **Seguridad:** ver R1 y R6 a R10. `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades.
- **Rendimiento:** ver R13 y R14.
- **Conocimiento:** ver R21.

# FE011 — Verificación

> Fase `/test` (2026-10-12). Incluye el recorrido de la T8 del [plan](plan.md). Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde.** Los 28 criterios de aceptación tienen evidencia automatizada, real (Genesys y Chrome) o ambas. La verificación escéptica encontró y corrigió tres problemas:

1. **Pérdida silenciosa de conversaciones:** la consulta de Genesys deja de paginar a partir de un número de resultados, y un tramo de 7 días con más conversaciones las habría perdido sin avisar. Ahora el tramo se parte hasta que cabe.
2. **«Insertada o actualizada» con un dato no documentado:** se decidía con `xmax` de PostgreSQL. Ahora se usa `ON CONFLICT DO NOTHING RETURNING` más un `UPDATE`, con semántica documentada.
3. **Log poco legible:** los instantes salían en ISO UTC con microsegundos.

Además se añadieron dos tests que faltaban: ninguna fila de la base de datos contiene secretos, tokens ni URL firmadas, y el servicio publica su propio OpenAPI.

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `./scripts/ci.sh` | **Código 0** («CI local: OK») |
| `python3 scripts/audit_vault.py` | **Código 0**: 50 archivos, 0 errores |
| Backend, sin PostgreSQL (dos datasets, FE009) | **854 passed** y 854 passed |
| Backend, con PostgreSQL (`REQUIRE_PG=1`) | **54 passed** |
| Front (`npm test`, `npm run lint`, `npm run build`, `tsc -b`) | **352 passed** (31 ficheros); lint sin avisos; código 0 en todo |
| OpenAPI | `openapi.yaml` al día y válido: 69 operaciones sobre 52 rutas |
| `pip-audit` / `npm audit --audit-level=high` | 0 vulnerabilidades / 0 «high». Siguen las 4 «moderate» de `swagger-ui-react`, que ya existían (ADR-002) |
| Mutaciones | **127 de 127 detectadas** entre T1 y `/test`: T1 7, T2 17, T3 16, T4 20, T5 20, T6 17, T7a 12, T7b 14, y en `/test` 2 (`xmax`), 1 (partición de tramos) y 1 (URL firmada en la base de datos). Las que sobrevivieron al principio se resolvieron con tests nuevos o quitando código muerto (ver el plan) |
| Rendimiento | 1.000 conversaciones del Genesys falso en unos 10 s (límite: 60 s) |
| Genesys real | Pruebas de humo de la T4, la T5 y la T6, y la T8 completa (abajo) |
| Dependencia nueva | `psycopg` 3.3.6, licencia LGPL-3.0-only (`pip show psycopg`) |

## Entorno

- **PostgreSQL** (Colima) con la base `speech_analytics`, que ya contenía las conversaciones de las pruebas de humo de la T4 y la T6.
- **Procesos en puertos propios:** servicio de ingesta en el 18001, API en el 18000 (`INGESTION_URL=http://localhost:18001`) y web en el 15173 (`API_PROXY_TARGET=http://localhost:18000`). Se arrancaron y pararon por PID, sin tocar los procesos de la persona usuaria.
- **Genesys:** la cuenta real del laboratorio (organización «SGTO», `eu-west-1`), en solo lectura.
- **Navegador:** Chrome real con la extensión Claude in Chrome, en una pestaña nueva que se cerró al terminar.

## Criterios 26 y 27: conversaciones del día (T8)

| Comprobación | Resultado |
|---|---|
| Conversaciones terminadas de hoy en Genesys (voz y chat), consulta de analítica | **13**, ninguna omitida |
| Conversaciones de hoy guardadas en PostgreSQL | **13**, el mismo conjunto de identificadores |
| Tipos presentes | Los 7 de la tabla de la spec |
| Repetir la descarga (manual a las 15:51 y programada a las 16:00, sobre las de la T4 y la T6) | 0 insertadas y 13 actualizadas en cada una. Las filas se mantienen: 13 conversaciones, 131 turnos, 48 tramos y 32 temas |

Valores del criterio 27, leídos con `GET /conversations/{id}` del servicio de ingesta en marcha:

| Referencia | Comprobado | Resultado |
|---|---|---|
| `37dcbccf` voz contenida en el bot | 12 turnos (9 del bot y 3 del cliente); ANI, DNIS y `externalTag`; flujo «Sierra VoiceAgent»; contenida; colgó el cliente (`endpoint`); 4 temas con su frase; completa | OK |
| `7b94988a` voz bot → agente | Turnos del bot antes de la transferencia y del agente después; derivada, con 218,1 s en el bot; cola `AIT_Transcription`; agente «Javier Del Olmo»; wrap-up; 8 temas; confianza del agente menor que la del bot | OK |
| `8d29170a` chat con agente | 16 turnos (uno por mensaje); métricas de chat; 2 temas; sin ANI ni acústica | OK |
| `f7e79502` chat bot → agente | 3 turnos del bot antes del agente; derivada; 3 mensajes del bot | OK |
| `9e3ec75a` mensaje no entregado | Un único turno no entregado: agente, «lo estoy revisando, un segundo» | OK |
| `c870bc58` chat con reconexión | Dos tramos de agente con su wrap-up; reconexión; 5 turnos del cliente y 4 del agente; sin errores por el `404` | OK |
| `687f2225` voz con agente sin frases | Parcial; agente y wrap-up resueltos; tiempo de conversación | OK |

## Criterio 28: recorrido en Chrome (T8)

**Con `admin`:**

1. **Configuración → Fuentes de datos:** la tarjeta «Genesys Cloud · datos reales» muestra el servicio disponible, `eu-west-1`, credenciales configuradas, la última descarga («Con avisos»), 13 conversaciones (voz 7 · chat 6) y su calidad (completa 9 · parcial 2 · sin transcripción 2). Los conectores mock de FE005 siguen encima, sin cambios.
2. **«Probar conexión»:** devuelve «Conexión correcta con Genesys Cloud: SGTO (eu-west-1)», y «Última prueba» pasa a «Correcta · 12 oct, 15:50 · SGTO».
3. **Flujos de insights:** el listado muestra las columnas «Tipo» y «Próxima ejecución». «Nuevo flujo» con el tipo «Descarga de transcripciones» crea «Descarga de hoy» y abre su formulario («Hoy», voz y chat, «Solo manual»).
4. **«Ejecutar ahora»:** abre la ejecución «En curso», con el progreso (1 de 13…) y el log en vivo. Termina en «Con avisos»: 13 de 13 descargadas, 0 insertadas y 13 actualizadas, voz 7 · chat 6, completa 9 · parcial 2 · sin transcripción 2, 2 mensajes no entregados, 14,4 s. El log tiene los 6 avisos esperados, cada uno con su conversación: 2 sin transcripción, 2 parciales y 2 con mensajes no entregados.
5. **Log:**
   - el filtro «Aviso» deja solo esos 6;
   - el log en texto (`format=text`) responde `200` con 14 líneas.

   No se pulsó «Descargar log», para no guardar un fichero en el equipo sin preguntar. La descarga del fichero está cubierta por los tests del front, y sus cabeceras se comprobaron con curl en la T5 y la T6.
6. **Historial:** muestra la ejecución, y su fila la vuelve a abrir.
7. **Programación:** se cambia a «Cada N horas» con 1. La cabecera pasa a «Cada hora · próxima ejecución: 12 oct, 16:00».
   - **El programador lanzó la ejecución a las 16:00:04** (origen «Programada»), que terminó en «Con avisos» con 13 encontradas y 13 actualizadas.
   - La siguiente quedó a las 17:00.
   - Después se devolvió el flujo a «Solo manual», para que no siga descargando.
8. **Servicio de ingesta parado** (se paró solo el proceso del 18001):
   - el listado muestra el aviso «Las descargas de Genesys no están disponibles: el servicio de ingesta no responde», con los flujos de insights a la vista;
   - un flujo de insights se crea y su editor abre con normalidad;
   - la tarjeta de Genesys dice «El servicio de ingesta no responde».

**Con un rol que solo tiene `flows:view`** (rol `lector_flujos` y usuaria creados por la API, en memoria): el listado no tiene «Nuevo flujo» ni columna «Acciones»; el formulario está deshabilitado y sin «Guardar»; no hay «Ejecutar ahora»; el historial se ve.

**Consola:** sin errores en ninguna pantalla.

## Hallazgos

| Hallazgo | Arreglo |
|---|---|
| El log mostraba los instantes en ISO UTC con microsegundos: «Ejecución manual de 2026-10-11T22:00:00+00:00 a 2026-10-12T13:51:16.515358+00:00» | Los instantes del inicio y de los tramos se escriben en la zona horaria del flujo y al minuto: «12/10/2026 00:00 – 12/10/2026 15:51 (Europe/Madrid)». El test `test_the_log_shows_instants_in_the_flow_timezone_without_microseconds` falló antes del cambio y pasa después. |

## Matriz de trazabilidad

| Criterio | Evidencia |
|---|---|
| 1. Arranque y migraciones sin perder datos | `test_ingestion_service.py`: `test_migrations_create_the_whole_schema`, `test_running_the_migrations_again_keeps_the_data`; uvicorn real (T1) |
| 2. Esquema normalizado y lectura interna | `test_the_internal_read_returns_the_normalized_conversation`, `test_the_read_resolves_queue_agent_and_wrapup_names`; T8 con `GET /conversations/{id}` |
| 3. Credenciales solo en la ingesta; sin secretos en ninguna salida | `test_ingestion_settings.py` (lista blanca, `repr`, estructura de imports); `test_no_error_reveals_the_secret_the_token_or_a_signed_url` (6 caminos); `test_the_log_covers_every_stage_without_turn_text_or_secrets`; **`test_no_stored_row_contains_the_secret_a_token_or_a_signed_url`** (nuevo); `test_wrong_credentials_are_reported_without_the_secret` |
| 4. OAuth, caché del token, credenciales malas, `403` | `test_genesys_client.py` (reloj simulado, renovación, `401`, `403` con ruta y permiso); Genesys real |
| 5. Token interno, sin CORS, OpenAPI propio | `test_without_the_internal_token_every_request_is_rejected` (con no ASCII), `test_the_service_is_not_exposed_to_browsers`, **`test_the_service_publishes_its_own_openapi_without_the_token`** (nuevo) |
| 6. Extracción: tramos, paginación, omisiones, transcripciones, mensajes y reintentos | `test_ingestion_extract.py` (incluida **la partición por el tope de resultados**, nueva); reintentos en `test_genesys_client.py`; `test_a_conversation_that_keeps_failing_does_not_stop_the_run` |
| 7. Turnos, hablantes, offsets, sentimiento y calidad | `test_ingestion_normalize.py` (23 tests sobre las 10 fixtures) |
| 8. Analítica de Genesys | `test_ingestion_normalize.py` (recorrido, cierre, contención, tiempos, chat, STA, acústica, confianza) |
| 9. Identificadores v5 sin colisiones | `test_real_identifiers_never_collide_with_the_synthetic_dataset`, `test_the_customer_comes_from_the_external_contact_then_the_phone` |
| 10. Carga idempotente | `test_repeating_a_run_duplicates_nothing`, `test_a_partial_transcript_becomes_complete_on_a_later_run`; T8 (3 descargas sin duplicados) |
| 11. `Analyzer` sustituible | `test_an_analyzer_fills_the_analysis_without_changing_the_schema` |
| 12. Tipos de flujo en el listado | `DownloadFlows.test.tsx`; Chrome |
| 13. Configuración y validación del flujo de descarga | `test_each_rule_answers_422_with_a_message_per_field` (15 casos), `test_ingestion_schedule.py`; formulario en `DownloadFlows.test.tsx`; Chrome |
| 14. Persistencia | `test_flows_runs_and_logs_survive_a_restart` |
| 15. Ejecución manual, `202` y `409` | `test_a_manual_run_resolves_the_interval_and_records_who_launched_it`, `test_a_second_run_while_one_is_active_is_409`, `test_two_simultaneous_launches_start_a_single_run`; servidor real (T5) y Chrome |
| 16. Ejecución programada | `test_an_hourly_flow_runs_once_per_hour_and_not_twice` y siguientes; **ejecución programada real a las 16:00** (T8) |
| 17. Contadores | `test_counters_add_up_with_skipped_conversations`, `test_progress_is_visible_while_the_run_is_going` |
| 18. Log | `test_the_log_*` (backend); `DownloadRuns.test.tsx` (polling, `after`, filtro, lectura final, descarga); Chrome |
| 19. Historial y retención | `test_history_is_newest_first_and_the_flow_shows_its_last_run`, `test_only_the_200_most_recent_runs_are_kept`; Chrome |
| 20. Permisos | `test_downloads_api.py` (`flows:view` frente a `flows:edit`; `viewer`); recorrido `401` de `test_auth.py`; Chrome con un rol `flows:view` |
| 21. Servicio caído | `test_an_unreachable_service_is_503_and_insight_flows_keep_working` (5 rutas), sin token y con token rechazado; Chrome con la ingesta parada |
| 22. Estado del conector | `test_connector_status_needs_config_view_and_the_test_config_edit`, `test_the_connector_reports_counts_and_tests_the_credentials`; `GenesysConnector.test.tsx`; Chrome |
| 23. Gate | `./scripts/ci.sh` código 0, con la pasada `pg` obligatoria; `ci.yml` con el servicio `postgres` |
| 24. Fixtures saneadas | `test_genesys_fixtures.py` (sin organización, URL firmadas ni tokens; ANI y `externalTag` conservados) |
| 25. Rendimiento | `test_a_thousand_conversations_load_in_under_a_minute`, `test_reads_keep_answering_during_a_run` |
| 26. Conversaciones del día | T8: 13 en Genesys y 13 guardadas, sin duplicados |
| 27. Valores por tipo | T8 (7 de 7) y las fixtures en `test_ingestion_normalize.py` |
| 28. Recorrido en Chrome | T8 (arriba) |

## Fundamentación

| Decisión | Fuente |
|---|---|
| Insertada o actualizada: `ON CONFLICT DO NOTHING` y `RETURNING` solo devuelve las filas insertadas | [PostgreSQL 16 — INSERT](https://www.postgresql.org/docs/16/sql-insert.html) («ON CONFLICT DO NOTHING simply avoids inserting a row»; `RETURNING` devuelve las filas insertadas o actualizadas) |
| Cerrojo consultivo de transacción para migrar | [PostgreSQL 16 — Advisory Lock Functions](https://www.postgresql.org/docs/16/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS) (`pg_advisory_xact_lock`, se libera al terminar la transacción) |
| Fábrica de filas por cursor (`tuple_row`) | [psycopg 3 — Row factories](https://www.psycopg.org/psycopg3/docs/advanced/rows.html) |
| Genesys falso con `httpx.MockTransport` | [HTTPX — Mock transports](https://www.python-httpx.org/advanced/transports/#mock-transports) |
| Token interno como dependencia global; `/docs` y `/openapi.json` sin ella | [FastAPI — Global Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/global-dependencies/); las rutas de documentación se añaden fuera de las operaciones (comprobado con un test) |
| Migración y programador en `lifespan` | [FastAPI — Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) |
| «Últimas N horas» en UTC: la resta entre fechas con la misma `tzinfo` ignora la zona (hora de pared) | [Python — datetime, aware arithmetic](https://docs.python.org/3/library/datetime.html#datetime-objects) |
| Cierre del pool con `cancel_futures` | [Python — concurrent.futures](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor.shutdown) |
| Polling del front con `refetchInterval` en función del estado | [TanStack Query v5 — useQuery](https://tanstack.com/query/v5/docs/framework/react/reference/useQuery) |
| user-event no simula `datetime-local` | Código instalado: `@testing-library/user-event/dist/esm/event/input.js` (`isDateOrTime` solo `date` y `time`) |
| `429` con `Retry-After` y espera creciente | [Foro de Genesys: «Normalized Platform API 429 responses»](https://developer.genesys.cloud/forum/t/normalized-platform-api-429-responses/12028) y [respuesta sobre 429](https://community.genesys.com/discussion/i-am-getting-error-429-rate-limit-exceeded-even-after-3-requests). La página oficial de límites no se pudo leer (el Developer Center se genera con JavaScript) |
| Transcripción por `…/communications/{id}/transcripturl` | [Foro de Genesys: «Retrieve conversation transcript»](https://developer.genesys.cloud/forum/t/retrieve-conversation-transcript/21489); comprobado contra la cuenta real |
| Tope de resultados por consulta | [Foro de Genesys: máximo de registros por consulta](https://developer.genesys.cloud/forum/t/analytics-conversation-detail-endpoint-api-maximum-record-per-query-change/8789) (100.000 según el aviso y 10.000 según una respuesta; se toma el menor) |
| `eu-west-1` en Dublín | [Genesys — AWS regions for Genesys Cloud](https://help.genesys.cloud/articles/aws-regions-for-genesys-cloud-deployment/); el dominio `mypurecloud.ie` está comprobado con un token real |

## Registro de duda

- **CLAIM:** la consulta de detalles rechaza intervalos de más de 7 días.
  **Duda:** la documentación pública habla de un periodo hacia atrás de 558 días ([aviso de Genesys](https://help.genesys.cloud/227647)), no de 7.
  **Reconciliación:** son límites distintos. Uno es la longitud de cada intervalo, observada en la cuenta («…that does not exceed 7 days», `400`). El otro es hasta qué fecha se puede mirar atrás. Los tramos de 7 días cumplen el primero; el segundo no afecta a intervalos de como mucho 90 días.
  **STOP.**
- **CLAIM:** paginar hasta `totalHits` trae todas las conversaciones del tramo.
  **Duda:** el foro de Genesys habla de un tope de 10.000 o 100.000 resultados por consulta.
  **Reconciliación:** era un fallo latente: un tramo con más resultados perdería conversaciones sin avisar. Ahora se parte en mitades hasta que cabe (mínimo, una hora), con el test `test_a_chunk_over_the_result_cap_is_split_until_it_fits`. La mutación que lo desactiva se detecta.
  **STOP.**
- **CLAIM:** `RETURNING (xmax = 0)` distingue una inserción de una actualización.
  **Duda:** es un detalle interno de PostgreSQL que su documentación no garantiza.
  **Reconciliación:** se sustituyó por `ON CONFLICT DO NOTHING RETURNING id` y, si no devuelve fila, `UPDATE`. Las mutaciones «no actualiza la existente» y «al revés» se detectan.
  **STOP.**
- **CLAIM:** respetar `Retry-After` basta ante un `429`.
  **Duda:** el foro dice que la cabecera no siempre está y no siempre es exacta.
  **Reconciliación:** sin cabecera, la espera crece (1, 2, 4…). Tras 5 esperas se da la conversación por fallida, y la ejecución sigue y la recoge en la siguiente descarga. **Riesgo aceptado** para cuentas con mucho volumen, a vigilar en el log.
  **STOP.**
- **CLAIM:** las frases sin entrada de sentimiento son neutras (`0`).
  **Duda:** Genesys no lo documenta.
  **Reconciliación:** sigue siendo una **hipótesis** (spec y [Datos de Genesys para STA](../../vault/producto/datos-de-genesys-para-sta.md)), aislada en un único punto de la normalización para cambiarla sin tocar el resto.
  **STOP.**
- **CLAIM:** la tabla de regiones de `regions.py` es correcta.
  **Duda:** el Developer Center no se pudo leer.
  **Reconciliación:** solo `eu-west-1` → `mypurecloud.ie` está verificada. Para otra región se puede poner el dominio directamente en `GENESYS_REGION`; «Probar conexión» lo confirma.
  **STOP.**
- **CLAIM:** una frase `internal` sin `userIds` es del bot.
  **Duda:** solo se ha observado en 13 conversaciones de una cuenta.
  **Reconciliación:** si cae en el tramo de un agente, es del agente (test). Queda como hipótesis en la spec.
  **STOP.**

## Bugs encontrados

| Bug | Causa raíz | Test de regresión |
|---|---|---|
| El sentimiento se aplicaba a la frase equivocada (T3) | El `phraseIndex` de Genesys no es el índice de la frase | `test_a_call_from_the_bot_to_an_agent` («vale muchas gracias» con sentimiento 1) |
| Las 10 conversaciones de una ejecución acababan con error (T4) | `load` leía por posición filas de una conexión con `dict_row` | Toda la batería `pg` de `test_ingestion_runs.py` |
| Pérdida silenciosa por encima del tope de resultados (`/test`) | La paginación confiaba en `totalHits` | `test_a_chunk_over_the_result_cap_is_split_until_it_fits` |
| «Insertada o actualizada» dependía de `xmax` (`/test`) | Detalle interno no documentado | `test_repeating_a_run_duplicates_nothing` y las mutaciones de arriba |
| Log con instantes ISO UTC con microsegundos (T8) | Se formateaba con `isoformat()` | `test_the_log_shows_instants_in_the_flow_timezone_without_microseconds` |
| Prueba con servidores reales contra otro proceso (T6) | `pkill -f` y el puerto 8000 ocupado | Procedimiento: puertos propios y PID ([lección 36](../../vault/aprendizaje/lecciones-construccion-plataforma.md)) |

## Estado que queda

- **PostgreSQL** contiene las 13 conversaciones de hoy y dos flujos de descarga: «Prueba de humo T4» (T4) y «Descarga de hoy» (T8), los dos «Solo manual», con sus ejecuciones.
- **Todo lo que viva en la memoria de la API se perdió al pararla:** el flujo de insights de prueba, el rol `lector_flujos` y su usuaria.
- **Procesos:** ninguno de la prueba sigue en marcha. PostgreSQL sigue arrancado.

# FE017 — Verificación

> Fase `/test` (2026-10-13). Recoge el recorrido en Chrome de `/build` T8 contra la API real y la cuenta de Genesys del laboratorio, la cobertura de cada criterio, las mutaciones, las fuentes y el log de duda. Siguiente paso: `/review`.

## Recorrido en Chrome (criterio 21)

Entorno: `./scripts/dev.sh` con puertos propios (API 18000, ingesta 18001, LLM 18002, web 15173), PostgreSQL de desarrollo, origen de datos «Real», interfaz en inglés (configuración guardada), usuario `admin`. Flujo creado para la prueba: «FE017 verificación end-to-end» (`1FL-F0DA2F92-D1C2-4D91-9422-761DBABB897F`).

| Paso | Resultado |
|---|---|
| Arrastrar «Genesys download» de la paleta al lienzo | La caja aparece con su tarjeta («Today · Voice + Chat · Manual only») y su panel. La paleta la deshabilita: «A flow can only have one Genesys download.» |
| Arrastrar Sampling, Prompt y Output y conectar caja → Sampling con el ratón | Conectado. El panel del Sampling oculta las fechas, explica que las conversaciones las da la descarga y la estimación dice «The number of conversations depends on the download.» |
| Marcar «All conversations» | Se ocultan método y tamaño; la tarjeta dice «All conversations». |
| Conectar la caja con el Prompt | Rechazado: «Cannot connect: A Genesys download can only be connected to a Sampling.» |
| Validar el flujo incompleto | Solo «Prompt 1: missing template» y «Output 1: missing destination name»; la caja y el Sampling son válidos. |
| Prompt de texto con Gemini 3.5 Flash-Lite y Output «Save to conversation fields» → Summary | «The flow is valid». |
| Guardar y recargar | El lienzo se reconstruye idéntico. |
| Ejecutar con «Today» (13/10, sin conversaciones en la cuenta) | La caja consulta Genesys (log: «Chunk 1/1 (13/10/2026 00:00 – 13/10/2026 20:59 (Europe/Madrid)): 0 conversations»), queda en OK con 0 encontradas, y Sampling, Prompt y Output quedan «Skipped» con «The download returned no conversations». Ejecución OK en 2,2 s, sin llamar al LLM. |
| Programar cada 1 hora y volver al listado | «Next run: Oct 13, 10:00 PM». |
| Historial | Columna «Origin» con «Manual». |
| Ejecutar con «Yesterday» y «Overwrite» (decisión de la persona usuaria, que aceptó borrar el análisis del LLM de las 13 conversaciones del 12/10) | La caja pasa por «Running» con los contadores creciendo (1 → 5 → 13 de 13) mientras el resto espera; descarga «With warnings» (13 encontradas, 13 guardadas). Sampling 13, Prompt 13/13, Output: 11 escritas y 2 rechazadas («The conversation has no transcript: it is not sent to the LLM», las dos llamadas sin transcripción). Ejecución OK en 29,4 s. |
| Abrir una conversación desde la tabla | El detalle muestra el summary nuevo de Gemini y «Back to the run»; el resto del análisis queda «Pending» porque «Overwrite» lo borró. |
| Ver el log de la descarga desde la ejecución | Se abre el visor de log con las entradas de búsqueda, descarga, normalización, análisis y carga. |
| Consola del navegador y logs de la API y la ingesta | Sin errores de consola desde que se empezó a capturar (a mitad del recorrido) y sin errores ni trazas en `.dev-logs/api.log` ni `.dev-logs/ingestion.log`. |

### No cubierto en el navegador

- **Solo lectura con `flows:view`:** ningún usuario demo tiene solo ese permiso; lo cubren `DownloadBox.test.tsx` (panel deshabilitado) y `test_flow_scheduler.py` (`403` al guardar y ejecutar).
- **Ejecución programada real:** antes de llegar a las 22:00 se volvió a «Manual only» para que el programador no repitiera la descarga con «Overwrite». La cubre `test_flow_scheduler.py` con reloj simulado.

### Observaciones

- **Cosmético, anterior a FE017:** el resumen de filtros de un Sampling detrás de la caja dice «All conversations in the period», aunque detrás de la caja no hay periodo.
- **Cosmético, anterior a FE017:** la tarjeta «Data origin» de Configuración sigue diciendo que el origen «se pierde al reiniciar la API», cuando FE015 ya lo persiste.
- **Incidencia de la prueba:** al parar el entorno de prueba, `dev.sh` paró el contenedor de PostgreSQL que compartía con el entorno de la persona usuaria (otro `dev.sh` en 8000/8001/5173). Se volvió a levantar en el momento con `docker compose up -d --wait postgres`; el volumen se conservó.

## Cobertura de los criterios de aceptación

| Criterio | Evidencia |
|---|---|
| 1. Caja: configuración, rangos, `422` con ruta, ida y vuelta | `test_flow_download_node.py` (`test_the_box_round_trips`, `test_invalid_box_values_are_rejected_with_their_path`) |
| 2. Reglas de conexión y una caja por flujo | `rules.cases.json` en `test_flow_rules.py` y `rules.test.ts`; `test_a_flow_has_at_most_one_box`, `test_the_box_only_feeds_a_sampling_when_saving` |
| 3. Validación: incompleta, suelta, origen real, ingesta caída, flujos sin caja igual | `test_flow_download_node.py`; `test_validation_fails_when_the_ingestion_service_is_down`; suites de FE004–FE014 sin cambios en verde |
| 4. Orden: nada empieza antes de que termine la descarga | `test_no_other_node_starts_before_the_download_ends`; recorrido en Chrome |
| 5. Progreso de la caja y enlace al log | `test_the_box_downloads_and_the_sampling_only_sees_its_subset`, `test_the_download_and_its_log_are_readable_from_the_run`, `RunDownload.test.tsx`; Chrome (1 → 5 → 13 de 13) |
| 6. Fin de la descarga: ok, con avisos, error, vacía (`omitido`, sin LLM) | `test_a_failed_download_stops_the_flow`, `test_a_download_with_warnings_lets_the_flow_continue` (añadido en `/test`), `test_a_download_without_conversations_skips_the_rest_without_calling_the_llm`, `test_the_ingestion_service_falling_mid_run_ends_in_error`; Chrome con «Today» |
| 7. Sampling solo sobre el subconjunto, sin fechas, con sus condiciones, método y tamaño | `test_the_sampling_conditions_still_apply_to_the_subset`, `test_behind_the_box_the_sampling_keeps_its_method_and_size` (añadido), `test_flow_end_to_end_pg.py` (8 nuevas frente a 2 ya guardadas) |
| 8. Concurrencia: `409` y descargas a la vez | `test_one_active_download_per_box` (ingesta); `409` de ejecución de FE004 sin cambios |
| 9. Programación | `test_flow_scheduler.py` (cada hora, diaria, omitida con nota, inactiva, reinicio, error de validación, `next_run`); Chrome («Next run») |
| 10. «All conversations», `large_sample`, estimación | `test_flow_sampling_all.py`; `DownloadBox.test.tsx` |
| 11. Compatibilidad con flujos guardados | `test_a_saved_sized_graph_still_draws_the_same_sample` y suites de FE004 |
| 12–15. Front: paleta, panel, conexiones, Sampling, ejecución e historial | `DownloadBox.test.tsx`, `RunDownload.test.tsx`; Chrome |
| 16. Textos `es`/`en` | test de paridad de i18n (ADR-010) en verde con las claves nuevas |
| 17. Solo lectura sin `flows:edit` | `DownloadBox.test.tsx › sin flows:edit…` |
| 18. Permisos y OpenAPI | `test_a_view_only_role_cannot_schedule_nor_run`, `test_a_view_only_role_reads_the_download_of_a_run` (añadido), `test_openapi.py` (rutas nuevas con respuesta real) |
| 19. Sin secretos | `test_the_log_is_readable_and_has_no_secrets` (ingesta) y `test_flow_end_to_end_pg.py` (ejecución, descarga y log en texto, reforzado en `/test`) |
| 20. Gate | ver «Gate» |
| 21. Recorrido en Chrome | sección anterior |

## Mutaciones (¿fallarían los tests si se rompe el comportamiento?)

Cada mutación se aplicó a mano, se ejecutaron los tests indicados y se restauró el fichero (sin cambios en `git status` al terminar).

| Mutación | Tests | Resultado |
|---|---|---|
| El Sampling detrás de la caja no quita el intervalo de fechas | `test_flow_end_to_end_pg.py` | **Detectada** (1 fallo) |
| El Sampling usa todo el dataset en vez del subconjunto | `test_flow_end_to_end.py` | **Detectada** (3 fallos) |
| Sin estado `omitido` con subconjunto vacío | `test_flow_end_to_end.py` | **Detectada** |
| El programador no espera a la hora | `test_flow_scheduler.py` | **Detectada** (3 fallos) |
| El programador no recuerda la última vez | `test_flow_scheduler.py` | **Detectada** (2 fallos) |
| La caja admite varias salidas | `test_flow_rules.py` | **Detectada** |
| La caja no exige el origen real | `test_flow_download_node.py`, `test_flow_scheduler.py` | **Detectada** (2 fallos) |
| Sin `begin_request()` tras la descarga | `test_flow_end_to_end_pg.py` | **Sobrevivía**: en los tests cada petición HTTP ya recarga la instantánea. Se añadió `test_the_real_data_snapshot_is_refreshed_after_the_download`, que la detecta. |
| El subconjunto incluye las conversaciones `omitida` de `load` | `test_insight_downloads_pg.py` | **Sobrevive (mutante equivalente en la práctica):** el ejecutor ya salta las existentes antes de descargarlas; `load` solo devuelve `omitida` en una carrera entre dos descargas. Se acepta. |

## Fuentes (grounding)

- **Pydantic, validadores `before`:** se ejecutan antes de la validación interna y lo que devuelven se valida contra la anotación ([Pydantic · Validators](https://pydantic.dev/docs/validation/latest/concepts/validators/)). Es lo que permite dar un único error en `nodes[i].config.size` y conservar en el OpenAPI la unión `integer | "all"` (T3).
- **PostgreSQL, índices únicos y `NULL`:** «By default, null values in a unique column are not considered equal» ([PostgreSQL · Unique Indexes](https://www.postgresql.org/docs/current/indexes-unique.html)). Por eso el índice único de FE011 sobre `download_run.flow_id` admite varias descargas de caja con `flow_id` nulo, y la de la caja necesita su propio índice parcial sobre `insight_flow_id` (T1).
- **FastAPI, tareas en segundo plano:** se ejecutan después de enviar la respuesta ([FastAPI · Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)). La documentación del `TestClient` de Starlette no dice cuándo las ejecuta. Comprobado en el código instalado (Starlette 1.7.0, `starlette/responses.py`): `Response.__call__` hace `await self.background()` tras enviar el cuerpo, así que el `TestClient` no devuelve el control hasta que terminan. En eso se apoyan los tests de la API que leen la ejecución terminada justo después del `POST`.
- **React Flow, tipos de nodo:** se registran en `nodeTypes` ([React Flow · Custom Nodes](https://reactflow.dev/learn/customization/custom-nodes)). La documentación no dice qué pasa con un tipo sin registrar. El código instalado (`@xyflow/system` 12.12.0, `error003`) usa el tipo `default`: «Node type "…" not found. Using fallback type "default".» Respalda la corrección de T6, que se dedujo del código y no se vio en el navegador antes de corregirla.
- **jest-dom, `toBeDisabled`:** considera deshabilitado un control dentro de un `fieldset` deshabilitado ([jest-dom · toBeDisabled](https://github.com/testing-library/jest-dom#tobedisabled)). Es como se prueba la solo lectura del panel de la caja.

## Log de duda

1. **CLAIM:** el Sampling ve las conversaciones recién descargadas. **ASUNCIÓN:** la instantánea de los datos reales se recarga tras la descarga. **DUDA:** solo se comprueba una vez por petición HTTP, y una ejecución programada no tiene petición. **EVIDENCIA:** la mutación que quita `begin_request()` sobrevivía; el test nuevo verifica el orden descarga → `begin_request` → Sampling. En Chrome, el Sampling recibió las 13. **STOP:** cubierto.
2. **CLAIM:** una ejecución programada no se lanza dos veces. **ASUNCIÓN:** un solo proceso de API. **DUDA:** con varios workers de uvicorn, cada uno tendría su programador y sus ejecuciones en memoria. **EVIDENCIA:** `dev.sh` y el README arrancan un solo proceso sin `--workers`; la spec lo deja como asunción. **STOP:** riesgo documentado para `/review`; fuera de alcance.
3. **CLAIM:** si la ingesta cae a mitad de la descarga, la ejecución no queda colgada. **DUDA:** ¿y si la ingesta sigue viva pero su descarga se queda en `en_curso` para siempre? **EVIDENCIA:** el ejecutor de la ingesta marca `error` ante cualquier excepción, y al reiniciar `interrupt_active_runs` pasa las activas a `error`; el sondeo de la API termina con ese estado. Un fallo de red al sondear acaba en `error` (`test_the_ingestion_service_falling_mid_run_ends_in_error`). **STOP:** un corte transitorio de una sola consulta termina la ejecución en error en lugar de reintentar; aceptable en el piloto y anotado para `/review`.
4. **CLAIM:** «Sobrescribir» en la caja no toca el análisis de conversaciones ajenas al intervalo. **EVIDENCIA:** usa el mismo `load` que FE013 y solo sobre lo descargado; en Chrome, solo cambiaron las 13 del 12/10. **STOP.**
5. **CLAIM:** el listado de flujos no se vuelve lento con «All conversations». **DUDA:** `Flow.status()` valida cada flujo al listar, y `large_sample` cuenta candidatos con el motor de consultas. **EVIDENCIA:** con el dataset completo, una consulta del explorador tarda menos de 500 ms (tests de rendimiento de la arquitectura) y solo cuenta en Samplings sin caja con «All conversations». **STOP:** coste aceptable; mejora posible (caché) para `/review`.

## Bugs encontrados

| Bug | Causa raíz | Corrección y test de regresión |
|---|---|---|
| (T1) `insight_flow_id` rompía el contrato cerrado de `DownloadRun` de FE011 | Se añadía a todas las descargas | Solo en las de caja; `test_the_whole_chain_matches_the_documented_schemas` |
| (T3) Un `size` no válido daba errores en `size.constrained-int` y `size.literal['all']` | Unión de Pydantic | Validador `before`; tests de rangos de FE004 (lección 48) |
| (T6) La caja se pintaba con el nodo `default` de React Flow | Faltaba registrarla en `nodeTypes` | Registrada; `DownloadBox.test.tsx` |
| (`/test`) La instantánea podía no recargarse en ejecuciones programadas sin `begin_request` | Ver duda 1 | `test_the_real_data_snapshot_is_refreshed_after_the_download` |
| (`/test`) El test de secretos de la API comprobaba una cadena que nunca podía aparecer | Test débil | Sustituido por la comprobación con el secreto y los tokens reales del Genesys falso en `test_flow_end_to_end_pg.py` |

## Gate

- **Auditoría del vault:** `python scripts/audit_vault.py` → código 0, «58 archivos revisados, 0 errores».

- `python scripts/audit_vault.py`: 58 archivos, 0 errores.
- Backend: 1231 tests (dos semillas) y 203 tests con PostgreSQL, en verde.
- Front: en la primera pasada de `./scripts/ci.sh` falló `ConversationsPage.test.tsx › muestra los filtros activos como chips eliminables` (el chip mostraba el código `cajeros` en vez de «Incidencia en cajero»: carrera con la carga del catálogo). FE017 no toca esa página y el test pasó 3 de 3 por separado.
- **Segunda pasada de `./scripts/ci.sh`: código 0.** Vault, backend (1231 + 1231 con otra semilla + 203 con PostgreSQL), OpenAPI al día, front (597 tests, lint y build) y auditoría de dependencias.
- **`/test`, tras añadir los tests: `./scripts/ci.sh` → código 0.** Backend 1234 tests (dos semillas) y 203 con PostgreSQL; OpenAPI al día; front 47 ficheros y 597 tests, lint y build; auditoría de dependencias sin hallazgos.

# FE013 — Verificación

> Fase `/test`. Spec: [spec.md](spec.md) · Plan y evidencia por tarea: [plan.md](plan.md). Siguiente paso: `/review`.

## Resultado

**Verificada.** Los 31 criterios de la spec tienen evidencia: tests que fallan si se rompe el comportamiento (30 mutaciones detectadas de 30), una comprobación contra la API real de Gemini y dos recorridos en Chrome. La verificación encontró **cuatro defectos**, todos corregidos con su test de regresión (ver «Defectos»). Quedan sin probar contra sus APIs reales los adaptadores de OpenAI y Anthropic (no hay claves): verificados solo contra su documentación.

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `./scripts/ci.sh` | **Código 0** el 2026-10-12 |
| `python scripts/audit_vault.py` | **Código 0**: 54 archivos, 0 errores (sin hallazgos) |
| Backend sin PostgreSQL, dos datasets (FE009) | **1030 passed** y 1030 passed |
| Backend con PostgreSQL (`REQUIRE_PG=1`) | **149 passed** |
| Front (`npm test`, lint, build) | **402 passed** (36 ficheros); lint y build sin errores |
| OpenAPI | Al día y válido (72 operaciones; las 2 rutas nuevas recorridas por el test de contrato) |
| `pip-audit` / `npm audit --audit-level=high` | Sin vulnerabilidades / 0 «high»; siguen las 4 «moderate» de `sprintf-js` anteriores a FE013 |
| Mutaciones de backend | **27 de 27 detectadas**: validación por formato y valores permitidos, temperatura, transcripción vacía, códigos que detienen el nodo, `overwrite` y lotes del Output, traducción a código del main topic, exclusión de conversaciones sin resultado, reglas (destino repetido, solo datos reales, proveedor sin clave, texto libre para summary), reintentos y semáforo del servicio, clave rechazada de Gemini y de los proveedores, respaldo de Anthropic, cliente de LLM, escritura (solo vacíos, `FOR UPDATE`), carga (`OMITTED`, borrado de `llm_meta`), omisión de existentes y copia de «Sobrescribir» en la ejecución, lectura de summary con análisis pendiente y protección de la taxonomía |
| Mutaciones de front | **3 de 3 detectadas**: opción «campo» con datos sintéticos, aviso de pendiente del detalle y envío de `overwrite` del flujo de descarga |
| Gemini real (`gemini-3.5-flash-lite`) | Prueba de proveedor, etiqueta, JSON con `enum` de 15 main topics y un flujo de 3 conversaciones desde la API: correctos (T5, T6 y T9 del plan) |

Script de mutaciones: aplica cada cambio, ejecuta los tests indicados con `python -B` y `PYTHONDONTWRITEBYTECODE=1` y restaura el fichero, como pide la sección «Aprendizaje» de las [lecciones](../../vault/aprendizaje/lecciones-construccion-plataforma.md); `git status` limpio al terminar.

## Trazabilidad de los criterios

| Criterio | Evidencia |
|---|---|
| 1–3 Servicio, claves aisladas, token | `test_llm_service.py` (health, 401 con tres cabeceras, clave nunca en respuestas ni logs), `test_llm_settings.py` (lista blanca, estructural de importaciones y de nombres de clave) |
| 4–5 Proveedores intercambiables | `test_llm_providers.py` (contrato del registro, petición y respuesta por proveedor), `test_llm_flows.py::test_the_llm_service_registry_matches_the_api_catalog`, Gemini real |
| 6–7 Errores, reintentos, concurrencia | `test_llm_service.py` (503, 502, 2 reintentos con esperas, pico ≤ N), `test_llm_providers.py::test_http_errors_are_classified`, `test_llm_edges.py` (cliente) |
| 8–10 Configuración y validación | `test_llm_flows.py` (catálogo, estado, «Probar», 503, permisos, proveedor sin clave, modelo ajeno, servicio caído), `ConfigPage.test.tsx`, `NodePanels.test.tsx`, Chrome (T7) |
| 11–14 Ejecución con el LLM | `test_llm_flows.py` (enrutado, enmascarado, formatos, clasificación de errores, paralelismo con cada fila en su conversación, nodo detenido) |
| 15–17 Output «campo», una llamada, reglas | `test_flow_fields.py`, `test_flow_fields_pg.py::test_a_one_call_flow_writes_both_fields_visible_in_the_next_request`, Gemini real con `enum` |
| 18 Editor | `FieldOutputPanel.test.tsx`, Chrome (T9) |
| 19–21 Escritura, trazabilidad, lectura | `test_flow_fields_pg.py` (vacío, sin y con `overwrite`, `status` intacto, concurrencia, lotes > 100 y valores vacíos), `ConversationDetailReal.test.tsx`, Chrome (T9) |
| 22 Resultado de la ejecución | `test_flow_fields.py::test_rejected_and_failed_conversations_appear_with_their_state`, `RunPage.test.tsx`, Chrome (T9) |
| 23 Plantillas | `test_flow_templates.py` (+3 con PostgreSQL), `test_llm_edges.py::test_the_main_topic_template_refuses_more_topics_than_labels`, `FlowsPage.test.tsx`, Chrome (T9) |
| 24 `dev.sh`, `.env.example`, gate | Arranque y parada por PID en puertos propios (T4, T7, T9), `ci.sh` con código 0 |
| 25 Navegador con Gemini | Chrome (T7 y T9 del plan) |
| 26–29 Ingesta «Sobrescribir» | `test_ingestion_overwrite.py` (9), `test_downloads_api.py::test_overwrite_reaches_the_service_when_creating_and_saving` |
| 30 Front de la ingesta | `DownloadFlows.test.tsx`, `DownloadRuns.test.tsx`, Chrome (abajo) |
| 31 Taxonomía protegida | `test_config_taxonomy_real.py` (5) |

## Defectos encontrados

| # | Defecto | Causa raíz | Corrección y test de regresión |
|---|---|---|---|
| 1 | Las conversaciones sin transcripción recibían un summary y un main topic **inventados** (distintos en cada ejecución; 2 en la base de desarrollo) | El runner enviaba al LLM una plantilla con `{{transcripcion}}` vacía; ningún test usaba una conversación vacía | Se rechazan sin llamar al LLM si la plantilla usa `{{transcripcion}}` · `test_a_conversation_without_transcript_is_rejected_without_calling_the_llm` y el test de integración con PostgreSQL |
| 2 | El aviso de análisis pendiente del detalle decía que el summary y el main topic llegarían más tarde aunque ya estaban | El texto de FE012 suponía que con el análisis pendiente no había ninguno de los dos | Solo nombra lo que falta · `ConversationDetailReal.test.tsx` |
| 3 | `POST /analysis/fields` aceptaba un valor vacío, que dejaba el campo «escrito» y vacío | Sin restricción de longitud mínima | `StringConstraints(strip_whitespace=True, min_length=1)` · `test_a_batch_over_one_hundred_or_an_empty_value_is_refused` |
| 4 | El historial de descargas decía «omite las conversaciones que ya existen» en ejecuciones anteriores a FE013, que las habían actualizado | La migración `0003` puso `false` por defecto también en las ejecuciones antiguas | Migración `0005` (modo desconocido, `NULL`) y la página no afirma modo · `test_runs_from_before_overwrite_existed_have_an_unknown_mode`, `DownloadRuns.test.tsx` |

Además, durante T5 la comprobación contra Gemini real destapó que la forma REST de su guía para JSON responde `400` ([plan](plan.md), notas de T5), y en T9 se estabilizó un test del listado que buscaba una fila sin esperarla.

## Grounding (documentación oficial)

- **Gemini:** [Generating content](https://ai.google.dev/api/generate-content) (endpoint, `x-goog-api-key`, `finishReason`, `promptFeedback.blockReason`), [Structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output) y [Modelos](https://ai.google.dev/gemini-api/docs/models). La forma JSON de la guía falla en runtime; la usada (`responseMimeType` + `responseJsonSchema`) se **comprobó en runtime**, también con `enum`.
- **OpenAI:** [Create chat completion](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create) y [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs): `enum` en strings admitido; en modo estricto, todos los campos en `required` y `additionalProperties: false` (lo cumple `json_schema` de `app/flows/llm_runner.py`). [Modelos](https://developers.openai.com/api/docs/models): no confirma `temperature` → no se envía.
- **Anthropic:** [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) (`output_config.format` con `json_schema`; `enum` de strings admitido; `additionalProperties: false`) y [Refusals and fallback](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback) (`fallbacks: "default"` con la beta `server-side-fallback-2026-07-01`; Haiku 5.5 sin respaldo en el servidor). Que los modelos vigentes rechazan `temperature`: guía de la Messages API (skill `claude-api`, caché del 2026-10-06).
- **PostgreSQL:** [SELECT · cláusula de bloqueo](https://www.postgresql.org/docs/current/sql-select.html): `FOR UPDATE` bloquea las filas frente a actualizaciones concurrentes y, sin `NOWAIT` ni `SKIP LOCKED`, otra transacción espera. Comprobado con 8 escrituras simultáneas (una «escrito», siete «omitido») y con la mutación que quita el bloqueo.
- **Sin fuente accesible:** la documentación de TanStack Query sobre el refresco en segundo plano respondió `500`. Solo afecta a la nota del entorno de Chrome (ventana oculta), no a una decisión de la feature.

## Rutina de duda

- **CLAIM:** «summary y main topic en una sola llamada». **Asunción:** los tres proveedores admiten `enum` en la salida estructurada. **Duda:** Gemini cambia su forma JSON y ninguna prueba sin red lo ve. **Evidencia:** documentación de OpenAI y Anthropic; Gemini real con `enum` de 15 topics; test de una llamada por conversación. **STOP.**
- **CLAIM:** «sin «Sobrescribir» nunca se toca lo que escribió el LLM». **Asunción:** la comprobación de existencia y la escritura no compiten. **Duda:** dos ejecuciones o dos flujos a la vez. **Evidencia:** `load(..., overwrite=False)` devuelve `OMITTED` si otra ejecución inserta antes (test y mutación); `FOR UPDATE` serializa escrituras del mismo campo (test con 8 hilos y mutación). **STOP.**
- **CLAIM:** «la redescarga con «Sobrescribir» borra lo del LLM». **Duda:** ¿y la trazabilidad? **Evidencia:** `llm_meta` vuelve a `{}` (test con PostgreSQL y mutación). **STOP.**
- **CLAIM:** «un summary del LLM es un resumen de la conversación». **Duda:** con la transcripción vacía no hay nada que resumir. **Evidencia:** en Chrome, el summary guardado y el recién generado de la misma conversación no coincidían → **defecto 1**, corregido. **STOP.**
- **CLAIM:** «el historial de descargas cuenta lo que pasó». **Duda:** ejecuciones creadas antes de existir la columna. **Evidencia:** en Chrome, «omite» junto a «13 actualizadas» → **defecto 4**, corregido. **STOP.**
- **CLAIM:** «las claves no salen del servicio de LLM». **Duda:** logs de `httpx`, mensajes de error del proveedor. **Evidencia:** la clave va en cabeceras, nunca en la URL; los errores no repiten el cuerpo del proveedor (test con la clave ficticia en el cuerpo de error); logs de las pruebas reales revisados sin la clave. **STOP.**
- **CLAIM:** «los adaptadores de OpenAI y Anthropic funcionan». **Asunción:** la documentación describe la API real. **Duda:** con Gemini la guía falló. **Evidencia insuficiente:** no hay claves. **Queda como hipótesis** en [ADR-009](../../vault/decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md); probar con «Probar» en cuanto haya clave.

## Recorrido en Chrome (criterio 30)

Contra `dev.sh` completo en puertos propios (18000–18002 y 15173), sin ejecutar ninguna descarga: el formulario del flujo «Descarga de hoy» muestra «Sobrescribir» desmarcado con su ayuda; la ejecución programada de las 16:00 muestra «Ya existentes (no descargadas) 0» junto al resto de contadores. Ese recorrido destapó el defecto 4. Los recorridos de los criterios 9, 18 y 21–25 están en el [plan](plan.md) (notas de T7 y T9).

**No comprobado en el navegador** (cubierto por tests): marcar «Sobrescribir» y ejecutar una redescarga real (borraría los summaries de la base de desarrollo).

## Pendiente fuera de esta fase

- **Hecho (2026-10-12, a petición de la persona usuaria):** se vaciaron el summary, el main topic y `llm_meta` de las 2 conversaciones sin transcripción de la base de desarrollo (`1CO-19947E2F…` y `1CO-CD1101BD…`), con la condición de que siguieran sin turnos. Las otras 11 conservan lo que generó el LLM.

## Gate

`./scripts/ci.sh` terminó con código 0 el 2026-10-12.

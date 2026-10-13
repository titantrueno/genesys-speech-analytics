# FE014 — Verificación

> Fase `/test` (2026-10-13). Veredicto: **PASA**. Los 17 criterios tienen evidencia; 29 de 29 mutaciones mueren; `./scripts/ci.sh` termina con código 0. Un hallazgo corregido en esta fase (la plantilla no admitía los 40 campos que promete) y dos en el recorrido de `/build` T8.

## Evidencia de la batería

| Comando | Resultado |
|---|---|
| `./scripts/ci.sh` | **Código 0.** Vault: 55 archivos, 0 errores. Backend: 1.143 tests en verde, también con la semilla 7 y la fecha de referencia 2026-11-10; 189 con PostgreSQL. OpenAPI al día y válido. Front: 411 tests, lint y build en verde. |
| `python scripts/audit_vault.py` | **Código 0**, 55 archivos revisados y 0 errores; sin enlaces rotos, metadatos incompletos, entradas huérfanas ni posibles secretos. |
| `npm audit --audit-level=high` / `pip-audit` | 0 vulnerabilidades «high» / ninguna conocida. Siguen las 4 «moderate» de `sprintf-js`, anteriores a FE013. |

## Cobertura de los criterios de aceptación

| Criterio | Evidencia |
|---|---|
| 1. Catálogo de destinos | `test_flow_targets.py`: los destinos agrupados, un `compliance:` por check activo, la desaparición al desactivarlo y los mismos tipos de entidad que el servicio de ingesta. |
| 2. Tipo «lista» | `test_flow_targets.py`: ida y vuelta, `array`/`items.enum` enviado al LLM y respuestas no válidas rechazadas. Gemini real (plan, notas de T2). |
| 3. 40 campos | `test_forty_fields_fit_and_forty_one_do_not`; la plantilla con 27 checks llega exactamente a 40 (`test_the_full_template_fits_exactly_the_maximum_number_of_checks`). |
| 4 y 5. Validación por campo, rangos en la API | `test_flow_field_values.py`: un caso por regla con sus límites; `test_one_invalid_field_is_rejected_and_the_rest_are_written`; `NaN`/`Infinity` en `test_fe014_edges.py`. |
| 6–8. Reglas del editor | `test_each_target_needs_a_json_field_of_its_type` (14 casos), `test_a_deleted_or_deactivated_check_blocks_the_run` y `test_duplicates_and_simulated_values_also_apply_to_new_targets`. |
| 9–11. Escritura | `test_analysis_fields_pg.py`: cada familia con y sin «Sobrescribir», combinación clave a clave, sentimiento con y sin Genesys y redescarga; concurrencia en `test_fe014_edges.py`. |
| 12. Lectura campo a campo | `test_real_partial_analysis.py` (10 tests con PostgreSQL), y en el front `ConversationDetailReal.test.tsx` y `DashboardsReal.test.tsx`. |
| 13. Plantilla | `test_flow_template_full.py`, incluida una ejecución que escribe todos los campos en PostgreSQL. |
| 14 y 15. Front de flujos | `RunPage.test.tsx`, `FieldOutputPanel.test.tsx` y `FlowsPage.test.tsx`. |
| 16. Navegador con Gemini | Recorrido de abajo. |
| 17. Gate y OpenAPI | `ci.sh` con código 0; `test_every_flow_issue_code_is_documented` y `test_field_states_and_pending_checks_are_documented`. |

## Pruebas de mutación

Script en el *scratchpad* de la sesión: aplica cada mutación, ejecuta los tests de FE014 y FE013 relacionados (con PostgreSQL) o `vitest`, y restaura el fichero. Primera pasada: **26 de 29 muertas**. Las 3 vivas revelaron huecos que ahora cubre `test_fe014_edges.py`; segunda pasada: **29 de 29 muertas**.

| Mutación | Test que la mata |
|---|---|
| M01 rangos exclusivos (`<` en lugar de `<=`) | `test_valid_values_are_stored_normalized[csat-1-1.0]` |
| M02 sin máximo de 10 palabras clave | `test_valid_values_are_stored_normalized[keywords-…]` |
| M03 temas secundarios duplicados | `test_secondary_topics_are_stored_by_code_without_duplicates` |
| M04 `coerce` acepta un check desactivado | **Viva en la primera pasada** → `test_a_check_deactivated_during_the_run_is_rejected` |
| M05 la ingesta ignora «Sobrescribir» | `test_each_field_is_written_kept_and_overwritten[resolution]` |
| M06 `compliance = %s` sin combinar | `test_checks_are_merged_key_by_key` |
| M07 el LLM pisa el sentimiento de Genesys | `test_sentiment_is_not_written_when_genesys_gives_it` |
| M08 `[]` no cuenta como vacío | `test_an_empty_list_counts_as_empty` |
| M09 el resultado guardado no manda en los personalizados | `test_a_custom_check_uses_the_llm_result_over_its_phrases` |
| M10 caché de checks solo por identificador | `test_a_custom_check_uses_the_llm_result_over_its_phrases` |
| M11 `has_compliance` cuenta checks de otro canal | **Viva** → `test_a_conversation_whose_checks_do_not_apply_does_not_count_for_compliance` |
| M12 un periodo vacío sale «pendiente» | **Viva** → `test_an_empty_period_is_not_pending` |
| M13 FCR sobre todas las conversaciones | `test_a_kpi_is_computed_on_the_conversations_that_have_its_field` |
| M14 el sentimiento del LLM antes que el de Genesys | `test_the_sentiment_is_genesys_first_then_the_llm` |
| M15 un campo vacío cumple condiciones | `test_a_check_is_empty_only_while_it_is_pending` |
| M16 sin estado `sin_valor` | `test_one_invalid_field_is_rejected_and_the_rest_are_written` |
| M17 resolución sin valores permitidos aceptada | `test_each_target_needs_a_json_field_of_its_type[…resolution]` |
| M18 un check desactivado no bloquea | `test_a_deleted_or_deactivated_check_blocks_the_run` |
| M19 el desglose por main topic sigue «pendiente» | `test_the_breakdown_says_which_kpis_are_still_pending` |
| M20 una lista con números pasa | `test_a_wrong_list_answer_is_rejected[…3…]` |
| M21 «Sobrescribir» no vacía `sentiment` | `test_redownloading_with_overwrite_erases_the_new_fields` |
| M22 la plantilla sin los checks en el Sampling | `test_the_sampling_takes_conversations_with_any_empty_field` |
| M23 entidades del objeto no leídas | `test_the_detail_shows_each_field_as_soon_as_it_exists` |
| M24 `pending` solo si falta todo | `test_the_detail_shows_each_field_as_soon_as_it_exists` |
| F01 sin grupo «Temas» en la tabla | «el análisis completo agrupa los campos…» |
| F02 KPI pendiente con el `pending` global | «el desglose por main topic se pinta…» |
| F03 check pendiente mostrado como «No aplica» | «el cumplimiento dice el resultado de cada check…» |
| F04 campo de origen sin filtrar por tipo | «cada destino ofrece solo los campos del JSON de su tipo» |
| F05 métrica que falta como «—» | «con el análisis pendiente lo dice en lugar de mostrar ceros» |

## Grounding: fuentes oficiales

| Decisión | Fuente | Lo que dice |
|---|---|---|
| Rangos y máximo de palabras clave en la API, no en el esquema | [Anthropic · Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | No admite `minimum`, `maximum` ni restricciones de listas más allá de `minItems` 0 o 1; `enum` de cadenas y `array` de `string`, sí. Una función no admitida da `400`. |
| `array` de `string` con `enum` en Gemini | [Gemini · Structured output](https://ai.google.dev/gemini-api/docs/structured-output) | `array` con `items` y `enum` de cadenas admitidos; «Very large or deeply nested schemas may be rejected», sin límites numéricos. Comprobado con la API real (abajo). |
| Lo mismo en OpenAI (modo estricto) | [OpenAI · Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), «Supported schemas» | `enum` y `array` admitidos; como mucho 1.000 valores de `enum` por esquema y 5.000 propiedades. La plantilla usa unos 73 valores (15 main topics, 34 temas, 3 + 3 + 3 por check). |
| Combinación clave a clave de `compliance` y `entities` | [PostgreSQL · JSON functions](https://www.postgresql.org/docs/current/functions-json.html), operador `jsonb ‖ jsonb` | Une las claves de dos objetos y, si se repiten, gana el segundo; no es recursivo. |
| `coalesce(columna, '{}')` antes de `‖` | Comprobado en PostgreSQL 16.15 | `'{"a":1}' ‖ NULL` y `NULL ‖ '{"a":1}'` dan `NULL` (la documentación no lo dice); `'{"b":2}' ‖ '{"b":null}'` conserva la clave con `null`, que es lo que hace de «no aplica» un valor. |
| Bloqueo de la fila de `analysis` y no de `conversation` | [PostgreSQL · SELECT](https://www.postgresql.org/docs/current/sql-select.html), «The Locking Clause» | Con `FOR UPDATE OF tabla`, solo se bloquean las filas de esa tabla; las demás del `JOIN` se leen sin bloquear. |

## Registro de dudas

- **CLAIM:** «La plantilla admite hasta 27 checks: 40 campos menos los 13 fijos».
  - **Asunción:** el único límite es `MAX_FIELDS`.
  - **Duda:** las instrucciones van en la plantilla, limitada a 4.000 caracteres (`MAX_TEMPLATE`).
  - **Evidencia:** con 27 checks de descripción vacía, `POST /api/flows` respondía `422` («no caben en un prompt»).
  - **Reconciliación:** **bug**; ver «Hallazgo de /test».
  - **STOP:** corregido, con test del límite exacto.
- **CLAIM:** «Un error de forma en un campo no tumba la respuesta entera».
  - **Asunción:** `validate_answer` solo comprueba tipos y `coerce` el resto.
  - **Duda:** `json.loads` acepta `NaN` e `Infinity`.
  - **Evidencia:** `validate_answer` los deja pasar como número y `coerce` los rechaza, campo a campo (`test_a_non_finite_number_passes_the_format_but_is_rejected_by_its_target`).
  - **STOP.**
- **CLAIM:** «La combinación por clave no pierde escrituras simultáneas».
  - **Asunción:** `FOR UPDATE OF a` serializa.
  - **Duda:** dos ejecuciones distintas escriben checks distintos en la misma conversación a la vez.
  - **Evidencia:** 8 hilos con 8 checks distintos dejan los 8 en `compliance` y en `llm_meta` (`test_simultaneous_writes_of_different_checks_keep_all_of_them`). La documentación de PostgreSQL respalda el bloqueo.
  - **STOP.**
- **CLAIM:** «El resultado guardado manda».
  - **Asunción:** por encima de todo.
  - **Duda:** ¿y si el check no aplica al canal de la conversación?
  - **Reconciliación:** decisión de `/build` T4: el canal configurado manda (Configuración es la fuente de verdad del alcance del check). Ahora tiene test (`test_a_check_that_does_not_apply_to_the_channel_is_not_applicable_even_with_a_stored_result`) y consta en ADR-007.
  - **STOP.**
- **CLAIM:** «Compactar las instrucciones de los checks no empeora las respuestas».
  - **Duda:** la frase «cumple, no_cumple o no_aplica» deja de ir en cada línea.
  - **Evidencia:** Gemini real con la plantilla nueva sobre 3 conversaciones sintéticas: 0 rechazos. Coinciden con las etiquetas del generador 17 de los 18 resultados de checks; antes del cambio, 16 de 18.
  - **Reconciliación:** sin regresión observable. La muestra es pequeña: es un indicio, no una medida de calidad.
  - **STOP.**
- **CLAIM:** «OpenAI y Anthropic aceptan el esquema».
  - **Evidencia:** solo su documentación (tabla de fuentes); sin claves no se ha probado.
  - **Reconciliación:** se mantiene como **hipótesis** en ADR-009.
  - **STOP:** no se puede verificar en este entorno.

## Hallazgo de /test: la plantilla no llegaba a 40 campos

- **Reproducción:** 6 checks base y 21 personalizados sin descripción; «Generar análisis completo» → `422`.
- **Localización:** `app/flows/templates.py`. Cada línea de check repetía «cumple, no_cumple o no_aplica si no corresponde en esta conversación» (unos 70 caracteres), y con 27 checks el prompt superaba `MAX_TEMPLATE`.
- **Arreglo:** la explicación de las respuestas de los checks va una sola vez en la instrucción general. El prompt por defecto baja de 2.329 a 1.996 caracteres. Con descripciones largas el `422` explicado sigue siendo el comportamiento correcto.
- **Blindaje:** `test_the_full_template_fits_exactly_the_maximum_number_of_checks` (en rojo antes del arreglo).

## Recorrido en navegador (criterio 16, `/build` T8, 2026-10-13)

**Entorno:** `./scripts/dev.sh` en los puertos 18000 (API), 18001 (ingesta), 18002 (LLM) y 15173 (web); PostgreSQL de desarrollo con 13 conversaciones reales del 12 de octubre (11 con transcripción, ninguna con resolución); Gemini con clave y `gemini-3.5-flash-lite`; usuario demo administrador; origen «Real (Genesys Cloud)».

| Paso | Resultado |
|---|---|
| «Nuevo flujo» → plantilla «Generar análisis completo» | El menú ofrece la plantilla. El flujo creado tiene Sampling (aleatorio, 12 filtros «está vacío»), Prompt (Gemini 3.5 Flash-Lite, JSON) y Output «Guardar en campos». |
| Panel del Output | 19 asignaciones; el desplegable de destino agrupa **Análisis (9), Cumplimiento (6) y Entidades (4)**. |
| Muestra de 3, «Guardar» y «Validar» | «13 conversaciones disponibles · muestra de 3»; «El flujo es válido.» |
| «Ejecutar» | Ejecución `ok` en 3,2 s, con 3 de 3 procesadas en cada nodo. |
| Recuentos por campo | Resolución, CSAT, esfuerzo, riesgo, los 6 checks y palabras clave: **3 escritos**. Temas secundarios y las 4 entidades: 2 escritos y 1 sin valor. Summary y main topic: 3 omitidos (ya los tenían de FE013). Sentimiento: 3 omitidos (Genesys ya lo da). **0 rechazados y 0 con error en todos los campos.** |
| Tabla de la ejecución | Cabecera de grupos: Análisis (7), Cumplimiento (6), Temas (2) y Entidades (4). La tabla (2.839 px) se desplaza dentro de su contenedor (1.551 px); la página no desborda (`scrollWidth` igual a `clientWidth`). |
| Detalle de `1CO-EA47555A-…` | Resultado: Escalada, CSAT 2,0 / 5, esfuerzo 3,0 / 5, riesgo Alto, sentimiento de Genesys. Cumplimiento: los 6 checks con Cumple, No cumple o No aplica. Temas secundarios: fraude, compras online y seguridad. Entidades: fecha, importe (58,32 euros), comercio y producto. 5 palabras clave. |
| Detalle de `1CO-889E6DFE-…` | La conversación con temas y entidades «sin valor» (llamada corta): Resultado y cumplimiento rellenos; sin secciones de temas ni de entidades. |
| Dashboard «Visión general» | Tasa de resolución, escalado, FCR y CSAT «Calculado sobre 3 conversaciones». Tras la corrección de abajo, la distribución por main topic muestra sus 2 grupos y la tabla «KPIs por main topic» da sus valores. |
| Consola del navegador | Sin errores. |

## Hallazgos del recorrido y correcciones

- **Desglose por main topic oculto:** el dashboard decía «Sin datos · pendiente de análisis» aunque 11 conversaciones ya tenían main topic. Causa: `breakdown.pending` seguía significando «a alguna conversación le falta análisis» y el front lo aplicaba a todo el gráfico. Ahora la respuesta lleva `pending_kpis` (los KPIs sin datos) y, por main topic, `pending` solo es `true` si ninguna conversación lo tiene. Hay un test de regresión en el backend (`test_the_breakdown_says_which_kpis_are_still_pending`) y otro en el front («el desglose por main topic se pinta…»). Comprobado de nuevo en el navegador.
- **Pestaña del Output de 432 caracteres:** el nombre era los 19 destinos unidos con «+». Ahora, con más de 3, lleva los dos primeros y «y N campos más». Test de regresión: `test_a_long_list_of_targets_gets_a_short_destination`.

## Notas

- OpenAI y Anthropic con el esquema de lista y la plantilla completa: sin claves, solo contrastados con su documentación (hipótesis de la spec).
- La base de desarrollo conserva lo que escribió el recorrido en 3 conversaciones, con su trazabilidad en `llm_meta` (ejecución `1RN-2305A807-…`).

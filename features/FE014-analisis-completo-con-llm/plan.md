# FE014 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-10-13. Siguiente paso: `/build`, una tarea cada vez y en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| [ADR-009](../../vault/decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md) (`active`), `app/flows/catalog.py` | `TARGET_FIELDS` es un `dict` fijo (`summary`, `main_topic`); `FieldMapping.target` es un `Literal` de esas claves y `OutputConfig.mappings` tiene `max_length=len(TARGET_FIELDS)`. | Los destinos `compliance:<código>` dependen de la configuración: `target` pasa a ser texto con patrón (`^(entity|compliance):[a-z0-9_]+$` o un destino fijo) y la existencia del check se comprueba en la completitud (criterio 7), no al guardar. El máximo de asignaciones pasa a una constante (`MAX_MAPPINGS = 60`). |
| `app/flows/model.py` (`SchemaField`) | Tipos `texto`, `numero`, `booleano`; `options` solo en `texto`; `MAX_FIELDS = 20`. | T2: tipo `lista` con `options` opcionales y `MAX_FIELDS = 40`. |
| `app/flows/llm_runner.py` | `_property` pone `enum` en los textos; `validate_answer` comprueba tipos y `options`. | T2: `{"type": "array", "items": {"type": "string", "enum"?}}` y validación de la lista (criterio 2). |
| `app/flows/rules.py` (`_mapping`, `_fields_output`) | Reglas de summary y main topic. | T3: una regla por familia de destino (criterio 6) y el check inexistente o desactivado (criterio 7). |
| `ingestion/analysis.py` (`write_fields`) | Lista blanca `COLUMNS` de dos columnas; «vacío» = `not current[t]`; `values: dict[Target, Value]` de textos. | T1: lista blanca de todas las columnas; valores tipados; combinación clave a clave de `compliance` y `entities`; regla del sentimiento de Genesys. |
| `ingestion/migrations/` | Hasta `0005`; `analysis` ya tiene `resolution`, `csat`, `effort`, `churn_risk`, `compliance`, `entities`, `keywords`, `secondary_topics` ([ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)). | T1: `0006_llm_sentiment.sql` con `analysis.sentiment real`. Con «Sobrescribir», `load` ya sustituye la fila entera de `analysis` y vacía `llm_meta` (FE013): el test del criterio 11 lo cubre con los campos nuevos. |
| `app/models.py` (`Entity`, `Analysis.entities: list[Entity]`) | La API expone las entidades como lista `{type, value}`. | En la base, `entities` se guarda como objeto `{tipo: valor}` (combinación clave a clave, criterio 9) y `real.py` lo convierte a la lista de siempre: el contrato de la API no cambia. |
| `app/data/real.py` (`_analysis`) | Solo lee el análisis si `status='completo'`; `pending = not done`; summary y main topic se leen siempre (FE013). | T4: todos los campos se leen siempre; el sentimiento es `customer_sentiment` o, si falta, `analysis.sentiment`. |
| `analysis.pending` en `services/kpis.py`, `config/compliance.py`, `query/engine.py`, `query/fields.py`, `services/filters.py`, `routers/conversations.py`, `routers/metrics.py` | Un booleano para todo el análisis. | T4: cada lector mira su propio campo. `pending` se mantiene como «falta algún campo del análisis» para el aviso del detalle y `analysis_pending` del listado. |
| `app/config/compliance.py` (`evaluate`) | Base: `analysis.compliance[código]`; personalizados: por frases; todo `None` si `pending`. | T4: resultado con cuatro estados (`cumple`, `no_cumple`, `no_aplica`, `pendiente`); la clave del LLM manda si existe (criterio 12; [ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md)). |
| `app/flows/templates.py`, `FlowsPage.tsx` | Tres plantillas de FE013 con `TEMPLATES`. | T5: `analisis_completo` («Generar análisis completo»). |
| [Arquitectura](../../vault/arquitectura/arquitectura-de-la-plataforma.md), [contrato de la API](../../vault/arquitectura/contrato-api-front-back.md), [runbook del servicio de LLM](../../vault/operaciones/runbook-servicio-llm.md), [catálogo de main topics](../../vault/producto/catalogo-de-main-topics.md) | `active`. | Se actualizan en T8. El catálogo de main topics no cambia. |
| [Lecciones](../../vault/aprendizaje/lecciones-construccion-plataforma.md), [registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md) | Tests independientes del dataset; sin prefijos nuevos. | No hay prefijos nuevos. Los tests consultan totales a la base o a la configuración, nunca valores fijos. |

## Decisiones de diseño

- **Catálogo de destinos** (`app/flows/catalog.py`):
  - `ANALYSIS_TARGETS` (fijos, con su etiqueta y familia): `summary`, `main_topic`, `resolution`, `csat`, `effort`, `churn_risk`, `sentiment`, `secondary_topics`, `keywords`.
  - `ENTITY_TYPES = ("importe", "producto", "fecha", "comercio")` → `entity:<tipo>`.
  - `target_fields(config)` añade `compliance:<código>` por check activo, con su nombre. `/api/flows/catalog` devuelve `target_fields` como lista `{value, label, group}` con `group` ∈ `analisis | cumplimiento | entidades`.
- **Validación de valores** (`app/flows/targets.py`, nuevo): `coerce(target, value, config) -> (valor_a_guardar | SIN_VALOR, None) | (None, motivo)`, una función pura por familia con las reglas del criterio 4. El Output la aplica por asignación antes de escribir, de modo que un rechazo afecta solo a ese campo. La completitud (criterio 6) reutiliza los mismos conjuntos de valores válidos.
- **Estados por campo** en el resultado del Output: `escrito`, `omitido`, `rechazado`, `sin_valor`, `error`, más `no_encontrada` por conversación. `omitido` lleva motivo: «Ya tenía valor» o «Genesys ya da el sentimiento».
- **Escritura** (`ingestion/analysis.py`):
  - `values: dict[str, str | float | list[str] | bool | None]`, con la clave validada contra la lista blanca y el patrón `compliance:`/`entity:`.
  - `SELECT … , c.customer_sentiment FROM analysis a JOIN conversation c … FOR UPDATE OF a`.
  - «Vacío»: escalar `NULL`; lista `NULL` o `[]`; `compliance:x` y `entity:x`, ausencia de la clave.
  - `compliance = coalesce(compliance, '{}') || %s` y lo mismo con `entities`: un solo `UPDATE` por conversación con todas las columnas y claves elegidas.
  - `llm_meta` por destino (`compliance:x`, `entity:x` incluidos).
- **Lectura** (`app/data/real.py`): `Analysis` se rellena siempre con lo que haya; `pending = True` si falta alguno de los campos del análisis (resolución, CSAT, esfuerzo, riesgo, summary, main topic). Cada consumidor decide con su propio campo:
  - KPIs: `resolution_rate`/`escalation_rate` sobre las que tienen `resolution`; `csat_avg`, `effort_avg`, `churn_high_pct` sobre las suyas; `compliance_rate` sobre las que tienen algún check con resultado; `based_on` para todos. `pending` del KPI es `based_on == 0` con datos reales.
  - **Decisión:** `fcr_rate` y `repeat_contact` no tienen campo del LLM; se calculan sobre las conversaciones con `resolution` (la misma base que la tasa de resolución). Así, sin nada escrito, siguen pendientes como en FE012.
  - El desglose por main topic de `metrics` deja de exigir el análisis entero: agrupa las que tienen main topic.
- **Cumplimiento** (`app/config/compliance.py`): `check_state(conv, code)` con cuatro estados; `check_result` sigue devolviendo `bool | None` (con `pendiente` → `None`) para no tocar a los consumidores. El detalle recibe `compliance` (solo los checks con resultado) y `compliance_pending: [códigos]`; el explorador usa `pendiente` para «está vacío».
- **Plantilla** «Generar análisis completo»: un Prompt JSON con un campo por destino (nombres iguales al destino, `compliance_<código>` y `entidad_<tipo>` en el JSON) y una línea de instrucciones por campo en el texto. El Sampling usa `or` de «está vacío» sobre `summary`, `main_topic`, `resolution`, `csat`, `effort`, `churn_risk` y cada `check:<código>`.

## Tareas

| Id | Título | Depende de | Criterios |
|---|---|---|---|
| T1 | Ingesta: escritura de los campos nuevos y columna `sentiment` | — | 9, 10, 11 |
| T2 | Catálogo de destinos, tipo «lista» y límite de campos | — | 1, 2, 3 |
| T3 | Validación de valores, reglas del editor y Output conectado a la escritura | T1, T2 | 4, 5, 6, 7, 8, 14 (API) |
| T4 | Lectura campo a campo: detalle, cumplimiento, KPIs, filtros y explorador | T1 | 12 (API) |
| T5 | Plantilla «Generar análisis completo» | T3 | 13 |
| T6 | Front de flujos: destinos agrupados, tipo «Lista» y resultado de la ejecución | T2, T3, T5 | 14, 15, 13 (menú) |
| T7 | Front del detalle con análisis parcial | T4 | 12 (UI) |
| T8 | Conocimiento, OpenAPI, navegador con Gemini y gate | T1–T7 | 16, 17, conocimiento afectado |

### T1 — Ingesta: escritura de los campos nuevos
- **Qué:**
  - migración `0006_llm_sentiment.sql` (`analysis.sentiment real`);
  - `FieldItem.values` tipado por destino (lista blanca de columnas y patrón de claves `compliance:`/`entity:`);
  - reglas de «vacío» del criterio 9, combinación clave a clave de `compliance` y `entities` y `llm_meta` por destino;
  - `sentiment` omitido con motivo si `conversation.customer_sentiment` no es `NULL`;
  - resultado `outcomes: {destino: escrito | omitido}` y `reasons: {destino: motivo}` para los omitidos.
- **Hecho cuando** (tests `pg`, primero en rojo):
  - por familia de destino (escalar, lista, `compliance:x`, `entity:x`, `sentiment`): escritura en vacío, `omitido` con valor existente y sustitución con «Sobrescribir»;
  - escribir `compliance:a` no borra `compliance:b` ya presente (y lo mismo con entidades);
  - `sentiment` con y sin sentimiento de Genesys;
  - `status` sin cambios y trazabilidad en `llm_meta` de cada destino;
  - una clave fuera de la lista blanca da `422`;
  - una redescarga con «Sobrescribir» deja vacíos los campos nuevos, `sentiment` y `llm_meta` (criterio 11);
  - la suite de ingesta y `test_flow_fields_pg.py` siguen en verde.
- **Conocimiento:** ADR-009 y runbook del servicio de LLM, en T8.

### T2 — Catálogo de destinos, tipo «lista» y límite
- **Qué:**
  - `ANALYSIS_TARGETS`, `ENTITY_TYPES` y `target_fields(config)` en `catalog.py`; `/api/flows/catalog` con `group`;
  - `FieldMapping.target` como texto con patrón y `MAX_MAPPINGS`;
  - `FIELD_TYPES["lista"]`, `options` admitidas en `texto` y `lista`, `MAX_FIELDS = 40`;
  - `_property` y `validate_answer` para listas en `llm_runner.py`; el mock (`prompting.py`) devuelve una lista de textos para un campo `lista`.
- **Hecho cuando:**
  - el catálogo contiene los destinos fijos, las cuatro entidades y un `compliance:` por check activo; desactivar un check lo quita (test con la configuración, sin códigos fijos);
  - ida y vuelta de un flujo con un campo `lista` con y sin valores permitidos y con 40 campos; 41 da error de integridad;
  - el esquema enviado al doble del servicio de LLM lleva `array` con `items.enum`;
  - una respuesta con un texto en lugar de lista, un elemento no textual o un valor no permitido se rechaza;
  - la suite de flujos sigue en verde.
- **Comprobación aparte:** Gemini acepta `array` de `string` con `enum` (una llamada real con la clave de la persona usuaria, anotada en este plan); OpenAI y Anthropic solo contra su documentación (hipótesis de la spec).

### T3 — Validación de valores, reglas y Output
- **Qué:**
  - `app/flows/targets.py` con `coerce` (criterios 4 y 5);
  - `_mapping` por familia y el check inexistente o desactivado en `rules.py` (criterios 6–8);
  - el Output `campo` aplica `coerce` por asignación, envía al escritor los valores tipados y compone `states`, `reasons` y `counts` con `rechazado` y `sin_valor`;
  - `AnalysisWriter` y el doble de los tests aceptan los valores tipados.
- **Hecho cuando:**
  - un test por regla del criterio 4, incluidos los límites (1 y 5, −1 y 1, 0, 6, 1,5), etiquetas de resolución, `NO APLICA`/`no_aplica`/`No aplica`, temas por nombre y por código, duplicados y 12 palabras clave que se guardan como 10;
  - una respuesta con `csat = 7` deja `csat` en `rechazado` y escribe el resto de campos de esa conversación;
  - un test por regla del criterio 6 en `POST /api/flows/validate` y uno del criterio 7 (check borrado y check desactivado bloquean la ejecución);
  - `duplicate_target` y `simulated_values_to_real_data` con destinos nuevos;
  - integración con PostgreSQL: un flujo con un Prompt JSON (doble del LLM) escribe resolución, un check y una entidad, y los recuentos por campo suman las conversaciones;
  - los tests de FE013 (`test_flow_fields*.py`, `test_llm_flows.py`) siguen en verde.

### T4 — Lectura campo a campo
- **Qué:** los cambios de «Lectura» y «Cumplimiento» de las decisiones de diseño: `real.py`, `compliance.py`, `kpis.py`, `routers/metrics.py`, `routers/conversations.py` (`compliance_pending`), `query/engine.py`, `query/fields.py` y `services/filters.py`.
- **Hecho cuando** (tests con la base, escribiendo el análisis parcial por SQL):
  - una conversación con solo `resolution` y `compliance:a` devuelve esos dos valores en el detalle, el resto `null` y `compliance_pending` con los demás checks activos;
  - un check personalizado con resultado del LLM usa ese resultado aunque sus frases digan lo contrario, y sin él se evalúa por frases; un check base sin resultado queda pendiente;
  - en un periodo donde solo una parte de las conversaciones tiene `resolution`, `resolution_rate` se calcula sobre ellas, `based_on` lo dice y `csat_avg` sigue «pendiente»;
  - el sentimiento es el de Genesys si existe y el del LLM si no;
  - `resolution is_empty` deja de cumplirse en las que tienen valor y `resolution is resuelta` las encuentra; `check:<código>` «está vacío» solo en las pendientes;
  - con el análisis vacío, los tests de FE012 (KPIs pendientes, filtros) y el dataset sintético siguen igual.
- **Conocimiento:** ADR-007 (cumplimiento del LLM sobre frases) y arquitectura (lectura campo a campo), en T8.

### T5 — Plantilla «Generar análisis completo»
- **Qué:** `analisis_completo` en `templates.py` (Prompt JSON, instrucciones por campo, Sampling y Output de las decisiones de diseño) y su entrada en `TEMPLATES`. Si los campos superan `MAX_FIELDS`, `TemplateError` con un mensaje que lo explica.
- **Hecho cuando** (test con PostgreSQL y origen `real`):
  - el flujo creado con un proveedor con clave pasa la completitud sin errores;
  - tiene un campo y una asignación por cada destino del catálogo, los valores permitidos de `secondary_topics` son los temas secundarios activos y los de `main_topic` los main topics activos;
  - `overwrite` es `false` y el Sampling contiene un «está vacío» por cada campo escalar y por cada check activo;
  - con un check personalizado añadido, la plantilla lo incluye;
  - ejecutado con el doble del LLM, escribe todos los campos de una conversación de prueba.

### T6 — Front de flujos
- **Qué:**
  - `OutputPanel.tsx`: desplegable de destino con `<optgroup>` «Análisis», «Cumplimiento» y «Entidades»;
  - `PromptPanel.tsx`: tipo «Lista» en el editor de esquema, con valores permitidos;
  - `RunOutputs.tsx`: tabla por conversación con desplazamiento horizontal, columnas agrupadas (análisis, cumplimiento, temas y entidades), estados `rechazado` y `sin valor`, y recuentos por campo;
  - `FlowsPage.tsx`: «Generar análisis completo» en «Nuevo flujo»;
  - tipos en `flows/types.ts`.
- **Hecho cuando:** tests de vitest del desplegable agrupado, del campo «Lista» (envío de `options`), de la tabla (un rechazado y un sin valor visibles, contenedor con `overflow-x`) y del menú de plantillas; `npm test`, `npm run lint` y `npm run build` en verde.

### T7 — Front del detalle con análisis parcial
- **Qué:** `AnalysisPanel.tsx`: «Resultado» con cada dato o «Pendiente»; cumplimiento con «Cumple», «No cumple», «No aplica» o «Pendiente» según `compliance_pending`; temas secundarios, entidades y palabras clave si existen; el aviso de análisis pendiente nombra solo lo que falta. Tipos en `api/conversations.ts`.
- **Hecho cuando:** tests de componente con un análisis parcial (resolución y un check, sin CSAT, con entidades y sin palabras clave) y con el análisis completo sintético sin cambios; lint y build en verde.

### T8 — Conocimiento, OpenAPI, navegador y gate
- **Qué:**
  - actualizar ADR-009, ADR-007, arquitectura, contrato de la API y runbook del servicio de LLM;
  - `backend/openapi.yaml` y `app/openapi/schemas.py` con el tipo `lista`, `group` de los destinos, los estados `rechazado` y `sin_valor` y `compliance_pending`.
- **Hecho cuando:**
  - `python scripts/audit_vault.py` y `./scripts/ci.sh` terminan con código 0;
  - recorrido en Chrome anotado en `VERIFY.md` (criterio 16): con `dev.sh` (puertos 18000/18001/18002), origen real y Gemini, flujo desde «Generar análisis completo» con 3 conversaciones con transcripción, ejecución con los recuentos por campo y el detalle de una de ellas con «Resultado», cumplimiento, temas secundarios, entidades y palabras clave rellenos;
  - recuentos de rechazados por campo anotados (riesgo de calidad del esquema grande); si alguno supera un tercio, se anota y se propone partir la plantilla.

## Riesgos del plan

- **Esquema grande en Gemini:** más de 25 propiedades con `enum` pueden chocar con límites de complejidad del esquema. Se comprueba con una llamada real en T2 y con la plantilla completa en T5; si falla, se parte la plantilla en dos Prompts (análisis y cumplimiento) y se ajusta la spec.
- **Lectores de `pending`:** son siete módulos; un lector olvidado mezclaría «pendiente» con «0». T4 busca todos los usos de `analysis.pending` y deja un test por lector.
- **Escritura en la base de desarrollo:** el recorrido de T8 escribe en conversaciones reales. Se hace sin «Sobrescribir» y con 3 conversaciones.

## Notas de T1

- **Hecho (2026-10-13):** `POST /analysis/fields` acepta todos los destinos con su forma (texto, número, lista, `compliance:<código>` con `true|false|null`, `entity:<tipo>` con texto) y responde `outcomes` y `reasons` por destino («Ya tenía valor», «Genesys ya da el sentimiento»). El significado de cada valor (rangos, taxonomía) lo valida la API en T3.
- **Decisión:** `sentiment` no se escribe si la conversación tiene sentimiento de Genesys, **tampoco con «Sobrescribir»**: el de Genesys siempre manda (criterio 10).
- **Ajuste de tests:** `test_runs_from_before_overwrite_existed_have_an_unknown_mode` reaplicaba todas las migraciones desde la 0005; ahora solo la 0005, que es la que prueba. La lectura interna del servicio devuelve también `sentiment`.

## Notas de T2

- **Hecho (2026-10-13, Gemini real):** con `gemini-3.5-flash-lite` y 3 conversaciones sintéticas (texto enmascarado), un esquema con `temas_secundarios` (`array` de `string` con `enum` de 6 valores) y `palabras_clave` (`array` de `string`) responde listas válidas: los temas siempre dentro de los permitidos y de 4 a 5 palabras clave. La hipótesis de la spec queda confirmada para Gemini; OpenAI y Anthropic siguen sin comprobar (sin claves).
- **Decisión:** `FieldMapping.target` deja de ser un `Literal`: se acepta un destino fijo (`ANALYSIS_TARGETS` y `entity:<tipo>`) o `compliance:<código>` con la forma de un código de check. Que el check exista y esté activo lo comprueba la completitud (T3), así un borrador no se rompe al borrar un check.
- **Decisión:** `MAX_MAPPINGS = 60` asignaciones por Output; `/api/flows/catalog` lo expone en `limits.max_mappings`, y `target_fields` lleva `group` (`analisis`, `cumplimiento`, `entidades`).
- **Decisión:** el proveedor simulado responde a un campo `lista` con un valor permitido, o con las palabras clave del análisis (o el main topic) si no tiene valores permitidos.
- **Ajuste de tests de FE013:** el catálogo de destinos se comprueba por sus dos primeros elementos, y el caso «demasiadas asignaciones» pasa de 3 a 61.

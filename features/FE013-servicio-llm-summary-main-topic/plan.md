# FE013 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-10-12 y ampliada en esta fase con los criterios 25–30: casilla «Sobrescribir» de la ingesta y protección de la taxonomía. Siguiente paso: `/build`, una tarea cada vez y en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| [ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md), `app/flows/prompting.py`, `routers/flows.py` | `PromptRunner.run(config, conversation, previous)`; `get_prompt_runner()` devuelve `MockPromptRunner`; el ejecutor (`flows/runs.py`) recorre las conversaciones de una en una. | T5 añade `LlmPromptRunner` y un runner que **enruta por el proveedor del nodo**, de modo que los flujos simulados no cambian. El nodo Prompt procesa en paralelo cuando el runner lo admite. |
| [ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md), `backend/ingestion/` | Patrón de servicio aparte: lista blanca de claves (`app/envfile.py`), token interno, cliente con `503` (`app/ingestion_client.py`) y un único escritor de PostgreSQL. | `backend/llm/` copia el patrón (T4). Las escrituras del LLM pasan por un endpoint interno del servicio de ingesta (T6). |
| `ingestion/pipeline/load.py` | Upsert de `conversation`; `DELETE` y reinserción de tramos, turnos, temas y respuestas originales; upsert de `analysis` que **pone a vacío** summary y main topic de una fila `pendiente`. | T1: sin «Sobrescribir» no se toca una conversación existente; con «Sobrescribir», la fila de `analysis` se sustituye siempre, también la `completo`. |
| `ingestion/runs.py` (`extract_and_load`) | `search` → por conversación `fetch` → `normalize` → `analyze` → `load`, con contadores `inserted` y `updated`. | T1 añade la comprobación de existencia antes de `fetch` y el contador `skipped_existing`. |
| `app/data/real.py` (`_analysis`) | Solo usa `analysis` si `status='completo'`. | T6 lee `summary` y `main_topic` siempre; `pending` sigue indicando el estado del resto del análisis. |
| `app/config/taxonomy.py` (`main_topic_usage`) | Cuenta solo el dataset del origen activo (`get_dataset()`). | T3 suma el uso en PostgreSQL al borrar, sea cual sea el origen. |
| `app/flows/catalog.py` | `PROVIDERS = {"simulado": …}` y `MODELS` mock; `ANALYSIS_FIELDS` ya existe en `app/query/fields.py`. | T5 amplía `PROVIDERS`. El catálogo de destinos se llama `TARGET_FIELDS` (spec ajustada). |
| `app/config/store.py` | Por defecto, `AiConfig(provider="simulado", model="mock-rapido")`. | T5 cambia el valor por defecto a `gemini` (criterio 8). Los tests de flujos fijan `simulado` de forma explícita (`flow_fixtures.py` ya usa modelos mock), para no depender de una clave. |
| `query/fields.py` | Operador `is_empty` (FE012). | Las plantillas filtran el Sampling con `summary is_empty` o `main_topic is_empty` (T8): el riesgo de la spec queda resuelto. |
| `scripts/dev.sh`, `scripts/ci.sh`, `.env.example` | Tres procesos más PostgreSQL. | T4 añade el cuarto proceso y sus claves. |
| [Lecciones](../../vault/aprendizaje/lecciones-construccion-plataforma.md), [registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md) | Tests independientes del dataset; prefijos `1FL`, `1ND`, `1RN`. | No hay prefijos nuevos. Los tests nuevos consultan totales a la base o al dataset, nunca valores fijos. |

## Decisiones de diseño

- **Servicio de LLM** (`backend/llm/`, `uvicorn llm.main:app --port 8002`):
  - `providers/base.py`: `LlmProvider` (`name`, `complete(request, http) -> Completion`), `CompletionRequest` (modelo, temperatura, prompt, formato `texto|etiqueta|json` con etiquetas o esquema) y `Completion` (texto, modelo y tokens opcionales).
  - Implementaciones `gemini.py`, `openai.py`, `anthropic.py` y `simulated.py`, y un registro `providers/__init__.py:REGISTRY`.
  - Llamadas REST con **`httpx`**, sin SDK, para no añadir dependencias y para probar con `MockTransport`, como la ingesta. Puntos de partida, que T4 contrastará con la documentación oficial:
    - **Gemini:** `POST …/v1beta/models/{model}:generateContent` con `x-goog-api-key`; JSON con `responseMimeType`.
    - **OpenAI:** `POST /v1/chat/completions` con `Authorization: Bearer`; JSON con `response_format`.
    - **Anthropic:** `POST /v1/messages` con `x-api-key` y `anthropic-version`; `max_tokens` obligatorio.
  - Rutas: `GET /health` (sin token: estado y `keys: {proveedor: bool}`), `POST /complete` y `POST /providers/{name}/test` (con `LLM_TOKEN`).
  - Concurrencia: un `threading.BoundedSemaphore(LLM_MAX_CONCURRENCY)` global. Reintentos de `429`/`5xx`: 2, con espera de 0,5 s y 1 s (configurable para los tests).
  - Claves: `LLM_KEYS = ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_TOKEN", "LLM_MAX_CONCURRENCY")` en `app/envfile.py`. El servicio solo importa `app.ids`, `app.clock` y `app.envfile`.
  - Los logs registran proveedor, modelo, duración y estado, **nunca** el prompt, la respuesta ni las claves.
- **API:**
  - `app/llm_client.py` (copia de `ingestion_client.py`: `LLM_URL`, `LLM_TOKEN`, `LlmUnavailable` → `503`, timeout de 60 s en `/complete`).
  - `PromptConfig` gana `provider`; un nodo sin `provider` se lee como `simulado`, así los flujos guardados siguen valiendo. `model` se valida contra los modelos de su proveedor.
  - `RoutingPromptRunner`: usa `MockPromptRunner` con `simulado` y `LlmPromptRunner` con cualquier otro proveedor. Este último renderiza con `render_template`, llama al servicio y valida la respuesta: normaliza texto y etiqueta con `normalize_text` y valida el JSON contra el esquema.
  - Los resultados por conversación pasan a ser `{"value"}`, `{"rejected": motivo}` o `{"error": motivo}`. Los outputs `tabla`, `metrica` e `informe` excluyen las conversaciones rechazadas o con error y las cuentan aparte.
  - Paralelismo: `runner.parallelism` (1 en el mock, 4 en el LLM) con `ThreadPoolExecutor` en `_prompt`, conservando el orden y el contador de procesados bajo el cerrojo de la ejecución.
  - Fallos que paran el nodo (criterio 14): `LlmUnavailable`, y `503` o `502` de clave del servicio. Se lanzan como `NodeFailure`.
  - Completitud (criterio 10): `validate(graph, context)` recibe un `ValidationContext` (origen activo y `keys` del `/health` del servicio, o «no disponible»). El router lo construye, así `rules.py` sigue siendo puro.
- **Output `campo`:**
  - `OUTPUT_KINDS["campo"]`, `TARGET_FIELDS = {"summary": "Summary", "main_topic": "Main topic"}`. `OutputConfig` gana `field` y `overwrite: bool = False`; para `campo`, `destination` no se pide y se muestra la etiqueta del campo.
  - Escritura: protocolo `AnalysisWriter` y dependencia `get_analysis_writer()` en la API, que llama a `POST /analysis/fields` del servicio de ingesta en lotes de 100.
  - Cuerpo de la escritura: `{run_id, provider, model, field, overwrite, items: [{conversation_id, value}]}` → `{results: [{conversation_id, outcome: escrito|omitido|no_encontrada}]}`.
  - SQL por elemento: `UPDATE analysis SET <campo> = %s, llm_meta = llm_meta || {campo: {provider, model, run_id, at}}, updated_at = now() WHERE conversation_id = %s AND (%s OR coalesce(<campo>, '') = '') RETURNING 1`. El nombre de columna sale de una lista blanca, nunca de la entrada.
  - Migración `0004_llm_meta.sql`: `analysis.llm_meta jsonb NOT NULL DEFAULT '{}'`. Es la «columna nueva» de trazabilidad del criterio 19; un solo `jsonb` sirve para todos los campos.
  - `main_topic` se traduce a código en la API antes de escribir. El valor ya validado nunca llega vacío.
- **Ingesta «Sobrescribir»:**
  - Migración `0003_overwrite.sql`: `download_flow.overwrite boolean NOT NULL DEFAULT false`. Se acepta en `FlowIn` y se devuelve en `flow_to_dict`.
  - La ejecución copia el valor del flujo al empezar, en `download_run.overwrite`, para que editar el flujo durante una ejecución no la cambie.
  - Sin «Sobrescribir»: antes de cada `fetch`, `SELECT 1 FROM conversation WHERE genesys_id = %s`. Si existe, `skipped_existing += 1`, log «Ya existe: no se descarga» y se pasa a la siguiente.
  - Como red de seguridad ante otra ejecución simultánea, `load(..., overwrite=False)` devuelve `OMITTED` si el `INSERT … ON CONFLICT DO NOTHING` no inserta, y entonces no actualiza nada.
  - Con «Sobrescribir»: `load` sustituye la fila de `analysis` sin la condición de `completo` y pone `llm_meta` a `'{}'`.
- **Taxonomía:** `app/data/real.py:main_topic_usage_in_db()` hace `SELECT main_topic, count(*) FROM analysis …` con una conexión propia y lanza `DataUnavailable` si la base no responde. `delete_topic` suma ese uso al del dataset sintético (`SyntheticRepository`, no el activo) solo para main topics. Con `DATABASE_URL` sin configurar, no consulta la base.
- **Plantillas:** `app/flows/templates.py` construye el grafo con la taxonomía activa y el proveedor y modelo por defecto. `POST /api/flows` acepta un `template` opcional (`summary` o `main_topic`); el front ofrece las tres opciones en «Nuevo flujo».

## Tareas

| Id | Título | Depende de | Criterios |
|---|---|---|---|
| T1 | Ingesta: «Sobrescribir» y omisión de existentes (backend) | — | 25, 26, 27 (con escritura simulada por SQL), 28 |
| T2 | Front de la ingesta: casilla y recuento | T1 | 29 |
| T3 | Taxonomía: no borrar main topics usados en datos reales | — | 30 |
| T4 | Servicio de LLM con proveedores intercambiables | — | 1–7, 23 (dev.sh y `.env.example`) |
| T5 | API: proveedores en Configuración y `LlmPromptRunner` | T4 | 8 y 9 (API), 10–14 |
| T6 | Output `campo`: modelo, validación, escritura y lectura | T1, T5 | 15, 16, 18–21 (API), 27 (con la escritura real) |
| T7 | Front: Modelos de IA y nodo Prompt | T5 | 8, 9, 10 (UI) |
| T8 | Front: Output «Guardar en campo» y plantillas | T6, T7 | 17, 21 (UI), 22 |
| T9 | Conocimiento, OpenAPI, navegador y gate | T1–T8 | 23, 24, conocimiento afectado |

### T1 — Ingesta: «Sobrescribir» y omisión de existentes
- **Qué:**
  - migración `0003_overwrite.sql` (`download_flow.overwrite` y `download_run.overwrite`);
  - `FlowIn.overwrite` y su vuelta en `flow_to_dict`;
  - comprobación de existencia antes de `fetch`, contador `skipped_existing` y log;
  - `load(conn, c, analysis, overwrite)` con la rama `OMITTED` y la sustitución completa de `analysis`;
  - el relevo de la API (`routers/downloads.py`) deja pasar el campo.
- **Hecho cuando** (tests `pg` con el Genesys falso, primero en rojo):
  - (a) un flujo sin el campo se guarda con `false` y la API lo devuelve;
  - (b) la segunda ejecución sin «Sobrescribir» hace cero llamadas a las rutas de descarga del Genesys falso, `skipped_existing` es igual al número de conversaciones y un `summary` escrito por SQL sigue intacto;
  - (c) con «Sobrescribir», ese `summary` y un `analysis` `completo` vuelven a `pendiente` y vacíos, con el mismo `1CO`;
  - (d) `inserted + updated + skipped_existing + errors` es igual a las conversaciones por descargar;
  - la suite de ingesta actual sigue en verde (los tests que esperaban `updated` en una segunda ejecución pasan a usar `overwrite=true` de forma explícita).
- **Conocimiento:** runbook de la ingesta y ADR-008 (ampliación), en T9.

### T2 — Front de la ingesta
- **Qué:** casilla «Sobrescribir» con su ayuda en `DownloadFlowForm.tsx`, el tipo en `downloads/types.ts` y el recuento «Ya existentes (no descargadas)» en `DownloadRunPage.tsx`.
- **Hecho cuando:** tests de vitest: la casilla se envía en el cuerpo, aparece desmarcada en un flujo nuevo y el recuento se pinta; `npm test`, `npm run lint` y `npm run build` en verde. El recorrido en navegador se hace en T9.

### T3 — Taxonomía protegida
- **Qué:** `main_topic_usage_in_db()` y el uso combinado en `delete_topic` (`409` con los recuentos por origen y `503` si la base no responde).
- **Hecho cuando:** tests `pg` con el origen activo `sintetico`:
  - (a) un main topic sin uso en el sintético pero escrito en `analysis` real da `409` y no se borra;
  - (b) con `DATABASE_URL` inválida da `503` y no se borra;
  - (c) sin `DATABASE_URL`, el comportamiento de hoy;
  - más un test sin `pg` de que con el origen `real` sigue contando también el sintético.
- **Conocimiento:** ADR-007 y arquitectura (propagación de la taxonomía), en T9.

### T4 — Servicio de LLM
- **Qué:**
  - `backend/llm/` (app, settings, seguridad por token, registro y cuatro proveedores, semáforo y reintentos);
  - `LLM_KEYS` en `app/envfile.py`;
  - test estructural (importaciones y lectura de claves);
  - cuarto proceso en `dev.sh` (`LLM_PORT=8002`) y claves en `.env.example`.
- **Antes de escribir los adaptadores:** contrastar en la documentación oficial de Google, OpenAI y Anthropic la URL, las cabeceras, el cuerpo, el modo JSON, si el modelo admite `temperature` y los identificadores de modelo vigentes. Las URL y la fecha de la consulta se anotan en este plan.
- **Hecho cuando** (tests sin red con `MockTransport`):
  - por proveedor: petición enviada (URL, cabeceras, modelo, temperatura, prompt) y texto extraído de una respuesta de ejemplo de la documentación;
  - `401` sin token;
  - `503` sin clave, `502` con clave rechazada y reintentos en `429`/`5xx` (con el número de intentos comprobado);
  - nunca más de N llamadas simultáneas;
  - una clave ficticia no aparece en respuestas ni en logs capturados (`caplog`);
  - el registro cumple el contrato y coincide con los proveedores del catálogo de la API (un test que importa los dos);
  - `dev.sh` arranca y para el servicio por PID (comprobado a mano en los puertos 18000/18001/18002).

### T5 — API: proveedores y `LlmPromptRunner`
- **Qué:**
  - `PROVIDERS` con `gemini`, `openai`, `anthropic` y `simulado`, y el valor por defecto `gemini`;
  - `PromptConfig.provider`;
  - `app/llm_client.py` y las rutas `GET /api/config/ai/status` y `POST /api/config/ai/test/{provider}` (con `config:view` y `config:edit`);
  - `RoutingPromptRunner` y `LlmPromptRunner` con la validación por formato y los resultados `value`, `rejected` y `error`;
  - paralelismo en `_prompt`;
  - `ValidationContext` en la completitud;
  - `default_provider` en `/api/flows/catalog`.
- **Hecho cuando** (doble del servicio de LLM con `dependency_overrides`):
  - el cambio de proveedor en Configuración cambia `default_provider`/`default_model` y los modelos del catálogo;
  - un nodo sin `provider` sigue ejecutándose simulado (ida y vuelta de un flujo antiguo);
  - un nodo `gemini` sin clave o con un modelo ajeno da `error` en la validación;
  - el prompt que recibe el doble no contiene un DNI ni un teléfono sembrados;
  - hay un test por formato con respuestas válidas y rechazadas;
  - el servicio caído o la clave rechazada dejan el nodo en `error` y los dependientes en `pendiente`;
  - el resto de fallos cuentan por conversación;
  - los outputs existentes excluyen las rechazadas;
  - la suite actual de flujos sigue en verde.
- **Conocimiento:** ADR-006 (ampliación) y ADR-009 (nuevo), en T9.

### T6 — Output `campo`
- **Qué:**
  - `OutputConfig.field` y `overwrite`, y `TARGET_FIELDS` en el catálogo;
  - las reglas del criterio 16;
  - `POST /analysis/fields` en el servicio de ingesta y la migración `0004_llm_meta.sql`;
  - `AnalysisWriter` en la API y el nodo `campo` del ejecutor (estados `escrito`, `omitido`, `rechazado` y `error`, y sus recuentos);
  - lectura de `summary` y `main_topic` en `real.py` aunque la fila esté `pendiente`;
  - en `load` con «Sobrescribir», `llm_meta` vuelve a `'{}'`.
- **Hecho cuando:**
  - ida y vuelta del JSON;
  - un test de `validate` por regla (formato, etiquetas fuera de la taxonomía activa, destino repetido, origen `sintetico`);
  - tests `pg` de las cuatro combinaciones del criterio 18 y de la trazabilidad en `llm_meta`, sin cambiar el `status` de una fila `completo`;
  - un nombre en la respuesta se guarda como código;
  - la integración del criterio 20 (`GET /api/conversations?main_topic=<código>` devuelve la conversación pendiente recién escrita);
  - la suma de recuentos es igual a la muestra;
  - el criterio 27 repetido con la escritura real.

### T7 — Front: Modelos de IA y nodo Prompt
- **Qué:**
  - `AiTab.tsx` sin el aviso de «ejecución simulada», con el estado del servicio, «clave configurada» por proveedor y «Probar»;
  - `PromptPanel.tsx` con un desplegable de proveedor y los modelos filtrados por proveedor;
  - los tipos en `flows/types.ts` y `config/types.ts`.
- **Hecho cuando:** tests de vitest (estado y prueba con éxito y con error, solo lectura sin `config:edit`, cambio de proveedor que reinicia el modelo, nodo antiguo mostrado como «Simulado»); lint y build en verde.

### T8 — Front: Output «Guardar en campo» y plantillas
- **Qué:**
  - en `OutputPanel.tsx`, el tipo `campo`, el desplegable de destino desde `target_fields`, la casilla «Sobrescribir valores existentes» y la opción deshabilitada con aviso si el origen es `sintetico`;
  - en `RunOutputs.tsx`, la tabla por conversación con su estado y los recuentos;
  - en `FlowsPage.tsx`, «Nuevo flujo» con «Vacío», «Generar summary» y «Generar main topic»;
  - `app/flows/templates.py` y `template` en `POST /api/flows` (backend).
- **Hecho cuando:**
  - test de pytest de que cada plantilla crea un flujo que pasa la completitud con origen `real` y un proveedor con clave, con las etiquetas iguales a los main topics activos;
  - tests de vitest del panel (opciones, deshabilitado en sintético, envío de `field` y `overwrite`), de los recuentos y del menú de plantillas;
  - lint y build en verde.

### T9 — Conocimiento, OpenAPI, navegador y gate
- **Qué:**
  - ADR-009 «Servicio de LLM con proveedores intercambiables» y runbook del servicio de LLM, con `/vault capture`;
  - ampliaciones de ADR-006, ADR-007 (taxonomía) y ADR-008 («Sobrescribir» y escritura del LLM);
  - actualizar arquitectura, contrato de la API, estado operativo, primeros pasos, runbook de la ingesta y `README.md`;
  - `backend/openapi.yaml` y `app/openapi/spec.py` con las rutas nuevas;
  - `ci.sh` con los tests del servicio de LLM.
- **Hecho cuando:**
  - `python scripts/audit_vault.py` y `./scripts/ci.sh` terminan con código 0;
  - recorrido en Chrome anotado en `VERIFY.md`: flujo de descarga con y sin «Sobrescribir» (recuento de existentes), Configuración → Modelos de IA, plantilla «Generar main topic» con `simulado` ejecutada sobre conversaciones reales y main topic visible en el detalle, y opción deshabilitada en sintético;
  - si hay una clave de Gemini, la misma ejecución con Gemini sobre 3 conversaciones; si no, se marca como no verificada.

## Riesgos del plan

- **Comportamiento de las suites:** hoy hay tests de ingesta que esperan `updated` al repetir una descarga. Con `overwrite=false` por defecto hay que cambiarlos a `overwrite=true` de forma explícita, no borrarlos (T1).
- **`temperature` en algunos modelos:** algunos modelos de razonamiento rechazan `temperature`. Si T4 lo confirma en la documentación, el adaptador la omite para esos modelos y lo anota en ADR-009.
- **Tiempo de las ejecuciones:** 1.000 conversaciones con 4 llamadas en paralelo dentro de `BackgroundTasks` de la API. Es aceptable para el laboratorio (spec); la cancelación queda fuera de alcance.

## Progreso

- [x] T1 · [ ] T2 · [ ] T3 · [ ] T4 · [ ] T5 · [ ] T6 · [ ] T7 · [ ] T8 · [ ] T9

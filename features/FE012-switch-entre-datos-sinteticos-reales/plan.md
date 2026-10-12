# FE012 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md) (la petición de implementar la feature, el 2026-10-12, la da por aprobada). Siguiente paso: `/build`, una tarea cada vez y en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| `app/data/store.py` | `get_dataset()`, `conversation_index()` y `followup_index()` son `@cache` sobre el dataset sintético. Los usan 14 módulos (KPIs, listado, explorador, búsqueda, sampling, configuración, cumplimiento, taxonomía). | Se mantienen esas tres funciones como fachada y pasan a delegar en el **repositorio activo**: los puntos de llamada no cambian. |
| `app/models.py` | `Analysis` y `Turn` asumen todos los campos presentes; `Conversation` exige cola, agente y cliente. | Los campos que Genesys no da pasan a ser opcionales (`None`) y se añade `Conversation.genesys` (analítica) y `Analysis.pending`. El dataset sintético los rellena como hoy: su salida JSON no cambia. |
| `app/config/store.py` (`Config`) | Instantánea inmutable con versión; toda escritura pasa por `apply_change`, que audita. | El origen es un campo más (`sources`), con sección de auditoría `fuentes` ya existente. Se pierde al reiniciar (alcance). |
| `app/services/kpis.py`, `query/fields.py`, `query/engine.py`, `flows/sampling.py`, `flows/prompting.py`, `config/compliance.py`, `config/taxonomy.py`, `privacy/masking.py` | Acceden a `analysis.*` sin comprobar nulos. | T2 y T4 los hacen tolerantes: «campo sin analizar = vacío» (criterio 10). |
| `ingestion/pipeline/read.py` y `migrations/0001` | Ya existe `read_conversation` con la forma normalizada; `metrics` guarda `handle_s`, tiempos, STA, confianza y calidad de voz. | La API lee PostgreSQL **directamente y en solo lectura** con su propio SQL (`app/data/real.py`): no importa `ingestion` (test estructural de FE011) y evita un salto HTTP por petición (criterio 14). |
| `app/envfile.py` | La API solo lee `INGESTION_URL` e `INGESTION_TOKEN`. | Se añade `DATABASE_URL` a las claves de la API. Sigue sin leer `GENESYS_*` (test existente). |
| `tests/conftest.py` (`pg_url`) y `tests/ingestion_helpers.py` | PostgreSQL efímero y Genesys falso con 10 fixtures. | El sembrado de los tests reales es `RunExecutor` sobre el Genesys falso (T2): los mismos datos que FE011. |
| `routers/search.py` | El índice es `@cache` y se construye al arrancar. | T5 lo cambia por un gestor con swap atómico y reconstrucción en segundo plano. |
| [Lecciones](../../vault/aprendizaje/lecciones-construccion-plataforma.md) 28 y 31 | Tests que dependen del dataset o de la estructura interna. | Los tests nuevos de modo real consultan los totales a la base y los del sintético a `get_dataset()`; los de contrato recorren los endpoints, no módulos. |
| ADR-002, 005, 006, 007, arquitectura, contrato, patrones de interfaz, glosario, propósito, README | Existen y están `active`. | T9. |

## Decisiones de diseño

- **Repositorio** (`app/data/repository.py`): `ConversationRepository` con `conversations()`, `get(id)`, `followups()` y `version()`. Dos implementaciones: `SyntheticRepository` (el generador de hoy, versión constante) y `RealRepository` (PostgreSQL).
  - `active_repository()` elige por `get_config().sources.origin`. Las tres funciones de `data/store.py` delegan en él.
  - **Instantánea con versión.** `RealRepository` carga todas las conversaciones como objetos `Conversation` y las guarda con un testigo `(count, max(updated_at))`, que se consulta en cada petición (una consulta de milisegundos). Si cambia, recarga: así «los datos nuevos aparecen en la siguiente petición» (criterio 4) sin canal de avisos entre procesos.
  - Los cachés de módulo (`@cache` de uso de taxonomía, de conectores por canal, de texto normalizado, de resultados de checks, del enmascarado) se indexan por **identidad de la instantánea**, como ya hace `get_fields()` con la configuración, o se reemplazan por `get_cache(snapshot)`.
  - Si PostgreSQL no responde, `RealRepository` lanza `DataUnavailable`; un manejador global lo traduce a `503` con «Los datos reales no están disponibles». Los routers de Configuración no tocan el repositorio real salvo las cuentas por canal, que toleran el fallo.
- **Análisis pendiente.** Para una conversación real, `analysis.pending = True`, y `summary=""`, `main_topic/resolution/csat/effort/churn_risk=None`, `compliance={}`. El sentimiento es `customer_sentiment` de Genesys (puede ser `None`); `sentiment_timeline` sale de los turnos del cliente con sentimiento.
- **KPIs en modo real:** `compute_kpis` devuelve `None` para los que dependen del análisis y se marcan con `pending: true` en `/api/metrics/summary` y `/breakdown` (el front los pinta «Sin datos · pendiente de análisis»). `volume`, `aht_s` (media de `handle_s` de las atendidas por un agente) y `sentiment_avg` (con `sentiment_n`) se calculan. `negative_pct` queda pendiente porque usa el análisis; `first_response_s` y `avg_turns` se calculan igual que hoy sobre los turnos de agente.
- **Campos vacíos (criterio 10).** `FieldDef.extract` devuelve `None` para lo sin analizar; el motor del explorador añade el operador `is_empty` a todos los tipos y trata `None` como no cumple nada salvo `is_empty`. Los filtros del drill-down (`resolution`, `churn_risk`, …) tratan `None` igual.
- **Campos de Genesys (criterio 7):** `build_fields` añade, solo con origen real, los campos del criterio 7 (clave prefijada `gc_`), de modo que con `sintetico` el esquema es idéntico al de hoy.
- **Enmascarado:** `masked()` se extiende a los turnos reales (mismo `mask`); ANI, DNIS y `externalTag` no se pasan por `mask`. Sin cambios en el índice: ya se construye sobre `masked()`.
- **Índice caliente:** `SearchIndex` guarda `(version, engine)`; `engine()` devuelve el vigente y, si la versión del repositorio ha cambiado, lanza **una** reconstrucción en un hilo (agrupada: si ya hay una en curso no lanza otra) y sigue sirviendo el anterior hasta el swap. En el primer uso de un origen sin índice, construye en línea.
- **Front:** `SourcesTab` gana el selector del origen con confirmación; al guardar se invalida toda la caché de consultas (`queryClient.clear()` o equivalente del proyecto). Un `ApiError` con estado 503 se pinta con un `DataUnavailable` reutilizable.

## Tareas

| Id | Título | Depende de | Criterios |
|---|---|---|---|
| T1 | Modelo opcional, repositorio y origen en Configuración (backend) | — | 1 (API, auditoría, permisos), 2 (sintético intacto) |
| T2 | `RealRepository`: lectura de PostgreSQL, 503 y datos nuevos | T1 | 2, 3, 4 |
| T3 | Listado, detalle y KPIs en modo real | T2 | 5 (API), 6 (API), 9, 10 |
| T4 | Explorador, sampling y variables de los prompts | T3 | 7, 8, 10 |
| T5 | Búsqueda: índice en caliente y privacidad del texto real | T3 | 11, 12 |
| T6 | Front: switch en Fuentes de datos, invalidación y 503 | T1–T3 | 1, 3 |
| T7 | Front: detalle con panel de analítica, listado y KPIs pendientes | T6 | 5, 6, 9 |
| T8 | Rendimiento, contrato de no-500 y recorrido en Chrome | T1–T7 | 10, 13, 14, 15 |
| T9 | Conocimiento, documentación y gate final | T1–T8 | conocimiento afectado, 13 |

### T1 — Modelo opcional, repositorio y origen
- **Qué:** campos opcionales en `models.py` (`genesys`, `pending`, `Turn.delivered/confidence`), `repository.py` con `SyntheticRepository`, `Config.sources` y `PUT /api/config/sources` (`config:edit`, auditoría `fuentes`), y `sources` en `GET /api/config`.
- **Hecho cuando:** test (rojo→verde) de que el origen por defecto es `sintetico`, de que cambiarlo exige `config:edit` (el `supervisor` recibe `403`), queda auditado, rechaza valores desconocidos y no cambia nada si el valor es el mismo; y la suite actual sigue en verde sin modificarse.

### T2 — `RealRepository`
- **Qué:** `app/data/real.py` (SQL de solo lectura → `Conversation`), testigo de versión, `DataUnavailable` y su manejador `503`, `DATABASE_URL` en la API; helper `seed_real(pg_url)` en `tests/`.
- **Hecho cuando:** tests `pg`: con origen `real` el total de `/api/conversations` es el de la base; una ejecución de FE011 posterior aparece en la petición siguiente; con PostgreSQL caído (URL inválida) los endpoints de datos dan `503` y `PUT /api/config/sources` sigue funcionando para volver a `sintetico`.

### T3 — Listado, detalle y KPIs
- **Qué:** columnas y búsqueda exacta de teléfono (con o sin `+34`) y `externalTag`; detalle con el bloque `genesys`; KPIs pendientes; filtros tolerantes a `None`.
- **Hecho cuando:** tests `pg` de listado (teléfono, etiqueta, summary vacío), detalle (llamada y chat bot → agente, chat con mensaje no entregado), `summary` con `pending`, volumen/AHT/sentimiento calculados y el resto `pending`, y drill-down que cuadra con el listado.

### T4 — Explorador, sampling y prompts
- **Qué:** operador `is_empty`, campos `gc_*` solo en real, sampling tolerante, `{{transcripcion}}`, `{{metadatos}}` y aviso de validación.
- **Hecho cuando:** tests de que el esquema del explorador no cambia en sintético, de «derivada a agente» en real, de `is_empty`, del sampling con campos vacíos y de las variables.

### T5 — Búsqueda
- **Qué:** gestor de índice con swap y reconstrucción agrupada; enmascarado de turnos reales.
- **Hecho cuando:** tests de que el índice se reconstruye al cambiar de origen y con datos nuevos, de que durante la reconstrucción se sirve el anterior, de que se encuentra «Amazon Brasil», y de privacidad (teléfono, email, DNI, IBAN y tarjeta ficticios; ANI/DNIS/`externalTag` sin enmascarar).

### T6 — Front: switch
- **Hecho cuando:** tests de vitest de la pestaña (muestra el origen, confirma, solo lectura para `supervisor`, estado del conector real) y del aviso `503`; lint y build verdes.

### T7 — Front: detalle, listado y KPIs
- **Hecho cuando:** tests de vitest del chat (estilos por hablante, línea de transferencia, «No entregado»), del panel de analítica, de «Análisis pendiente» y de los KPIs «Sin datos».

### T8 — Rendimiento, contrato y Chrome
- **Hecho cuando:** test `pg` con 1.000 conversaciones (< 500 ms por endpoint), test de contrato sin `500` y el recorrido del criterio 15 hecho en Chrome, anotado en `VERIFY.md`.

### T9 — Conocimiento y gate
- **Hecho cuando:** actualizadas las entradas de «Conocimiento afectado» y el `README`, `python scripts/audit_vault.py` y `./scripts/ci.sh` con código 0.

## Progreso

- [x] T1 · [ ] T2 · [ ] T3 · [ ] T4 · [ ] T5 · [ ] T6 · [ ] T7 · [ ] T8 · [ ] T9

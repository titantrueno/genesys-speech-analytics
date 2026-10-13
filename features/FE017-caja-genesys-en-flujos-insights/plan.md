# FE017 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-10-13. Siguiente paso: `/build`, una tarea cada vez y en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| `ingestion/migrations/0001_initial.sql` (`download_run`, `run_log`) | `download_run.flow_id` es `NOT NULL REFERENCES download_flow`, con un índice único de una ejecución activa por flujo. No se guarda qué conversaciones tocó cada ejecución: solo contadores. | T1: migración `0008_insight_downloads.sql`. `flow_id` pasa a admitir `NULL`, se añade `insight_flow_id` con referencia a `insight_flow` (FE015, `ON DELETE CASCADE`) y un `CHECK` que exige exactamente uno de los dos. Se añaden un índice único de ejecución activa por `insight_flow_id` y la tabla `download_run_conversation (run_id, conversation_id)`, que es el subconjunto. |
| `ingestion/pipeline/load.py` | `load` devuelve `insertada`, `actualizada` u `omitida`; esta última significa que ya existía y no se sobrescribe. | El subconjunto son las `insertada` y `actualizada` (spec, «Conceptos»). Por eso una programación «hoy» cada hora sin «Sobrescribir» solo pasa al Sampling las conversaciones nuevas. |
| `ingestion/scheduler.py` (`launch`) y `ingestion/runs.py` (`create_run`) | `launch` lee el intervalo, los canales y la zona horaria de `download_flow`; `create_run` copia `overwrite` de esa tabla. | T1: `create_run` recibe `overwrite` y `insight_flow_id` como parámetros. La caja de descarga lanza con los valores de su configuración, sin crear un `download_flow` oculto. |
| `ingestion/flows.py` (`Interval`, `Schedule`, `resolve_interval`, `next_occurrence`) | Modelos y funciones puros, pero dentro de `ingestion/`. `app/` nunca importa `ingestion/` (la ingesta sí importa `app.ids` y `app.clock`). | T2: se mueven a `app/flows/download_config.py` y `ingestion/flows.py` los importa desde ahí. La API valida la caja y calcula la próxima ejecución sin cruzar la frontera. Los mensajes no cambian, y los tests de FE011 lo comprueban. |
| `app/flows/model.py`, `connections.py`, `catalog.py`, `rules.py`, `frontend/src/flows/rules.cases.json` | Tipos `sampling`, `prompt` y `output`. `ALLOWED` y `SINGLE_INPUT` en `connections.py`. El Sampling es siempre el inicio. | T2: tipo `descarga`, par `descarga → sampling`, `sampling` en `SINGLE_INPUT`, una sola salida para `descarga`, como máximo una caja por grafo y los códigos de validación del criterio 3. |
| `app/flows/sampling.py` (`candidates`, `draw_sample`), `SamplingConfig.size` (`1..1000`) | El tamaño es obligatorio para ejecutar. `candidates` filtra todo el dataset activo con la consulta del nodo. | T3: «All conversations» como `size: "all"`. T4: `candidates(config, subset=None)` restringe a los `1CO` del subconjunto y no aplica el intervalo de fechas de la consulta. |
| `app/flows/runs.py` (`FlowExecutor`, `Run`, `RunStore`) | Ejecuciones en memoria. Estados `pendiente`, `en_curso`, `ok` y `error`. Una muestra vacía es `error`. No hay origen `manual` ni `programada`. | T4: nodo `descarga` en el ejecutor y estado `omitido`. T5: `origin` en `Run`. |
| `app/data/real.py` (`RealRepository.snapshot`) | La instantánea de los datos reales se rehace cuando cambia la versión de la base. | Al terminar la descarga, el Sampling ve las conversaciones nuevas sin hacer nada más. Un test de T4 lo cubre. |
| `app/ingestion_client.py` | Cliente con token interno; ante un error de red o un `5xx`, lanza `IngestionUnavailable`. | Lo reutilizan T4 (lanzar la descarga, consultar su estado, su log y el subconjunto) y la validación del criterio 3. |
| `backend/app/main.py` (`lifespan`) | La API no tiene programador; el de FE011 vive en el servicio de ingesta. | **Decisión (riesgo de la spec):** T5 añade un programador en la API (`app/flows/scheduler.py`), porque las ejecuciones de insights viven en su memoria. Lee los flujos persistidos (FE015) y sigue el patrón `tick()` con reloj simulado del programador de FE011. |
| `frontend/src/downloads/DownloadFlowForm.tsx` | Formulario completo de flujo de descarga: intervalo, canales, programación, activo y «Sobrescribir». | T6: los controles de intervalo, canales y programación se extraen a componentes que reutilizan ese formulario y el panel de la caja. |
| [FE004](../FE004-disenador-de-flujos-de-insights/spec.md), [FE011](../FE011-ingesta-de-conversaciones-genesys/spec.md), [FE015](../FE015-persistencia-flujos-y-preferencias/spec.md) | Vigentes. | Los tests de esas features siguen en verde sin cambios (criterios 3 y 11). |
| [ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md) (`active`) | Solo la ingesta habla con Genesys y escribe en PostgreSQL. | Se respeta: la API solo pide al servicio de ingesta que descargue y lee el subconjunto. En T8 se amplía con el programador de la API y las descargas de las cajas. |
| [ADR-010](../../vault/decisiones/adr-010-idioma-de-la-interfaz-y-api-en-ingles.md) (`active`) | Textos `es`/`en` con test de paridad; la API responde en inglés. | Los textos nuevos de T6 y T7 van en los dos diccionarios, y los mensajes nuevos de la API, en inglés. |
| [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md) | `1FL`, `1ND` y `1RN` activos. | No hacen falta prefijos nuevos. La ejecución de descarga de una caja es un `1RN` generado en la ingesta con `ids.py`. |
| [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md) | La 19 trata las ejecuciones en segundo plano. Los tests no dependen del dataset. | El ejecutor espera la descarga sondeando con un intervalo inyectable, sin `sleep` fijo en los tests. Los tests de subconjunto consultan los `1CO` reales de la base. |

## Decisiones de diseño

- **Configuración de la caja** (`DownloadNodeConfig`, en `app/flows/model.py`): `interval` (`Interval`), `channels`, `overwrite`, `schedule` (`Schedule`, `desactivada` por defecto) y `active` (`true` por defecto). Todo es opcional al guardar, como el resto de nodos, y obligatorio para ejecutar. La zona horaria **no** se guarda en la caja: se usa la de la plataforma en el momento de lanzarla.
- **API interna de la ingesta** (T1):
  - `POST /insight-downloads` con `{insight_flow_id, interval_from, interval_to, channels, overwrite, origin, user}` → `202 {run_id}` (`409` si esa caja ya tiene una descarga activa). La API resuelve el intervalo antes de llamar.
  - `GET /insight-downloads/{id}`, `GET /insight-downloads/{id}/log` y `GET /insight-downloads/{id}/conversations` (lista de `1CO`). Una descarga de un flujo de FE011 responde `404` en estas rutas. *(Ajustado en `/build` T1: en la ingesta no había rutas de ejecución independientes del flujo, y separar el prefijo deja intacto el contrato de FE011. El campo `insight_flow_id` solo aparece en las descargas de caja, porque el esquema de `DownloadRun` de FE011 es cerrado.)*
- **Ejecutor** (T4), cuando el nodo es `descarga`:
  1. resuelve el intervalo con la zona horaria de la plataforma y lanza la descarga;
  2. guarda `download_run_id` en el estado del nodo;
  3. sondea cada `poll_s` (2 s por defecto, inyectable) y copia los contadores en `NodeState.download`;
  4. al terminar, lee el subconjunto.

  Si el subconjunto está vacío, los nodos que dependen de la caja pasan a `omitido` con el motivo y la ejecución termina en `ok`. Si la ingesta deja de responder durante la ejecución, la caja queda en `error` con el mensaje de no disponible.
- **Subconjunto en el Sampling:** `candidates(config, subset)` aplica `parse_query` sin el intervalo de fechas (o con un intervalo que lo cubra todo) y filtra `c.id in subset` sobre `get_dataset()`.
- **«All conversations»:** `SamplingConfig.size: int | Literal["all"]`. Con `"all"`, `method` no se exige y `draw_sample` devuelve todas en orden cronológico. El aviso `large_sample` (`severity: warning`) se calcula en `validate` con la estimación. Si el Sampling va detrás de una caja, no hay aviso, porque el tamaño no se conoce hasta ejecutar.
- **Programador de la API** (T5): `FlowScheduler.tick(now)`:
  - recorre los flujos con una caja activa y programada y lanza los que tienen una ejecución pendiente (`next_occurrence` desde la última vez que se lanzaron);
  - la autoría de la ejecución es `{id: "system", name: "Scheduler"}`, con `origin: "programada"`;
  - si ya hay una ejecución en curso, la omite y anota la hora en la siguiente (`notes`);
  - si el flujo no valida, registra una ejecución `error` con los errores, sin lanzar nada.

  La última vez que se lanzó cada flujo se guarda en memoria y se inicializa con el instante de arranque, así que las perdidas no se recuperan. Corre en un hilo cada 30 s (desactivable en los tests).
- **Log de la descarga en la UI:** la API añade `GET /api/flows/{id}/runs/{run_id}/download` (estado y contadores) y `GET /api/flows/{id}/runs/{run_id}/download/log`, que reenvían a la ingesta con `flows:view`. La vista de la ejecución reutiliza el visor de log de FE011.

## Tareas

| Id | Título | Depende de | Criterios |
|---|---|---|---|
| T1 ✅ | Ingesta: descargas de una caja y subconjunto por ejecución | — | 4, 5 y 6 (datos), 19 (ingesta) |
| T2 | Modelo, reglas y validación de la caja `descarga` | — | 1, 2, 3 (salvo el servicio caído), 11 |
| T3 | Sampling «All conversations» y aviso `large_sample` | T2 | 10, 11 |
| T4 | Ejecución end-to-end: descarga, subconjunto y estado `omitido` | T1, T2, T3 | 3 (servicio caído), 4, 5, 6, 7, 8, 19 (API) |
| T5 | Programador de flujos de insights en la API | T4 | 9, 18 (API) |
| T6 | Front del editor: caja, reglas, panel del Sampling y textos | T2, T3 | 12, 13, 14, 16, 17 |
| T7 | Front de la ejecución, historial y listado | T4, T5, T6 | 15, 9 (próxima ejecución en el listado) |
| T8 | OpenAPI, conocimiento, recorrido en Chrome y gate | T1–T7 | 18, 20, 21 y conocimiento afectado |

### T1 — Ingesta: descargas de una caja y subconjunto por ejecución
- **Qué:**
  - migración `0008_insight_downloads.sql`, según el contraste;
  - `create_run` parametrizado (`overwrite`, `insight_flow_id`);
  - `RunExecutor` inserta en `download_run_conversation` cada conversación `insertada` o `actualizada`, en la misma transacción que su carga;
  - rutas internas `POST /insight-downloads`, `GET /runs/{id}`, `GET /runs/{id}/log` y `GET /runs/{id}/conversations`, con el token interno.
- **Hecho cuando** (tests `pg` con el Genesys falso, primero en rojo):
  - una descarga de caja termina en `completada` y `/conversations` devuelve exactamente los `1CO` insertados y actualizados; las `omitida` y las que acaban con error no aparecen;
  - una segunda descarga del mismo intervalo sin «Sobrescribir» devuelve un subconjunto vacío, y con «Sobrescribir» devuelve todas;
  - una segunda descarga activa de la misma caja da `409`;
  - borrar el `insight_flow` borra sus descargas y logs;
  - un `download_run` sin flujo, o con los dos, viola el `CHECK`;
  - sin token, `401`;
  - el test de secretos de FE011 (criterio 3) recorre también las salidas nuevas;
  - la suite de ingesta de FE011, FE013 y FE015 sigue en verde.
- **Conocimiento:** ADR-008 y el runbook de ingesta, en T8.

### T2 — Modelo, reglas y validación de la caja `descarga`
- **Qué:**
  - mover `Interval`, `Schedule`, `resolve_interval` y `next_occurrence` a `app/flows/download_config.py`, con `ingestion/flows.py` reexportándolos;
  - `DownloadNode` y `DownloadNodeConfig`, con la regla «programada exige intervalo relativo»;
  - `NODE_TYPES["descarga"] = "Genesys download"` en el catálogo;
  - reglas de conexión (`ALLOWED`, `SINGLE_INPUT` con `sampling`, una salida en `descarga`, «A Sampling can only receive a Genesys download»), con sus casos en `rules.cases.json`;
  - como máximo una caja por grafo en `parse_graph`;
  - en `validate`: `download_incomplete`, `download_without_output`, `download_needs_real_origin` y ajuste de `node_loose`, porque un Sampling con entrada de caja ya no está suelto y un Sampling sin caja sigue siendo inicio.
- **Hecho cuando:**
  - test de ida y vuelta del grafo con la caja;
  - `422` con ruta para cada rango no válido y para la programación con intervalo específico, con el mismo mensaje que FE011;
  - cada caso nuevo de `rules.cases.json` pasa en el backend (el front, en T6);
  - una segunda caja da `422`;
  - un test por código de validación;
  - los tests de FE004, FE011, FE012, FE013 y FE014 siguen en verde sin cambiarlos.

### T3 — Sampling «All conversations» y aviso `large_sample`
- **Qué:**
  - `size: int | "all"` en `SamplingConfig`;
  - `draw_sample` con `"all"`;
  - la completitud no exige método con `"all"`;
  - `POST /api/flows/sampling/estimate` acepta `size: "all"` (y `after_download: true`, que devuelve `available: null` con `depends_on_download: true`);
  - aviso `large_sample` si la estimación pasa de 1.000, que dice si algún Prompt usa un proveedor real.
- **Hecho cuando:**
  - con «All conversations», la ejecución de un flujo sin caja procesa todas las conversaciones que cumplen los filtros (recuento contra `run_query`, no un número fijo);
  - hay test del aviso por encima y por debajo de 1.000, usando un dataset de prueba inyectado;
  - un grafo de FE004 guardado con método y tamaño se ejecuta igual (misma semilla, misma muestra);
  - ida y vuelta de `"all"`.

### T4 — Ejecución end-to-end: descarga, subconjunto y estado `omitido`
- **Qué:**
  - el `FlowExecutor` trata el nodo `descarga` según las decisiones de diseño, con `NodeState.download` (`run_id`, contadores y estado);
  - estado `omitido`;
  - `candidates(config, subset)`;
  - el error de validación `ingestion_unavailable` cuando el grafo tiene caja y la ingesta no responde;
  - rutas de reenvío `…/runs/{run_id}/download` y `…/download/log`.
- **Hecho cuando** (tests con un `IngestionClient` doble y uno `pg` de punta a punta con el Genesys falso):
  - la caja pasa por `en_curso` con contadores que no decrecen y ningún otro nodo empieza antes de que termine;
  - `completada` o `completada_con_avisos` → la caja queda en `ok` y el Sampling solo ve el subconjunto: 5 conversaciones nuevas frente a 20 ya guardadas del mismo intervalo;
  - descarga en `error` → la caja y la ejecución acaban en `error` y los nodos siguientes quedan en `pendiente`;
  - subconjunto vacío → los nodos siguientes quedan en `omitido` con el motivo y la ejecución en `ok`, sin llamadas al `PromptRunner` (doble que cuenta las llamadas);
  - la ingesta cae a mitad → `error` con «The ingestion service is not available»;
  - `409` con una ejecución en curso;
  - en el test de punta a punta, el Output «Guardar en campos» escribe en las conversaciones del subconjunto;
  - una muestra vacía sin caja sigue siendo `error` (FE004);
  - ninguna respuesta nueva contiene secretos (se amplía el test de FE011).

### T5 — Programador de flujos de insights en la API
- **Qué:**
  - `app/flows/scheduler.py` con `tick(now)` y un hilo en el `lifespan` de la API, desactivable con `FLOW_SCHEDULER=0` y apagado en los tests;
  - `Run.origin` (`manual` o `programada`) y `Run.notes`;
  - la ejecución programada que no valida queda registrada como `error`;
  - `next_run` en el listado `GET /api/flows` para los flujos con caja programada y activa.
- **Hecho cuando** (reloj simulado):
  - «cada 1 hora» lanza una vez por hora y no dos;
  - «diaria 08:00» se lanza en su zona horaria;
  - con una ejecución en curso, se omite y la siguiente lleva la nota;
  - una caja inactiva no se lanza por programación pero sí a mano;
  - tras recrear el `FlowStore` desde la persistencia (doble de FE015), el flujo sigue programado y no lanza las perdidas;
  - con origen «Sintético», la ejecución programada queda en el historial como `error` con `download_needs_real_origin`;
  - permisos: con solo `flows:view`, `403` al guardar un grafo con programación y al ejecutar.

### T6 — Front del editor: caja, reglas, panel del Sampling y textos
- **Qué:**
  - extraer de `DownloadFlowForm` los controles de intervalo, canales y programación;
  - nodo `descarga` en `nodes.tsx`, la paleta y `graph.ts`;
  - `DownloadPanel` con intervalo, canales, «Sobrescribir», programación y activo, y los errores por campo del `422`;
  - reglas en `rules.ts` (casos compartidos), con la paleta deshabilitada y una explicación si ya hay caja;
  - `SamplingPanel` con la opción «All conversations» (oculta método y tamaño) y sin intervalo de fechas detrás de una caja, con el texto explicativo y la estimación «depends on the download»;
  - textos `es` y `en`.
- **Hecho cuando** (Vitest):
  - `rules.test.ts` pasa los casos nuevos;
  - hay tests de componente del panel de la caja: valores, validación y programación deshabilitada con intervalo específico;
  - hay tests del Sampling con y sin caja y con «All conversations»;
  - la conversión JSON ↔ lienzo con la caja es de ida y vuelta;
  - sin `flows:edit`, el panel de la caja está deshabilitado;
  - el test de paridad de i18n sigue en verde;
  - `DownloadFlows.test.tsx` sigue en verde tras la extracción;
  - `npm run lint` y `npm run build` terminan sin errores.

### T7 — Front de la ejecución, historial y listado
- **Qué:**
  - `RunPage` muestra la caja con su estado y contadores, y un enlace a su log (visor de FE011 sobre las rutas de reenvío);
  - estado `omitido` con su motivo en `StatusBadge` y en los nodos;
  - origen `manual`/`programada` y notas en el historial;
  - columna de próxima ejecución en `FlowsPage` para los flujos de insights con caja programada.
- **Hecho cuando** (Vitest con API simulada):
  - el polling actualiza los contadores de la caja hasta el final;
  - el enlace abre el log;
  - `omitido` se muestra con su motivo;
  - el historial muestra el origen;
  - el listado muestra la próxima ejecución;
  - textos `es` y `en`.

### T8 — OpenAPI, conocimiento, recorrido en Chrome y gate
- **Qué:**
  - `backend/openapi.yaml` (nodo `descarga`, `size: "all"`, `omitido`, `large_sample`, `origin`, `next_run` y las rutas de reenvío) y el OpenAPI interno de la ingesta;
  - actualizar en el vault:
    - [arquitectura](../../vault/arquitectura/arquitectura-de-la-plataforma.md): ejecución end-to-end, programador de la API y subconjunto;
    - [contrato de la API](../../vault/arquitectura/contrato-api-front-back.md);
    - [runbook de ingesta](../../vault/operaciones/runbook-ingesta-de-genesys.md): diagnosticar desde la caja hasta su log;
    - [glosario](../../vault/glosario/terminos-del-harness.md);
    - ampliar [ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md) con las descargas de caja y el programador en la API;
    - lecciones nuevas, si las hay.
  - recorrido en Chrome con `./scripts/dev.sh` en puertos propios (18000 y 18001), parando por PID, del criterio 21, con la evidencia en `VERIFY.md`.
- **Hecho cuando:**
  - el recorrido de rutas del OpenAPI cubre las nuevas;
  - `python scripts/audit_vault.py` termina con código 0;
  - `./scripts/ci.sh` termina con código 0;
  - el recorrido de Chrome está completo, sin errores de consola.

## Riesgos del plan

- **El programador de la API duplica el patrón del de la ingesta.** Se acepta para no sacar las ejecuciones de insights de la memoria de la API (fuera de alcance de la spec). Las dos implementaciones comparten `next_occurrence`, que se mueve en T2.
- **El índice único de ejecución activa ahora cubre dos columnas.** Si el `CHECK` y los índices parciales complican la migración con datos de FE011, T1 lo prueba migrando una base con flujos y ejecuciones existentes.
- **Esperar la descarga con sondeo ocupa un hilo de la API** durante toda la descarga, como ya ocurre con los Prompt largos. Se acepta en el piloto; con muchas ejecuciones simultáneas habría que mover el ejecutor a una cola (otra feature).

# FE011 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-10-12. Siguiente paso: `/build`, una tarea cada vez y en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| `backend/app/ids.py` | `new_id(prefix, rng)` (v4) y `stable_id(prefix, name)` (v5 sobre `"{prefix}:{name}"`) con un namespace del proyecto. `PREFIXES` no necesita prefijos nuevos. | Los identificadores reales se derivan con `stable_id(prefix, f"genesys:{id_genesys}")`. El prefijo `genesys:` evita colisiones con los nombres del generador sintético (criterio 9). |
| `backend/app/flows/` y `routers/flows.py` | Los flujos de insights viven en memoria (`FlowStore`) con `1FL`, `1RN` y `BackgroundTasks`. `GET /api/flows/{flow_id}` captura cualquier segmento. | Los flujos de descarga no se mezclan con `FlowStore`: viven en el servicio de ingesta y se exponen en `/api/download-flows`, para no chocar con `/api/flows/{flow_id}`. FE004 no cambia. |
| `frontend/src/flows/FlowsPage.tsx` y `api.ts` | Listado, creación y acciones de los flujos de insights. | T7 une los dos listados, añade «Tipo» y elige el tipo al crear. |
| `routers/config.py` y `config/tabs/SourcesTab.tsx` | Conectores mock con «Sincronizar» auditado (`fuentes`). | T6 y T7 añaden el estado de Genesys sin tocar los conectores mock (criterio 22). |
| `tests/test_auth.py` | Recorre `app.openapi()` y exige `401` o `403` en toda ruta `/api` salvo `PUBLIC_ROUTES` ([lección 1](../../vault/aprendizaje/lecciones-construccion-plataforma.md)). | Las rutas nuevas entran solas en el recorrido; el rol de solo lectura se crea con `tests/roles.py`. |
| `backend/requirements.txt` | FastAPI 0.141, httpx 0.28 y Python 3.14. | Se añade `psycopg[binary]` 3.3.6, que tiene rueda `cp314` (comprobado). httpx ya sirve para llamar a Genesys y para el `MockTransport` del Genesys falso. |
| Docker | CLI de Docker 29.5 y Compose 5.5 de Homebrew, **sin Docker Desktop**: el daemon es **Colima** (contexto `colima`, VM de 8 CPU y 12 GB). Arrancado el 2026-10-12 con `colima start`; `postgres:16` (16.15) descargada y probada. | El `README` documenta `colima start` como requisito. `ci.sh` comprueba `docker info` y, si falla, sugiere `colima start`. |
| `scripts/ci.sh` y `.github/workflows/ci.yml` | El backend se ejecuta con dos datasets (FE009); no hay servicios. | T1 añade PostgreSQL (`docker compose` en local; contenedor de servicio en GitHub) y una pasada `-m pg`. |
| [ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md), [ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md), [arquitectura](../../vault/arquitectura/arquitectura-de-la-plataforma.md), [contrato](../../vault/arquitectura/contrato-api-front-back.md), [registro](../../vault/ingenieria/registro-de-identificadores.md), [estado operativo](../../vault/operaciones/estado-operativo.md), [glosario](../../vault/glosario/terminos-del-harness.md), [lecciones](../../vault/aprendizaje/lecciones-construccion-plataforma.md) | Todas existen y siguen en `active`. | T9. |
| [Lecciones](../../vault/aprendizaje/lecciones-construccion-plataforma.md) | 19 y 20 (segundo plano y carreras), 5 y 28 (fechas en tests), 7 (secretos como `bytes`), 10, 21 y 24 (gate por código de salida), 31 (helpers en tests). | Se aplican en T4 y T5 (gancho por paso y servidor real), en T3 (fechas fijas), en T1 (token interno) y en todos los commits. |

## Decisiones de diseño

- **«Nuevo backend» = otro proceso, mismo proyecto Python.** El paquete `backend/ingestion/` vive junto a `app/`, comparte el venv y `requirements.txt`, y se arranca con `uvicorn ingestion.main:app --port 8001`. Importa `app.ids` y `app.clock`, porque los identificadores solo se generan con `ids.py`, pero no importa nada más de `app`. Un test estructural lo comprueba, y otro comprueba que `app` no importa `ingestion`. Se descarta un proyecto aparte: duplicaría `ids.py` o lo convertiría en una librería publicada.
- **Configuración:** un lector mínimo del `.env` de la raíz (`ingestion/settings.py`, sin dependencias) con una lista blanca de claves por proceso.
  - El servicio de ingesta lee `GENESYS_*`, `DATABASE_URL` e `INGESTION_TOKEN`.
  - La API lee solo `INGESTION_URL` (por defecto `http://localhost:8001`) e `INGESTION_TOKEN`.
  - Un test comprueba que la configuración de la API nunca contiene `GENESYS_*` (criterio 3).
  - Se añade un `.env.example` versionado, con las claves y sin valores.
- **PostgreSQL:** `docker-compose.yml` con `postgres:16`, un volumen nombrado y el puerto 5432. Bases `speech_analytics` y `speech_analytics_test`.
  - El esquema se gestiona con **migraciones SQL numeradas** (`ingestion/migrations/0001_*.sql`), aplicadas al arrancar dentro de una transacción y registradas en `schema_migrations`. No se usa Alembic: no hay ORM, y son pocas tablas.
  - Acceso con `psycopg` 3 y SQL explícito, con una conexión por operación de un pool pequeño (`psycopg_pool` se valora en T1; si no, conexiones directas).
- **Tablas:**
  - `conversation`: `1CO`, `genesys_id` único, canal, inicio, fin, duración, `external_tag`, ANI, DNIS, `transcript_quality`, `customer_id` y analítica escalar en columnas.
  - `segment`: los tramos.
  - `turn`: hablante, texto, offset, sentimiento, `delivered`, `genesys_user_id` y `message_id`.
  - `topic_hit`: los temas detectados.
  - `analysis`: estado, fuente y campos del análisis, todos nulos.
  - `raw_payload`: respuestas originales en `jsonb`, por tipo.
  - Catálogos: `queue`, `agent`, `flow`, `wrapup` y `division`.
  - `download_flow`, `download_run` y `run_log`.
- **Cliente de Genesys** (`ingestion/genesys/client.py`): httpx síncrono con un `transport` inyectable, de modo que el Genesys falso es un `httpx.MockTransport` que sirve fixtures y nunca toca la red.
  - Tabla de regiones (`eu-west-1` → `mypurecloud.ie`, etc.).
  - Token en caché hasta 5 minutos antes de caducar, con el reloj inyectable de `app.clock`.
  - Reintentos: `429` con `Retry-After`; `5xx` y fallos de red, 3 veces con espera creciente; `401` sin reintentos («Credenciales de Genesys no válidas»); `403` sin reintentos, con la ruta.
  - Un filtro de redacción quita el secreto, el token y las URL firmadas de cualquier mensaje de error o de log (`redact()`), y se prueba en cada camino de error.
- **Pipeline** (`ingestion/pipeline/`): funciones puras por etapa, separadas del I/O, para probar la normalización solo con fixtures:
  - `search(interval)`: tramos de 7 días, paginación y filtro de canales y de conversaciones terminadas;
  - `fetch(conversation)`: STA, transcripciones con desduplicado por `transcriptId` y tolerancia a `404`, y mensajes en bloque si es chat;
  - `normalize(raw) → NormalizedConversation`;
  - `load(conn, normalized)`: `upsert` en una transacción por conversación;
  - `Analyzer.analyze(normalized) → Analysis`: `PendingAnalyzer` en esta fase.
- **Ejecutor y programador** en el servicio de ingesta:
  - las ejecuciones corren en un `ThreadPoolExecutor` (máximo 2 en paralelo, una por flujo, con un arranque atómico en la base de datos: `409`);
  - el programador es un hilo con un `tick()` cada 30 s que calcula las ejecuciones debidas con el reloj inyectable. Los tests llaman a `tick()` con un reloj simulado, sin hilos;
  - cada paso del ejecutor emite un gancho (`on_step`) para observar estados intermedios, como en FE004 ([lección 19](../../vault/aprendizaje/lecciones-construccion-plataforma.md)).
- **Zona horaria de «hoy» y «ayer»:** la configuración vive en la memoria de la API. La API envía la zona horaria vigente al crear o guardar un flujo de descarga, y el flujo la guarda. Las ejecuciones (también las programadas) resuelven el intervalo con ella.
- **Rutas de la API** (`app/routers/downloads.py`; proxy con httpx al servicio de ingesta y token interno):
  - `GET/POST /api/download-flows`;
  - `GET/PATCH/DELETE /api/download-flows/{id}`;
  - `POST /api/download-flows/{id}/runs`;
  - `GET /api/download-flows/{id}/runs` y `GET /api/download-flows/{id}/runs/{run_id}`;
  - `GET /api/download-flows/{id}/runs/{run_id}/log?after=&level=`, con el log descargable en `text/plain` con `?format=text`;
  - `GET /api/config/connectors/genesys` y `POST /api/config/connectors/genesys/test`.

  La API comprueba los permisos y añade el usuario. Si el servicio no responde, devuelve `503` con «El servicio de ingesta no está disponible». El flujo de descarga usa `1FL` y su ejecución `1RN`, generados en el servicio de ingesta con `ids.new_id`.
- **Tests con PostgreSQL:** se marcan con `@pytest.mark.pg` y usan `TEST_DATABASE_URL`. Cada test recrea el esquema en una base efímera (`DROP SCHEMA … CASCADE` + migraciones).
  - Sin `TEST_DATABASE_URL`, se saltan con un motivo visible.
  - `ci.sh` y GitHub la definen y activan `REQUIRE_PG=1`, con lo que un test `pg` saltado **falla**. Así el gate nunca pasa en verde sin haberlos ejecutado.
  - Las dos pasadas de FE009 siguen con `-m "not pg"`.
- **Fixtures:** `scripts/capture_genesys_fixtures.py` (solo lectura, ejecución manual con el `.env`) descarga las conversaciones de referencia y las sanea:
  - quita las URL firmadas, el `organizationId` y los tokens;
  - conserva ANI y `externalTag`.

  Las guarda en `backend/tests/fixtures/genesys/<tipo>/`. Un test comprueba que ninguna fixture contiene `https://` a buckets, `organizationId` ni nada con forma de token.
- **Front:** módulo `frontend/src/downloads/`:
  - `api.ts` y `types.ts`;
  - el formulario del flujo de descarga en `/flujos/descargas/:id`;
  - la vista de ejecución con el log en `/flujos/descargas/:id/ejecuciones/:runId`.

  `FlowsPage` pide los dos listados y los une; si el de descargas responde `503`, muestra los de insights y un aviso. La card de Genesys va en `SourcesTab`.

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | PostgreSQL, esqueleto del servicio de ingesta, migraciones y gate | — | 1, 2 (esquema), 3 (configuración), 5, 23 (parcial) |
| T2 | Cliente de Genesys, Genesys falso y fixtures de referencia | T1 | 3, 4, 6 (HTTP), 24 |
| T3 | Normalización: turnos, hablantes, sentimiento, calidad y analítica | T2 | 7, 8, 9, 27 (sobre fixtures) |
| T4 | Extracción, carga idempotente, `Analyzer`, ejecutor y log | T3 | 2 (lectura), 6, 10, 11, 17, 18 (backend), 25 |
| T5 | Flujos de descarga, ejecución manual y programador | T4 | 13, 14, 15, 16, 19 (backend) |
| T6 | Rutas de la API: proxy, permisos, `503` y estado del conector | T5 | 12 (backend), 20, 21, 22 (backend), 23 |
| T7 | Front: tipos de flujo, formulario, ejecución con log, historial y conector | T6 | 12, 13, 15, 18, 19, 22 |
| T8 | Prueba con las conversaciones del día y recorrido en Chrome | T7 | 26, 27, 28 |
| T9 | Conocimiento, documentación y gate final | T1–T8 | 23 y conocimiento afectado |

### T1 — PostgreSQL, esqueleto del servicio y gate

- **Qué:**
  - `docker-compose.yml`, `.env.example` y `psycopg[binary]` en `requirements.txt`;
  - `backend/ingestion/` con `main.py` (FastAPI, `/health`, OpenAPI propio, CORS cerrado), `settings.py` (lista blanca), `security.py` (token interno comparado como `bytes`, [lección 7](../../vault/aprendizaje/lecciones-construccion-plataforma.md)) y `db.py`;
  - `migrations/0001_initial.sql` con todas las tablas de la decisión de diseño;
  - fixture `pg` y marcador `REQUIRE_PG` en `tests/conftest.py`;
  - `ci.sh` y `ci.yml` con PostgreSQL y la pasada `-m pg`;
  - una sección «Servicio de ingesta» en `README.md`.
- **Hecho cuando:**
  - `docker compose up -d` y `uvicorn ingestion.main:app --port 8001` arrancan, y `GET /health` con el token responde `200`;
  - tests: sin token o con uno erróneo (también no ASCII), `401`; las migraciones dos veces conservan una fila insertada; la configuración de la API no contiene claves `GENESYS_*`; estructural, `ingestion` solo importa de `app` los módulos `ids` y `clock`, y `app` no importa `ingestion`;
  - `./scripts/ci.sh` termina con código 0 con la pasada `pg`, y falla si Docker está parado (comprobado a mano y anotado en Progreso).

### T2 — Cliente de Genesys, Genesys falso y fixtures

- **Qué:**
  - `ingestion/genesys/regions.py`, `client.py` (OAuth, caché del token, reintentos, `redact`) y `fake.py` (`MockTransport` con rutas de analítica, STA, transcript URL, descarga del JSON, mensajes en bloque, colas, usuarios, wrap-ups, flujos y divisiones, más errores programables por ruta);
  - `scripts/capture_genesys_fixtures.py` y las fixtures saneadas de los 7 tipos de la tabla de la spec, capturadas de la cuenta real (solo lectura).
- **Hecho cuando:** hay tests de:
  - la caché del token con reloj simulado (no se renueva antes de tiempo y sí cerca de caducar);
  - `429` con `Retry-After` (respeta la espera, sin dormir de verdad: espera inyectable);
  - `5xx` tres veces y luego éxito; `5xx` persistente;
  - `401` (mensaje y sin reintentos) y `403` (ruta en el mensaje);
  - la redacción: en cada camino de error, ningún mensaje contiene el secreto, el token ni la URL firmada;
  - el saneado de las fixtures.

  Las fixtures existen para `37dcbccf`, `7b94988a`, `687f2225`, `8d29170a`, `f7e79502`, `9e3ec75a` y `c870bc58`.

### T3 — Normalización

- **Qué:** `ingestion/pipeline/normalize.py`, con funciones puras de las respuestas crudas a `NormalizedConversation`:
  - tramos y recorrido;
  - turnos de voz (unión y desduplicado de transcripciones) y de chat (mensajes de la API, con el respaldo de la transcripción agrupada por `messageID`);
  - hablantes (`userIds` o `createdBy`, y si no, el tramo);
  - offsets no negativos y sentimiento por turno;
  - calidad de la transcripción;
  - analítica (teléfonos sin `tel:`, cierre, contención, tiempos sumados por tramo, métricas de chat, STA, confianza media) y temas enlazados a su turno;
  - identificadores v5.
- **Hecho cuando:**
  - hay un test por fixture con **todos** los valores esperados del criterio 27, más tests de los casos límite: transcripción vacía, `404` de una comunicación ya incluida, frase `internal` sin `userIds` dentro del tramo de un agente, API de mensajes caída (respaldo con mensaje no entregado sin texto), sentimiento ausente frente a lista vacía, métrica que falta (queda vacía, no a 0) y conversación sin contacto externo ni ANI;
  - un test comprueba que los `1CO`, `1CU`, `1AG` y `1QU` reales no coinciden con ninguno del dataset sintético;
  - las mutaciones de la regla de hablantes, del cálculo de calidad y del agrupado por `messageID` rompen al menos un test cada una (`python -B`, [lección 23](../../vault/aprendizaje/lecciones-construccion-plataforma.md)).

### T4 — Extracción, carga, `Analyzer`, ejecutor y log

- **Qué:**
  - `search` (tramos de 7 días, paginación, filtros), `fetch` y `load` (`upsert` por conversación con borrado y reinserción de turnos, tramos y temas en la misma transacción);
  - `PendingAnalyzer`;
  - el ejecutor de una ejecución con contadores, log por etapa (sin texto de turnos) y gancho `on_step`;
  - la lectura interna `GET /conversations/{id}`.
- **Hecho cuando:** hay tests `pg` con el Genesys falso de:
  - un intervalo de 20 días con varias páginas: 3 consultas y todas las conversaciones;
  - conversaciones en curso y de otro medio omitidas y contadas;
  - repetir la ejecución: mismas filas en cada tabla y todas «actualizadas»;
  - una conversación que falla tras los reintentos: el resto se guarda y la ejecución acaba en `completada_con_avisos`;
  - `parcial` que pasa a `completa` en una segunda descarga;
  - la identidad de los contadores;
  - el log: entradas por etapa y por conversación con aviso, sin texto de turnos ni secretos;
  - un `Analyzer` de test que rellena summary y main topic y se lee con `fuente: llm`;
  - estados intermedios observados con `on_step`;
  - 1.000 conversaciones sintéticas del Genesys falso en menos de 60 s.

### T5 — Flujos de descarga y programador

- **Qué:** en el servicio de ingesta:
  - CRUD de `download_flow` con validación (`422` por campo) del intervalo relativo («hoy», «ayer», horas, días), del específico (orden, 90 días, sin futuro), de los canales, de la programación (solo con relativo) y del estado activo;
  - ejecución manual (`202` y `409`);
  - historial con retención de 200;
  - log paginado (`after`) y filtrable;
  - `tick()` del programador con «cada N horas» y «diaria a una hora».
- **Hecho cuando:** hay tests `pg` de:
  - cada regla de validación;
  - «hoy» y «ayer» resueltos en la zona horaria guardada, con una fecha cercana a medianoche ([lección 5](../../vault/aprendizaje/lecciones-construccion-plataforma.md));
  - el `409` con una ejecución en curso (arranque concurrente determinista);
  - con reloj simulado: «cada 1 hora» se lanza una vez por hora y no dos; un flujo inactivo no se lanza; con una ejecución en curso, se omite y queda anotado en la siguiente;
  - la retención de 200;
  - reiniciar el servicio (crear una app nueva sobre la misma base) conserva flujos, ejecuciones y logs.

### T6 — Rutas de la API

- **Qué:** `app/routers/downloads.py` y las dos rutas de Genesys en `routers/config.py`:
  - cliente httpx del servicio de ingesta inyectable con `dependency_overrides`, con un tiempo de espera corto;
  - `503` si no responde;
  - `backend/openapi.yaml` regenerado;
  - el rol `flows:view` en `tests/roles.py`.
- **Hecho cuando:**
  - los tests (con un servicio de ingesta simulado en proceso) cubren cada ruta con `admin`, el rol de solo lectura (`403` en cada escritura y `200` en las lecturas) y sin sesión (`401`, ya cubierto por el recorrido del OpenAPI);
  - el `503` funciona en las rutas de descarga mientras `/api/flows` sigue respondiendo;
  - el usuario de la sesión llega a la ejecución manual, y la zona horaria vigente llega al crear y al guardar un flujo;
  - el estado del conector exige `config:view` y «Probar conexión» exige `config:edit`;
  - `export_openapi.py --check` y el validador pasan.

### T7 — Front

- **Qué:**
  - `FlowsPage`: une los listados, añade la columna «Tipo» y la próxima ejecución, el diálogo de creación con tipo y el aviso si las descargas no están disponibles;
  - el formulario del flujo de descarga, con errores por campo desde el `422` (patrón de FE005);
  - la vista de ejecución: estado y contadores con polling cada 2 s hasta terminar, log con filtro por nivel, carga incremental por `after` y botón «Descargar log»;
  - el historial;
  - la card de Genesys en `SourcesTab` con «Probar conexión»;
  - fechas solo con `lib/format.ts`.
- **Hecho cuando:** hay tests de front de:
  - el listado mixto con su columna «Tipo», y el aviso con `503`;
  - crear de cada tipo;
  - un `422` por campo que conserva lo escrito;
  - «programación con intervalo específico» rechazada;
  - la ejecución que pasa de `en_curso` a `completada` con polling y deja de pedir al terminar;
  - el filtro del log y la descarga;
  - la solo lectura sin `flows:edit` (sin acciones ni formulario editable);
  - la card de Genesys con sus estados cargando, error, conectado y credenciales no válidas.

  `npm test`, `npm run lint` y `npm run build` terminan con código 0.

### T8 — Prueba del día y recorrido en Chrome

- **Qué:** arrancar Postgres, el servicio de ingesta, la API y la web, y seguir los criterios 26–28 con las conversaciones del día de la cuenta real.
- **Hecho cuando:** `VERIFY.md` recoge:
  - el recuento de Genesys frente al guardado;
  - un tipo por fila, con su conversación y los valores comprobados con `GET /conversations/{id}`;
  - la segunda descarga sin duplicados;
  - el recorrido en Chrome con `admin` y con el rol de solo lectura, sin errores de consola.

  Si falta algún tipo ese día, se pide al usuario que lo genere antes de cerrar la tarea.

### T9 — Conocimiento, documentación y gate

- **Qué:** las entradas de «Conocimiento afectado» de la spec:
  - ADR-008 nuevo y ADR-002 ampliado;
  - arquitectura (componentes, flujo de datos y límite de persistencia) y contrato de la API (rutas nuevas, `503` y la API interna);
  - registro de identificadores (la excepción de los v5 de Genesys);
  - una entrada de Producto, «Datos de Genesys para STA»;
  - estado operativo y un runbook nuevo;
  - glosario y lecciones de la construcción;
  - `README.md`, `backend/README.md`, `frontend/README.md` y los índices de cada área.
- **Hecho cuando:**
  - cada entrada cita su fuente y está enlazada desde su índice;
  - `python3 scripts/audit_vault.py` termina con código 0;
  - `./scripts/ci.sh` termina con código 0, encadenado al commit por su código de salida ([lección 24](../../vault/aprendizaje/lecciones-construccion-plataforma.md)).

## Riesgos del plan

- **Docker es un requisito nuevo del gate.** Sin el daemon (Colima en esta máquina), `ci.sh` falla (es intencionado). T1 lo deja explicado en el `README` y en el mensaje de error. Colima no arranca solo al iniciar sesión: tras reiniciar el equipo hay que ejecutar `colima start`, o configurarlo con `brew services start colima`.
- **Las fixtures dependen de que las conversaciones de hoy sigan en Genesys** cuando se ejecute T2. Las respuestas del sondeo están en el scratchpad de esta sesión, que es temporal; si se pierden, se vuelven a capturar con el script, y los valores esperados del criterio 27 se recalculan solo si Genesys hubiera completado alguna transcripción.
- **El sentimiento neutro (`0`) es una hipótesis de la spec.** T3 la aísla en una sola función, para cambiarla sin tocar el resto.
- **T4 y T7 son las tareas más grandes.** Si una supera una sesión, se parte: T4 en «extracción y carga» y «ejecutor y log»; T7 en «listado y formulario» y «ejecución, log y conector».

## Progreso

### T1 — Hecha (2026-10-12)

- **Rojo:** los 20 tests nuevos (`test_ingestion_service.py`, `test_ingestion_settings.py`) fallaban en la recogida porque no existían `ingestion`, `app.envfile` ni `psycopg`.
- **Verde:** 17 tests sin PostgreSQL y 3 `pg` (salud con base, esquema completo, migraciones idempotentes que conservan filas).
- **Mutaciones** (`python -B`, sin caché de bytecode): mueren las 7. Son el token que solo comprueba el esquema, la app sin guardia de token, el token en el `repr`, la API leyendo el secreto de Genesys, el fichero con prioridad sobre el entorno, las migraciones no idempotentes y la salud sin comprobar la base. La mutación del fichero con prioridad sobre el entorno sobrevivió al principio, porque el test usaba una clave que no estaba en el fichero; se reforzó el test.
- **Servidor real:** `uvicorn ingestion.main:app --port 8001` con el `.env`. Sin token, `401`; con token, `{"status":"ok","database":"ok"}`; `/docs`, `200`. La migración `0001_initial` queda en `schema_migrations` de `speech_analytics`, y el log no contiene «secret» ni «token».
- **Gate:** `./scripts/ci.sh` termina con código 0, con 745 + 745 tests sin `pg` y 3 `pg`. Con `DOCKER_HOST` apuntando a un socket inexistente falla con código 1 y el mensaje «Docker no responde. Arranca el daemon (en local, 'colima start')…». Con `REQUIRE_PG=1` y sin `TEST_DATABASE_URL`, pytest termina con código 1.
- **Hallazgo ajeno a FE011:** el gate fallaba en `npm audit` por un aviso «high» nuevo, `source-map-js` 1.2.1 ([GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)), dependencia transitiva de Tailwind, Vite y jsdom. `npm audit fix`, sin `--force`, solo cambia `package-lock.json` a la 1.2.2. Va en un commit aparte. Los avisos «moderate» de `swagger-ui-react` ya existían, y el gate solo bloquea los «high».
- **Desviación del plan:** `ingestion` puede importar también `app.envfile` (el lector del `.env` con lista blanca), además de `ids` y `clock`. El test estructural lo refleja. No se usa `psycopg_pool`: el servicio abre una conexión por operación, y se revisará en T4 si el rendimiento lo pide.

### T2 — Hecha (2026-10-12)

- **Rojo:** `test_genesys_client.py` fallaba en la recogida, porque no existía `ingestion.genesys`.
- **Verde:** 27 tests del cliente y del Genesys falso, y 18 de fixtures.
  - **Cliente:** región, caché del token con reloj simulado, `Bearer` en la API y sin él en URL firmadas, credenciales malas sin reintentos, token renovado una vez, `429` con `Retry-After`, `5xx` con 1, 2 y 4 s, fallos de red, `403`, `404` y `400` sin reintentos, y el permiso que falta en el mensaje del `403`.
  - **Redacción:** en 6 caminos de error, ningún mensaje contiene el secreto, el token ni la URL firmada.
- **Mutaciones:** mueren las 17 (cliente, Genesys falso y saneado). «El falso no comprueba el token» sobrevivió al principio; se añadió un test de que el falso rechaza tokens desconocidos.
- **Fixtures:** capturadas de la cuenta real con `scripts/capture_genesys_fixtures.py`, que es solo lectura y usa el propio cliente; es la prueba del cliente contra Genesys de verdad. Son **10** conversaciones, no 7: se añaden `voz_sin_transcripcion` (`87a83caa`), `chat_bot_agente_corto` (`90116482`) y `chat_no_entregado_mixto` (`d74fc0d8`, con un mensaje entregado y otro no), que cubren casos de la tabla de la spec sin coste extra.
  - Ocupan 952 kB, sobre todo por `words`, `decoratedWords` y `alternatives` de las frases de voz. Se conservan sin recortar para que la normalización trabaje sobre respuestas idénticas a las reales.
  - En el repositorio no aparece el identificador real de la organización (comprobado con `grep`).
- **Desviación:** el falso modela **un documento de transcripción por comunicación** (con varias transcripciones dentro), como la API real, y no una lista de documentos como decía la primera versión del diseño.

### T3 — Hecha (2026-10-12)

- **Rojo:** `test_ingestion_normalize.py` fallaba en la recogida, porque no existían `ingestion.pipeline.normalize` ni `ingestion.pipeline.raw`. Con la primera versión fallaron 4 tests por dos hechos de Genesys que no conocíamos (ver «Hallazgos»).
- **Verde:** 23 tests sobre las 10 fixtures, con los valores del criterio 27, más los casos límite del plan:
  - transcripción vacía;
  - `404` de una comunicación ya incluida;
  - frase `internal` sin `userIds` en el tramo del agente, y `userIds` sin tramo de agente;
  - API de mensajes caída, con respaldo por `messageID`, textos idénticos a los de la API y el mensaje no entregado contado sin texto;
  - sentimiento ausente frente a lista vacía, y sentimiento de STA ausente;
  - métrica que falta, que queda vacía y no a 0;
  - conversación sin contacto externo ni ANI;
  - transcripción repetida en dos comunicaciones;
  - identificadores que no colisionan con los del dataset sintético;
  - la entrada cruda, que no se modifica.
- **Mutaciones** (`python -B`): mueren las 16 aplicables (hablantes por `userIds`, por tramo y sin bot; autor de los mensajes de chat; calidad parcial y sin transcripción; agrupado por `messageID`; desduplicado de `transcriptId`; sentimiento neutro por defecto; offsets no negativos; respaldo del ANI; bot solo si el flujo de entrada escribe; entregado o no; espacio `genesys:` de los identificadores; sentimiento de STA). Al principio sobrevivieron tres (ignorar `userIds`, no agrupar por `messageID` y no desduplicar `transcriptId`), porque ninguna fixture distinguía el caso; se añadió un test para cada una.
- **Resumen por fixture:** coincide con la tabla de la spec. Por ejemplo, `7b94988a` tiene 40 turnos (24 del bot, 2 del agente, 14 del cliente), 8 temas y `derivada`. `c870bc58` tiene 8 tramos (dos de cada tipo) y 9 turnos. `687f2225` queda `parcial` con el aviso «intervino agente y bot sin frases».
- **Hallazgos** (añadidos a la spec):
  1. El resumen de STA trae `sentimentScore`, `sentimentTrend` y `sentimentTrendClass` de la conversación. `customer_sentiment` usa `sentimentScore` y, si no está, la media de los turnos del cliente.
  2. El `phraseIndex` de las entradas de sentimiento no es el de la frase. El sentimiento y los temas se enlazan por lado, instante y texto (`_phrase_for`).
  3. Los mensajes del bot en la API de mensajes traen `originatingEntity: Bot` y no tienen `createdBy`. Se usa la ausencia de `createdBy`, como dice la spec; `originatingEntity` queda en la respuesta original.
- **Desviaciones:**
  - El Genesys falso usa `RawConversation`, la misma estructura que normaliza la ingesta, en lugar de su propia clase.
  - La calidad `parcial` también tiene en cuenta un bot que intervino sin frases (IVR con `tIvr > 0`, o un flujo de entrada que escribió), como dice el criterio 7.

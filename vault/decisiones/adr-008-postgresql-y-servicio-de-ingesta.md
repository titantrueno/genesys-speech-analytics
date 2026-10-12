---
title: "ADR-008 — PostgreSQL y servicio de ingesta de Genesys aparte"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, genesys, ingesta, postgresql, persistencia, fe011]
created: 2026-10-12
updated: 2026-10-12
---

# ADR-008 — PostgreSQL y servicio de ingesta de Genesys aparte

## Contexto

FE011 trae conversaciones reales de una organización de Genesys Cloud: transcripciones, mensajes de chat y analítica ([spec](../../features/FE011-ingesta-de-conversaciones-genesys/spec.md)).

- Hasta entonces la plataforma no tenía persistencia: el dataset era mock y en memoria ([ADR-002](adr-002-stack-vite-fastapi-mock.md)).
- Las credenciales de Genesys son un secreto que solo debe conocer quien descarga ([gobierno del vault](../Governance.md)).
- Genesys da la transcripción y su analítica, pero no el análisis que usa la plataforma (summary, main topic de la taxonomía, CSAT…). Ese análisis llegará en una fase posterior con un LLM.

## Decisión

- **PostgreSQL 16 en Docker** (`docker-compose.yml`, volumen persistente, solo en `127.0.0.1`). En la máquina de desarrollo el daemon es Colima. El esquema se gestiona con **migraciones SQL numeradas** (`backend/ingestion/migrations/`), aplicadas al arrancar con un cerrojo consultivo, sin ORM.
- **El «nuevo backend» es otro proceso del mismo proyecto Python** (`backend/ingestion/`, `uvicorn ingestion.main:app`):
  - Comparte venv y `requirements.txt` con la API.
  - Solo importa de `app` los módulos `ids`, `clock` y `envfile`, porque los identificadores se generan en un único sitio. La API no importa `ingestion`. Un test estructural lo comprueba.
  - Es el **único** que lee `GENESYS_*`. Cada proceso lee del `.env` solo su lista blanca de claves (`app/envfile.py`).
- **La API es la única puerta.** El front solo habla con la API, que comprueba la sesión y los permisos (`flows:view`/`flows:edit`, `config:view`/`config:edit`), añade la autoría, la zona horaria y quién lanza, y delega en el servicio de ingesta con un **token interno**. Si el servicio no responde, falta el token o lo rechaza, la API devuelve `503`.
- **Analítica separada del análisis.** La analítica de Genesys (tramos, contención, tiempos, métricas de chat, Speech & Text Analytics, acústica) va en columnas filtrables y en `metrics` (`jsonb`). El análisis de la plataforma va en `analysis`, en estado `pendiente`, con `fuente` `genesys` o `llm`. Las respuestas originales se guardan en `raw_payload` para poder reanalizar.
- **Turnos:** en voz, uno por frase, uniendo las transcripciones de cada tramo; en chat, uno por mensaje de la **API de mensajes**, que da el texto completo, también el de los no entregados. El hablante sale de las marcas de Genesys (`userIds` o `createdBy`) y, si no las hay, del tramo.
- **Carga idempotente:** los identificadores `1CO`, `1CU`, `1AG` y `1QU` son v5 derivados del identificador de Genesys (`genesys:<id>`), con un `upsert` y una transacción por conversación. Un análisis `completo` no se pisa con uno pendiente.
- **Punto de extensión del LLM:** la etapa `analizar` está detrás de `Analyzer`. Hoy, `PendingAnalyzer`; mañana, un analizador con LLM, sin cambiar el esquema ni la lectura. Es el mismo patrón que `PromptRunner` ([ADR-006](adr-006-ejecucion-de-prompts-simulada.md)).
- **Ejecución:** los flujos de descarga, sus ejecuciones y sus logs viven en PostgreSQL.
  - Las ejecuciones corren en un pool de 2 hilos, como mucho una activa por flujo (índice único y `409`).
  - Un programador por tics de 30 s lanza las ejecuciones debidas.
  - Al arrancar, las ejecuciones interrumpidas pasan a `error` y la próxima ejecución se recalcula, así que las perdidas no se recuperan.
- **Pruebas sin red:**
  - Un Genesys falso (`httpx.MockTransport`) sirve **fixtures capturadas de la cuenta real** y saneadas: sin organización, sin URL firmadas ni tokens.
  - Los tests con base de datos (`pg`) usan `TEST_DATABASE_URL`, y el gate los exige (`REQUIRE_PG=1`).
  - El contrato de la API se prueba con un doble del servicio de ingesta y con un test de integración contra el servicio real que valida los mismos esquemas.

## Alternativas

- **SQLite:** descartada por la persona usuaria en la entrevista, que pidió PostgreSQL.
- **Ingesta como módulo de la API:** no sería el «nuevo backend» que se pidió, y la API conocería las credenciales de Genesys.
- **Front contra el servicio de ingesta:** habría que duplicar sesión y permisos y abrir CORS.
- **Proyecto Python separado:** obligaría a duplicar `ids.py` o a publicarlo como librería.
- **ORM y Alembic:** pocas tablas y SQL explícito; no compensan la dependencia.
- **Celery o APScheduler:** un solo proceso y pocas tareas; un pool de hilos y un tic bastan.
- **Turnos de chat desde la transcripción:** pierden el texto de los mensajes no entregados (llegan como frases vacías). Se mantiene solo como respaldo si falla la API de mensajes.

## Consecuencias

- El gate necesita Docker: sin el daemon, `ci.sh` falla con un mensaje claro.
- Hay un tercer proceso que arrancar: [runbook de la ingesta de Genesys](../operaciones/runbook-ingesta-de-genesys.md).
- Los datos reales persisten entre reinicios; la configuración, los usuarios y los flujos de insights siguen en memoria.
- Las transcripciones, los teléfonos (ANI y DNIS) y el `externalTag` se guardan en claro, por decisión de la persona usuaria para esta cuenta de laboratorio. Las fixtures de los tests los llevan. Para producción habría que revisar esta decisión, la retención y el cifrado.
- La plataforma aún no usa las conversaciones reales. Cambiar entre datos sintéticos y reales es [FE012](../../features/FE012-switch-entre-datos-sinteticos-reales/spec.md), que leerá con la misma estructura.

## Ampliaciones

- **FE013 (2026-10-12) · «Sobrescribir»:** los flujos de descarga tienen la casilla `overwrite` (migración `0003`, `false` por defecto; la ejecución copia el valor al crearse). Sin marcar, antes de descargar una conversación se comprueba si ya está en la base; si está, no se llama a Genesys ni se toca nada (contador `skipped_existing`). Marcada, se sustituye entera y su análisis vuelve a `pendiente`, también si estaba `completo`, borrando summary, main topic y su trazabilidad. **Cambio de comportamiento:** volver a descargar ya no actualiza las conversaciones existentes salvo con «Sobrescribir».
- **FE013 · escritura del LLM:** el servicio de ingesta sigue siendo el único escritor. `POST /analysis/fields` escribe summary y main topic generados por un flujo (solo campos vacíos salvo `overwrite`), con la trazabilidad en `analysis.llm_meta` (migración `0004`) y sin cambiar el `status`. La API lee summary y main topic aunque el resto del análisis siga pendiente. Ver [ADR-009](adr-009-servicio-llm-con-proveedores-intercambiables.md).

## Fuentes

- [Spec FE011](../../features/FE011-ingesta-de-conversaciones-genesys/spec.md)
- [Plan y evidencia de FE011](../../features/FE011-ingesta-de-conversaciones-genesys/plan.md)
- [Verificación de FE011](../../features/FE011-ingesta-de-conversaciones-genesys/VERIFY.md)
- [Servicio de ingesta](../../backend/ingestion/main.py)
- [Migraciones](../../backend/ingestion/migrations/0001_initial.sql)
- [Datos de Genesys para STA](../producto/datos-de-genesys-para-sta.md)

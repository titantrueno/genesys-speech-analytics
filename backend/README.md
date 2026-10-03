# Backend · API de Speech & Text Analytics

API FastAPI que sirve datos **mock** de conversaciones bancarias transcritas, métricas y autenticación por roles.

## Arranque

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

- Documentación interactiva: http://localhost:8000/docs (OpenAPI 3.1 completo; exportado en `openapi.yaml`). Desde la web, en Configuración → «API» (`config:view`), con búsqueda y «Try it out» con la sesión (FE010).
- Salud: `GET /api/health`

## Tests

```bash
.venv/bin/pytest
```

## Variables de entorno

| Variable | Por defecto | Uso |
|---|---|---|
| `DATA_SEED` | `42` | Semilla del generador de datos mock. |
| `DATA_REFERENCE_DATE` | hoy | Fecha de referencia (`YYYY-MM-DD`); los datos cubren los 90 días anteriores. |
| `AUTH_SECRET` | valor solo para desarrollo | Secreto HMAC de los tokens. **Obligatorio fijarlo fuera de local.** |
| `AUTH_TOKEN_TTL_SECONDS` | `28800` (8 h) | Caducidad del token. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Orígenes permitidos (separados por comas). |

## Usuarios demo

Contraseña de todos: `demo` (mock, solo para demo; ver ADR-003 en el vault).

| Email | Rol | Ve |
|---|---|---|
| `admin@bancohorizonte.demo` | admin | Todo |
| `supervisor@bancohorizonte.demo` | supervisor | Todo salvo editar configuración y administrar usuarios |
| `analista@bancohorizonte.demo` | analista | Dashboards, conversaciones, explorador, búsqueda y flujos |
| `viewer@bancohorizonte.demo` | viewer | Dashboards y conversaciones |

Es el estado inicial: desde Usuarios y roles (FE006) se crean usuarios, que comparten la misma contraseña demo, y roles personalizados, y se cambian los permisos de cualquier rol.

## Endpoints

Resumen. El contrato completo (parámetros, cuerpos, respuestas, formatos de error y qué módulo del front usa cada ruta) está en `vault/arquitectura/contrato-api-front-back.md`. La especificación formal es [`openapi.yaml`](openapi.yaml) (OpenAPI 3.1: respuestas, errores y seguridad de cada operación), que también sirven `/openapi.json` y `/docs`. Al cambiar una ruta, documéntala en `app/openapi/spec.py` y regenera con `python ../scripts/export_openapi.py`; `tests/test_openapi.py` valida las respuestas reales contra ella.

| Método y ruta | Permiso | Descripción |
|---|---|---|
| `POST /api/auth/login` | público | Devuelve token Bearer y usuario. |
| `GET /api/auth/me` | autenticado | Usuario actual, nombre de su rol (`role_name`) y permisos. |
| `GET /api/metrics/summary` | `dashboards:view` | 13 KPIs con periodo anterior, variación, objetivo y estado (`verde`/`ambar`/`rojo`); cumplimiento por check activo. Con `dashboard`, solo los KPIs que se muestran en él. |
| `GET /api/metrics/timeseries?kpi=&granularity=day\|week` | `dashboards:view` | Serie temporal de un KPI. |
| `GET /api/metrics/breakdown?dimension=main_topic\|channel\|queue\|agent` | `dashboards:view` | KPIs por grupo. |
| `GET /api/conversations` | `conversations:view` | Listado filtrado, paginado (25) y ordenado. |
| `GET /api/conversations/{id}` | `conversations:view` | Conversación completa con análisis. |
| `GET /api/catalog` | `dashboards:view` o `conversations:view` | Valores de los filtros (main topics con `active`, checks activos) y fecha de referencia. |
| `GET /api/query/schema` | `explorer:use` o `flows:view` | Campos del explorador con tipo, operadores y valores. |
| `POST /api/query/run` | `explorer:use` | Ejecuta una consulta: total, 13 KPIs y página del listado (`page`, `page_size`, `sort`, `order`). |
| `GET /api/query/suggest?field=` | `explorer:use` o `flows:view` | Valores de un campo categórico en el intervalo, con recuento. |
| `POST /api/query/interpret` | `explorer:use` | Frase en español → consulta editable y palabras no entendidas. |
| `GET/POST /api/query/saved`, `GET/PATCH/DELETE /api/query/saved/{id}` | `explorer:use` | Consultas guardadas privadas del usuario (`1QY-…`). |
| `GET /api/search/semantic?q=` | `search:use` | Búsqueda semántica por fragmentos: resultados por puntuación (0–1) con turnos, términos resaltables, metadatos, expansión y `max_score`. Admite `from`, `to`, `channel`, `queue`, `min_score`, `group=conversation\|fragment` y `limit` (1–100, 20 por defecto). |
| `GET /api/search/similar/{id}` | `search:use` | Las 10 conversaciones más cercanas a una dada, excluida ella misma. |
| `GET /api/flows`, `GET /api/flows/{id}` | `flows:view` | Flujos de insights (`1FL-…`): listado con autor, fechas, última ejecución y estado (`valido`/`con_errores`), y detalle con el grafo JSON. |
| `POST /api/flows`, `PATCH/DELETE /api/flows/{id}`, `POST /api/flows/{id}/duplicate` | `flows:edit` | Crear, renombrar, borrar (con su historial) y duplicar («Copia de …», nodos nuevos). |
| `PUT /api/flows/{id}/graph` | `flows:edit` | Guarda el grafo si es íntegro (`422` con la lista de errores si no); asigna `1ND` a las claves `tmp-…` y devuelve el `id_map`. |
| `GET /api/flows/catalog` | `flows:view` | Métodos, modelos mock y modelo por defecto, variables, formatos, tipos de output y límites. |
| `POST /api/flows/validate` | `flows:view` | Errores de completitud de un grafo sin guardar (código, mensaje y nodo). |
| `POST /api/flows/sampling/estimate` | `flows:view` | Conversaciones que cumplen una consulta de FE002 y tamaño efectivo de la muestra. |
| `POST /api/flows/{id}/runs` | `flows:edit` | Ejecuta en segundo plano la versión guardada (`202`); `422` si no es válida, `409` si ya hay una en curso. |
| `GET /api/flows/{id}/runs`, `GET /api/flows/{id}/runs/{run_id}` | `flows:view` | Historial y detalle de una ejecución (`1RN-…`): estado y procesados por nodo, outputs y grafo ejecutado. |
| `GET /api/config/public` | público | Nombre de la plataforma, zona horaria e idioma (login y todos los roles). |
| `GET /api/config` | `config:view` | Configuración completa (General, Privacidad, Modelos de IA, KPIs), versión y opciones. |
| `PUT /api/config/general`, `/privacy`, `/ai`, `/kpis/{code}` | `config:edit` | Guarda una sección; `422` con un error por campo (`loc`, `msg`). |
| `GET /api/config/connectors`, `POST /api/config/connectors/{id}/sync` | `config:view` / `config:edit` | Conectores mock (`1CN-…`) y sincronización simulada. |
| `GET /api/config/taxonomy`, `POST/PUT/DELETE /api/config/taxonomy/{main-topics,secondary-topics}[/{id}]` | `config:view` / `config:edit` | Taxonomía (`1TP-…`, `1TS-…`); el código no cambia y uno en uso no se borra (`409`). |
| `GET/POST /api/config/compliance-checks`, `PUT/DELETE /api/config/compliance-checks/{id}` | `config:view` / `config:edit` | Checks de cumplimiento (`1CK-…`); los de FE001 no se borran (`409`). |
| `GET /api/config/audit?section=` | `config:view` | Registro de cambios de la configuración (`1AU-…`), el más reciente primero. |
| `GET /api/users?q=&role=&active=`, `POST /api/users`, `PUT /api/users/{id}` | `users:admin` | Usuarios (`1US-…`) con rol, estado y último acceso; búsqueda por nombre o email sin tildes. Email duplicado: `409` en el campo `email`. Desactivar invalida su sesión. |
| `GET/POST /api/roles`, `PUT/DELETE /api/roles/{id}` | `users:admin` | Roles (`1RO-…`) con nº de usuarios y catálogo de permisos con etiqueta. Los base no se borran ni se renombran; uno en uso no se borra (`409`). |
| `GET /api/users/audit` | `users:admin` | Registro de cambios de usuarios y roles, el más reciente primero. |

**Filtros comunes:** `from`, `to` (por defecto, los últimos 30 días), `channel`, `queue` (IDs `1QU-…`), `agent` (IDs `1AG-…`), `main_topic` (códigos). El listado admite además `resolution`, `churn_risk`, `sentiment_lt`, `compliant` y `repeat_contact`, que usa el drill-down desde los KPIs.

**Búsqueda semántica:** el índice se construye al arrancar la API (unos 2,5 s). El motor es sustituible detrás de `SearchEngine`; sus límites y la migración a embeddings están en `vault/decisiones/adr-005-busqueda-vectorial-ligera.md`.

**Flujos de insights:** el prompt es simulado y determinista detrás de `PromptRunner` (`vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md`). `FLOW_RUN_STEP_DELAY_MS` (15 por defecto) marca el ritmo de la ejecución para que el progreso sea visible.

**Configuración y privacidad:** la configuración es global, en memoria y leída en cada petición; los datos personales se enmascaran por defecto, y el índice de búsqueda y los prompts usan siempre el texto enmascarado (`vault/decisiones/adr-007-configuracion-global-y-enmascarado.md`). Los días de los filtros se calculan en la zona horaria configurada.

**Usuarios y roles:** toda escritura pasa por `UserStore.apply`, que rechaza con `409` lo que dejaría la plataforma sin administración: quitarse a uno mismo `users:admin`, dejar sin ningún `admin` activo o quitar `users:admin` al rol `admin`. Cada respuesta a una petición con sesión lleva `X-Auth-Version` (expuesta por CORS); el front recarga `/api/auth/me` cuando cambia (`vault/decisiones/adr-003-auth-mock-por-roles.md`).

**Identificadores:** formato `PREFIJO-UUID` generado solo con `app/ids.py` (ver el registro en `vault/ingenieria/registro-de-identificadores.md`).

## Estructura

```text
app/
  main.py            # app FastAPI, CORS, routers
  auth.py            # usuarios y roles en memoria, protecciones, token HMAC, require_permission
  audit.py           # registro de auditoría compartido (configuración y usuarios)
  ids.py             # identificadores PREFIJO-UUID
  models.py          # modelos Pydantic
  data/              # catálogo bancario, guiones, generador y store
  services/          # filtros y cálculo de KPIs
  query/             # modelo, campos, motor, intérprete y consultas guardadas del explorador
  search/            # búsqueda semántica: interfaz SearchEngine, TF-IDF, diccionario de sinónimos (ADR-005)
  flows/             # flujos de insights: modelo JSON, reglas, sampling, prompt simulado, outputs y ejecuciones (ADR-006)
  config/            # configuración global: store, taxonomía, checks y cumplimiento efectivo, KPIs (ADR-007)
  privacy/           # enmascarado de datos personales
  routers/           # auth, metrics, conversations, query, search, flows, config, users
  openapi/           # OpenAPI completo: modelos de respuesta (documentales) y descripción de cada operación
tests/
```

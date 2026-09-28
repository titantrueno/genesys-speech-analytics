# Backend · API de Speech & Text Analytics

API FastAPI que sirve datos **mock** de conversaciones bancarias transcritas, métricas y autenticación por roles.

## Arranque

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

- Documentación interactiva: http://localhost:8000/docs
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

## Endpoints

| Método y ruta | Permiso | Descripción |
|---|---|---|
| `POST /api/auth/login` | público | Devuelve token Bearer y usuario. |
| `GET /api/auth/me` | autenticado | Usuario actual y permisos. |
| `GET /api/metrics/summary` | `dashboards:view` | 13 KPIs con periodo anterior y variación; cumplimiento por check. |
| `GET /api/metrics/timeseries?kpi=&granularity=day\|week` | `dashboards:view` | Serie temporal de un KPI. |
| `GET /api/metrics/breakdown?dimension=main_topic\|channel\|queue\|agent` | `dashboards:view` | KPIs por grupo. |
| `GET /api/conversations` | `conversations:view` | Listado filtrado, paginado (25) y ordenado. |
| `GET /api/conversations/{id}` | `conversations:view` | Conversación completa con análisis. |
| `GET /api/catalog` | `dashboards:view` o `conversations:view` | Valores de los filtros y fecha de referencia. |
| `GET /api/query/schema` | `explorer:use` | Campos del explorador con tipo, operadores y valores. |
| `POST /api/query/run` | `explorer:use` | Ejecuta una consulta: total, 13 KPIs y página del listado (`page`, `page_size`, `sort`, `order`). |
| `GET /api/query/suggest?field=` | `explorer:use` | Valores de un campo categórico en el intervalo, con recuento. |
| `POST /api/query/interpret` | `explorer:use` | Frase en español → consulta editable y palabras no entendidas. |
| `GET/POST /api/query/saved`, `GET/PATCH/DELETE /api/query/saved/{id}` | `explorer:use` | Consultas guardadas privadas del usuario (`1QY-…`). |

**Filtros comunes:** `from`, `to` (por defecto, los últimos 30 días), `channel`, `queue` (IDs `1QU-…`), `agent` (IDs `1AG-…`), `main_topic` (códigos). El listado admite además `resolution`, `churn_risk`, `sentiment_lt`, `compliant` y `repeat_contact`, que usa el drill-down desde los KPIs.

**Identificadores:** formato `PREFIJO-UUID` generado solo con `app/ids.py` (ver el registro en `vault/ingenieria/registro-de-identificadores.md`).

## Estructura

```text
app/
  main.py            # app FastAPI, CORS, routers
  auth.py            # usuarios demo, token HMAC, require_permission
  ids.py             # identificadores PREFIJO-UUID
  models.py          # modelos Pydantic
  data/              # catálogo bancario, guiones, generador y store
  services/          # filtros y cálculo de KPIs
  query/             # modelo, campos, motor, intérprete y consultas guardadas del explorador
  routers/           # auth, metrics, conversations, query
tests/
```

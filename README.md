# Speech & Text Analytics · Banco Horizonte

Plataforma web de analítica de conversaciones para la atención al cliente de un banco. Trabaja solo sobre **transcripciones de llamadas y chats** (nunca audio): dashboards de KPIs con drill-down al listado de conversaciones y un detalle de cada conversación como chat, con su análisis.

> Por defecto la plataforma muestra datos **sintéticos**: se generan de forma determinista al arrancar el backend (1.000 conversaciones de los últimos 90 días). Un servicio de ingesta aparte (FE011) descarga conversaciones **reales** de Genesys Cloud a PostgreSQL y, desde FE012, **Configuración → Fuentes de datos** cambia toda la plataforma entre los dos orígenes. Con datos reales el análisis de la plataforma (summary, main topic, CSAT…) empieza pendiente; un flujo de insights lo genera con un LLM (Gemini por defecto, u OpenAI o Anthropic) y lo guarda en las conversaciones: summary y main topic desde FE013 y el resto del análisis desde FE014. Cada dato se muestra y cuenta en los KPIs en cuanto existe. La API lee PostgreSQL con `DATABASE_URL` (solo lectura) y el origen vuelve a sintético al reiniciarla.

## Estructura

| Carpeta | Contenido |
|---|---|
| [`backend/`](backend/README.md) | API FastAPI (Python) con datos mock, auth por roles y métricas. |
| [`frontend/`](frontend/README.md) | SPA Vite + React + TypeScript + Tailwind. |
| [`features/`](features/README.md) | Documentación de cada feature (`FEXXX-descripcion-breve/`: spec, plan…). |
| [`vault/`](vault/Home.md) | Conocimiento del proyecto: producto, arquitectura, decisiones, convenciones. |
| `.claude/skills/` | Skills del ciclo `spec → plan → build → test → review → ship` y `vault`. |
| `scripts/audit_vault.py` | Auditoría del vault. |

## Entorno local con un solo comando

```bash
./scripts/dev.sh             # PostgreSQL (Docker/Colima) + ingesta + LLM (si hay LLM_TOKEN) + API + web
./scripts/dev.sh --no-db     # solo API + web, sin Docker
./scripts/dev.sh --reload    # uvicorn con --reload
API_PORT=18000 INGESTION_PORT=18001 LLM_PORT=18002 WEB_PORT=15173 ./scripts/dev.sh   # puertos propios
```

Para probar la interfaz en inglés (Configuración → General → «Idioma de la interfaz») con `--no-db`, arranca con la variable `INGESTION_TOKEN` vacía: con el valor del `.env` y sin servicio de ingesta, guardar la configuración responde `503`.

Por defecto: web en `:5173`, API en `:8000`, ingesta en `:8001`, LLM en `:8002`. El script comprueba antes que los puertos (y el 5432) estén libres y, si no, aborta sin lanzar nada; arranca Colima si el daemon no responde; crea el venv y hace `npm install` si faltan; espera a que cada servicio responda y escribe sus logs en `.dev-logs/` (ignorado por git).

**Ctrl+C lo para todo**: cada servicio va en su propio grupo de procesos (se mata con sus hijos), se hace `docker compose stop` + `rm` del contenedor de PostgreSQL (el volumen `pgdata` se conserva) y se ejecuta `colima stop` solo si lo arrancó el propio script. Si un servicio muere, el script para el resto. Al terminar avisa si algún puerto sigue ocupado. Los tests con PostgreSQL de `ci.sh` dejan el contenedor levantado; `dev.sh` lo para al salir.

## Arranque rápido (manual)

Requisitos: Python 3.11+ y Node 20+.

```bash
# Terminal 1 — API en http://localhost:8000 (docs en /docs)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# Terminal 2 — web en http://localhost:5173
cd frontend
npm install
npm run dev
```

Entra con cualquiera de los usuarios demo que aparecen en la pantalla de login (contraseña `demo`). Ver [backend/README.md](backend/README.md#usuarios-demo).

### Servicio de ingesta de Genesys (FE011)

Descarga conversaciones reales de Genesys Cloud a PostgreSQL. Es un proceso aparte de la API y el único que lee las credenciales de Genesys. Requisitos: Docker (en esta máquina, el daemon es [Colima](https://github.com/abiosoft/colima): `colima start`) y un `.env` en la raíz con las claves de [`.env.example`](.env.example).

```bash
# PostgreSQL (desde la raíz)
docker compose up -d --wait

# Terminal 3 — servicio de ingesta en http://localhost:8001 (docs en /docs; el resto exige el token interno)
cd backend
.venv/bin/uvicorn ingestion.main:app --port 8001
```

El esquema se crea o actualiza al arrancar el servicio. Las descargas se crean en «Flujos de insights» (tipo «Descarga de transcripciones») y el estado del conector está en Configuración → Fuentes de datos. Ver [backend/README.md](backend/README.md#servicio-de-ingesta) y el [runbook](vault/operaciones/runbook-ingesta-de-genesys.md).

### Servicio de LLM (FE013)

Conecta los flujos de insights con un LLM para generar el análisis de las conversaciones reales. Es otro proceso aparte y el único que lee las claves de los proveedores. En el `.env`: `LLM_TOKEN` y la clave de cada proveedor que uses (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

```bash
# Terminal 4 — servicio de LLM en http://localhost:8002 (/health sin token)
cd backend
.venv/bin/uvicorn llm.main:app --port 8002
```

El proveedor por defecto se elige en Configuración → Modelos de IA, que muestra qué proveedores tienen clave y permite «Probar». La plantilla «Generar summary y main topic» de «Nuevo flujo» obtiene los dos campos con una llamada por conversación, y «Generar análisis completo» (FE014), todo el análisis: resolución, CSAT, esfuerzo, riesgo, sentimiento si Genesys no lo da, cada check activo, temas secundarios, palabras clave y entidades. Ver el [runbook](vault/operaciones/runbook-servicio-llm.md).

## Verificación

`./scripts/ci.sh` ejecuta todos los gates (vault, tests del backend con dos datasets mock distintos, tests con PostgreSQL, que necesitan Docker, tests del front, lint, build y auditoría de dependencias) y termina con código distinto de 0 si alguno falla. La misma pipeline está en `.github/workflows/ci.yml`. Por separado:

```bash
cd backend && .venv/bin/pytest          # tests de la API
cd frontend && npm test && npm run lint && npm run build
python3 scripts/audit_vault.py          # desde la raíz
```

## Estado

| Feature | Estado |
|---|---|
| FE001 Base, dashboards y detalle de conversaciones | Entregada en `v0.1.0` |
| FE007 Fila completa abre el detalle | Entregada en `v0.1.0` |
| FE008 Identificadores con prefijo y UUID | Entregada en `v0.1.0` |
| FE002 Explorador de queries asistidas | Entregada en `v0.2.0` |
| FE003 Búsqueda semántica de conversaciones | Entregada en `v0.3.0` |
| FE004 Diseñador de flujos de insights | Entregada en `v0.4.0` |
| FE005 Configuración de la plataforma | Entregada en `v0.5.0` |
| FE006 Usuarios y roles | Entregada en `v0.6.0` |
| FE009 Tests independientes del dataset mock | Entregada en `v0.5.1` |
| FE010 Especificación OpenAPI en Configuración | Entregada en `v0.7.0` |
| FE011 Ingesta de conversaciones de Genesys | Entregada en `v0.8.0` |
| FE012 Switch entre datos sintéticos y reales | Entregada en `v0.9.0` |
| FE013 Servicio de LLM para summary y main topic | Entregada en `v0.10.0` |
| FE014 Análisis completo con LLM | Entregada en `v0.11.0` |
| FE015 Persistencia de flujos y preferencias | Entregada en `v0.12.0` (sin review propio, ver [SHIP de FE016](features/FE016-idioma-ingles-de-la-interfaz/SHIP.md)) |
| FE016 Idioma inglés de la interfaz | Entregada en `v0.12.0` |

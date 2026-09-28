# Speech & Text Analytics · Banco Horizonte

Plataforma web de analítica de conversaciones para la atención al cliente de un banco. Trabaja solo sobre **transcripciones de llamadas y chats** (nunca audio): dashboards de KPIs con drill-down al listado de conversaciones y un detalle de cada conversación como chat, con su análisis.

> Todos los datos son **mock**: se generan de forma determinista al arrancar el backend (1.000 conversaciones de los últimos 90 días). No hay integración real con Genesys ni persistencia.

## Estructura

| Carpeta | Contenido |
|---|---|
| [`backend/`](backend/README.md) | API FastAPI (Python) con datos mock, auth por roles y métricas. |
| [`frontend/`](frontend/README.md) | SPA Vite + React + TypeScript + Tailwind. |
| [`features/`](features/README.md) | Documentación de cada feature (`FEXXX-descripcion-breve/`: spec, plan…). |
| [`vault/`](vault/Home.md) | Conocimiento del proyecto: producto, arquitectura, decisiones, convenciones. |
| `.devin/skills/` | Skills del ciclo `spec → plan → build → test → review → ship` y `vault`. |
| `scripts/audit_vault.py` | Auditoría del vault. |

## Arranque rápido

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

## Verificación

`./scripts/ci.sh` ejecuta todos los gates (vault, tests, lint, build y auditoría de dependencias) y termina con código distinto de 0 si alguno falla. La misma pipeline está en `.github/workflows/ci.yml`. Por separado:

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
| FE003–FE006 Búsqueda semántica, flujos, configuración, usuarios y roles | Especificadas (aparecen como «Próximamente») |

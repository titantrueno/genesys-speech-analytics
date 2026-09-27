---
title: "Estado operativo inicial"
type: runbook
status: active
owners: [equipo-del-proyecto]
tags: [operaciones, runbook, local]
created: 2026-09-27
updated: 2026-09-27
---

# Estado operativo inicial

## Cuándo usarlo

Para arrancar, comprobar o revertir la plataforma en su estado actual: **demo local con datos mock**. No existe entorno de producción, infraestructura desplegada ni telemetría.

## Prerrequisitos

- Python 3.11+ y Node 20+.
- Entorno del backend creado (`python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`) y dependencias del front instaladas (`cd frontend && npm install`).

## Procedimiento

1. API: `cd backend && .venv/bin/uvicorn app.main:app --port 8000`. Para una demo fuera de local, define `AUTH_SECRET` (ver [ADR-003](../decisiones/adr-003-auth-mock-por-roles.md)).
2. Web: `cd frontend && npm run dev` (desarrollo), o `npm run build && npx vite preview` (build de producción, que reenvía `/api` a la API).
3. Gate antes de entregar un cambio: `./scripts/ci.sh` debe terminar con código 0.

## Verificación

- **Salud de la API:** `curl -s localhost:8000/api/health` devuelve `{"status":"ok"}`.
- **Humo funcional:** login con un usuario demo, abrir un dashboard y hacer drill-down al listado.
- **Datos:** con `DATA_SEED` y `DATA_REFERENCE_DATE` fijos, el dataset es reproducible.

## Rollback

- Cada entrega tiene una etiqueta de Git (por ejemplo `v0.1.0`). Para volver a la anterior: `git checkout <etiqueta>`, o revertir los commits con `git revert <desde>..<hasta>`.
- No hay datos persistentes que migrar; reiniciar la API regenera el dataset.

## Escalado

El propietario del proyecto (`equipo-del-proyecto`).

**Pendiente, hipótesis:** cuando exista un despliegue real, este runbook debe incorporar señales de salud, logs estructurados, métricas, alertas y rollout escalonado.

## Fuentes

- [README del proyecto](../../README.md)
- [README del backend](../../backend/README.md)
- [Script de CI local](../../scripts/ci.sh)

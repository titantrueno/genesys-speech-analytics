# FE001 — Ship

> Fase `/ship`. Fecha: 2026-09-27. Entrega: [Plataforma v0.1.0](../../vault/entregas/2026-09-27-plataforma-v0-1-0.md), junto con FE007 y FE008.

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada |
| [plan.md](plan.md) | T1 a T9 hechas, con evidencia |
| [VERIFY.md](VERIFY.md) | Verde; 2 bugs corregidos con regresión |
| [REVIEW.md](REVIEW.md) | Aprobado; sin critical ni major abiertos |

## Resumen del cambio

No hay remoto ni PR: la integración es trunk-based en `main`, con un commit atómico por tarea. Desde la base `03de25a` hasta la etiqueta `v0.1.0`:

- **Backend FastAPI:** dataset mock bancario determinista, auth por roles, métricas de 13 KPIs, series, desgloses, listado con filtros de drill-down, detalle y catálogo.
- **Front Vite + React:** login, navegación por permisos, 3 dashboards, drill-down, listado y detalle como chat con panel de análisis.
- **Correcciones de verificación y revisión:** periodos rápidos con la fecha de referencia, estados de error en los widgets y 401 ante tokens no ASCII.

## Pipeline con gates

| Gate | Dónde | Resultado |
|---|---|---|
| Auditoría del vault | `scripts/ci.sh`, job `vault` | Código 0 |
| Tests del backend | `scripts/ci.sh`, job `backend` | 108 passed |
| Tests, lint y build del front | `scripts/ci.sh`, job `frontend` | 72 passed, 0 avisos, build OK |
| Seguridad de dependencias | `npm audit --audit-level=high`, `pip-audit` | 0 vulnerabilidades |

- `scripts/ci.sh` termina con código 0 en verde; con un fallo provocado (enlace roto en el vault) termina con código 1 y no continúa.
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) reproduce los mismos gates, pero **no se ha ejecutado**: no hay remoto. Queda pendiente confirmarlo en la primera subida a GitHub.

## Observabilidad

La observabilidad de producción está **fuera de alcance** según la spec, porque no hay despliegue. Señales disponibles:

- `GET /api/health` como señal de salud;
- códigos HTTP explícitos (401, 403, 404 y 422 con detalle);
- avisos visibles en la UI cuando falla la API.

Lo que falta para un despliegue real (logs estructurados, métricas y trazas) está anotado en el [runbook](../../vault/operaciones/estado-operativo.md).

## Rollout y rollback

- **Rollout:** entrega local marcada con la etiqueta `v0.1.0`. No hay usuarios reales ni feature flags; el blast radius es la máquina local.
- **Rollback:** `git checkout 03de25a` (base) o `git revert` del rango de la entrega. No hay datos persistentes que migrar.

## Pendiente tras la entrega

- R9: drill-down de «Cumplimiento por check», que necesita un filtro por check en la API.
- R10: confirmar si la tarjeta «Cumplimiento» debe llevar a las conversaciones que cumplen o a las que fallan.
- R17: versionar la prueba de humo en navegador cuando exista CI.
- R5: endurecer la auth (secreto, límite de intentos, cookie `httpOnly`) antes de cualquier despliegue compartido.

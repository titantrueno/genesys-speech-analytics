# FE004 — Ship

> Fase `/ship`. Fecha: 2026-09-28. Entrega: [Plataforma v0.4.0](../../vault/entregas/2026-09-28-plataforma-v0-4-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada (revisada tras v0.3.0) |
| [plan.md](plan.md) | T1–T9 hechas, con evidencia y mutaciones |
| [VERIFY.md](VERIFY.md) | Verde; un bug y una fragilidad de tests corregidos con regresión |
| [REVIEW.md](REVIEW.md) | Aprobado; sin critical ni major abiertos |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.3.0` a `v0.4.0`:

- **Backend (`app/flows/`, `app/routers/flows.py`):**
  - formato JSON del flujo con integridad y reglas de conexión, y validación de completitud;
  - CRUD, catálogo, estimación y validación;
  - sampling real por método, prompt simulado detrás de `PromptRunner` y outputs;
  - ejecuciones en segundo plano con progreso, errores e historial.
- **Front (`src/flows/`):**
  - listado;
  - editor con React Flow, paleta, reglas y paneles por nodo;
  - validar, guardar y ejecutar;
  - vista de ejecución con polling, pestañas de resultados e historial.
- **FE002:** `schema` y `suggest` aceptan también `flows:view`.
- **Dashboards:** `RankedBars` pasa a `dashboards/bars.tsx`, sin Recharts.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault (40 archivos, 0 errores);
- 508 tests de backend;
- 230 tests de front, lint y build;
- `npm audit` y `pip-audit` sin vulnerabilidades.

Dependencia nueva: `@xyflow/react` 12.12.0 (MIT) en el front. `requirements.txt` no cambia. `.github/workflows/ci.yml` sigue preparado y sin ejecutar, porque no hay remoto.

## Observabilidad

- Cada ejecución expone su estado, el de cada nodo (procesados, total y mensaje de error), la duración y el usuario en `GET /api/flows/{id}/runs/{run_id}`, y el historial en `GET /api/flows/{id}/runs`.
- Códigos HTTP explícitos: `422` (grafo o flujo no válido, con la lista de errores), `409` (ejecución en curso), `404` y `403`.
- La UI muestra el estado de cada nodo, los avisos de error y los errores de validación sobre el lienzo.
- **Pendiente con despliegue real:** logs estructurados por ejecución, métricas de duración y de ejecuciones con error, y trazas por nodo; con un LLM real, además coste y latencia por llamada.

## Rollout y rollback

- **Rollout:** etiqueta local `v0.4.0`. FE001, FE002, FE003, FE007 y FE008 siguen verificadas en la misma suite (el cambio de permisos de `schema`/`suggest` y el de `RankedBars` los cubren sus tests).
- **Rollback:** `git checkout v0.3.0`. No hay datos persistentes; flujos y ejecuciones viven en memoria.

## Pendiente tras la entrega

- R5: rol de solo lectura de flujos cuando FE006 permita crear roles.
- R7: enmascarar datos personales antes de enviar transcripciones a un LLM real (FE005 y ADR-006).
- Migrar a un `PromptRunner` real con reintentos, límites de tasa, cancelación y ejecución fuera del proceso de la API.

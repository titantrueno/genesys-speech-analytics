# FE009 — Ship

> Fase `/ship`. Fecha: 2026-10-02. Entrega: [Plataforma v0.5.1](../../vault/entregas/2026-10-02-plataforma-v0-5-1.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada |
| [plan.md](plan.md) | T1–T4 hechas, con matriz y mutaciones |
| [VERIFY.md](VERIFY.md) | Verde |
| [REVIEW.md](REVIEW.md) | Aprobado; sin critical ni major |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.5.0` a `v0.5.1`, sin cambios de la aplicación:

- `tests/dates.py`, fechas relativas en los tests de FE001–FE003 y esperados sobre el mismo dataset que la API;
- calibración de relevancia de FE003 con un dataset explícito (semilla 42, 2026-09-27);
- segunda pasada del backend en `scripts/ci.sh` y en `.github/workflows/ci.yml` (semilla 7, referencia 2026-11-10);
- aparte: límite de 15 s por test en Vitest.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0: vault, backend 666 + 666, front 267, lint, build y auditorías. Falla si un test vuelve a depender del dataset por defecto.

## Observabilidad

No aplica: no hay cambios en ejecución. La señal es el propio gate (segunda pasada).

## Rollout y rollback

- **Rollout:** etiqueta local `v0.5.1`.
- **Rollback:** `git checkout v0.5.0` (solo cambian tests, el gate y la documentación).

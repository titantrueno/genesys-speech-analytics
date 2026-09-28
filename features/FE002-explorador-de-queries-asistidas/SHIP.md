# FE002 — Ship

> Fase `/ship`. Fecha: 2026-09-28. Entrega: [Plataforma v0.2.0](../../vault/entregas/2026-09-28-plataforma-v0-2-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada (revisada tras v0.1.0) |
| [plan.md](plan.md) | T1–T9 hechas (T7 en a/b), con evidencia |
| [VERIFY.md](VERIFY.md) | Verde; 5 bugs corregidos con regresión |
| [REVIEW.md](REVIEW.md) | Aprobado; sin critical ni major abiertos |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.1.0` a `v0.2.0`:

- **Backend:** modelo y validación de consultas, motor y `POST /api/query/run`, sugerencias, consultas guardadas (`1QY`) e intérprete de lenguaje natural por reglas.
- **Front:** sección Explorador con constructor visual, frase en lenguaje natural, resultados en tiempo real con la tabla compartida y consultas guardadas.
- **Correcciones de verificación y revisión:** salidas del intérprete, errores sin fila y límites de tamaño.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault;
- 230 tests de backend;
- 109 tests de front, lint y build;
- `npm audit` y `pip-audit` sin vulnerabilidades.

`.github/workflows/ci.yml` sigue preparado y sin ejecutar, porque no hay remoto.

## Observabilidad

Sin cambios respecto a v0.1.0: `GET /api/health`, códigos HTTP explícitos (el `422` de consultas con la ruta de cada error) y avisos en la UI. No hay despliegue.

## Rollout y rollback

- **Rollout:** etiqueta local `v0.2.0`. No afecta a FE001, que sigue verificado en la misma suite.
- **Rollback:** `git checkout v0.1.0`. Las consultas guardadas están en memoria y se pierden al reiniciar en cualquier caso.

## Pendiente tras la entrega

- R6: persistencia y concurrencia de las consultas guardadas, cuando se decida un almacenamiento real.
- Ampliar el intérprete según las frases reales de los usuarios (las no entendidas se pueden recoger como señal).

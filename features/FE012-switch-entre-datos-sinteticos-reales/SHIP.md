# FE012 — Ship

> Fase `/ship`. Fecha: 2026-10-12. Entrega: [Plataforma v0.9.0](../../vault/entregas/2026-10-12-plataforma-v0-9-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Entregada; aprobada al pedir su implementación |
| [plan.md](plan.md) | T1–T9 hechas, cada una con rojo a verde y su commit |
| [VERIFY.md](VERIFY.md) | Verde: 15 criterios con evidencia; un bug real corregido (periodo por defecto) y 31 de 31 mutaciones detectadas |
| [REVIEW.md](REVIEW.md) | Aprobada, sin critical ni major abiertos: R1 (`500` en «similares» de una conversación aún no indexada) resuelto |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.8.0` a `v0.9.0`.

- **Backend:** repositorio de conversaciones con dos orígenes, `RealRepository` (PostgreSQL de solo lectura con testigo de versión), origen en la configuración global (`PUT /api/config/sources`), KPIs, filtros y motor del explorador tolerantes al análisis pendiente, campos de Genesys y «está vacío», índice de búsqueda por origen con reconstrucción en caliente, enmascarado de turnos y frases de temas, avisos de validación y periodo por defecto que incluye hoy. El OpenAPI pasa a `0.9.0` con 70 operaciones.
- **Front:** selector de origen con confirmación, aviso único de datos no disponibles, panel «Analítica de Genesys», chat con transferencia y mensajes no entregados, listado con columnas y búsqueda exacta, KPIs «Sin datos · pendiente de análisis» y avisos de validación.
- **Dependencias:** ninguna nueva.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0: vault sin errores; 868 tests de backend con cada dataset; 124 tests con PostgreSQL (`REQUIRE_PG=1`); OpenAPI al día y válido; 383 tests de front, lint y build; `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades. `.github/workflows/ci.yml` ejecuta lo mismo.

## Observabilidad

- **Señales de salud:** el origen activo (`GET /api/config`, `GET /api/catalog`), el estado del conector real y, si falla la base, el `503` «Los datos reales no están disponibles» con su aviso en la UI.
- **Registro:** cada cambio de origen queda en el log de Configuración; las reconstrucciones fallidas del índice, en el logger `app.search.index`.

## Rollout y rollback

- **Rollout:** etiqueta `v0.9.0` en `main`, sin despliegue. El origen por defecto es `sintetico` y vuelve a serlo al reiniciar la API: el comportamiento por defecto es el de `v0.8.0`. El origen `real` solo se activa a mano y exige `DATABASE_URL` en el `.env`.
- **Rollback:** en caliente, «Sintético» en Configuración o reiniciar la API; en código, `git checkout v0.8.0`. No hay migraciones nuevas.

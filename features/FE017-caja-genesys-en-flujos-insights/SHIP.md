# FE017 — Ship

> Fase `/ship`. Fecha: 2026-10-13. Entrega: [Plataforma v0.13.0](../../vault/entregas/2026-10-13-plataforma-v0-13-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Entregada en `v0.13.0`; 21 criterios |
| [plan.md](plan.md) | T1–T8 hechas, una por commit, con los ajustes de `/build` anotados en cada tarea |
| [VERIFY.md](VERIFY.md) | Verde: cobertura por criterio, nueve mutaciones (una detectada gracias a un test añadido y una equivalente), fuentes oficiales y recorrido en Chrome contra Genesys real |
| [REVIEW.md](REVIEW.md) | Aprobada: 15 hallazgos, 4 resueltos y el resto justificados; sin critical ni major |

## Qué se entrega

Integración trunk-based en `main`, de `v0.12.0` a `v0.13.0`, en 11 commits: T1–T8, `/test`, `/review` y este ship.

- **Ingesta:** migración `0008`, descargas que cuelgan de un flujo de insights, su subconjunto y las rutas internas `/insight-downloads`.
- **API:**
  - nodo `descarga` con sus reglas y su validación;
  - Sampling `size: "all"` con el aviso `large_sample`;
  - ejecución end-to-end con estado `omitido`;
  - programador de flujos de insights;
  - rutas `…/runs/{run_id}/download` y `…/download/log`;
  - versión `0.13.0`.
- **Front:**
  - caja en la paleta, el lienzo y su panel (campos compartidos con FE011);
  - «All conversations»;
  - sección «Descarga de Genesys» en la ejecución, columna «Origin» en el historial y «Next run» en el listado.
- **Dependencias:** ninguna nueva.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0 (pasada de `/review`, repetida antes de etiquetar):

- vault sin errores;
- backend: 1.235 tests con cada dataset y 203 con PostgreSQL (`REQUIRE_PG=1`);
- OpenAPI al día y válido;
- front: 597 tests, lint y build;
- `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades «high».

`.github/workflows/ci.yml` ejecuta lo mismo. Ningún test usa red ni claves reales: Genesys, la ingesta y el LLM se sustituyen por dobles.

## Observabilidad

- **Ejecución:** el estado de cada nodo, `download` (estado y contadores de la descarga), `origin` y `notes` en `GET /api/flows/{id}/runs/{run_id}`, y el log de la descarga en `…/download/log` y en la sección «Descarga de Genesys» de la web.
- **Salud:** `/health` del servicio de ingesta; la validación da `ingestion_unavailable` si no responde.
- **Programador:** las ejecuciones con origen «Programada» en el historial, y el log de la API (`app.flows.scheduler`) si falla un tic.

## Rollout y rollback

- **Rollout:** etiqueta `v0.13.0` en `main`, sin despliegue. La migración `0008` se aplica al arrancar el servicio de ingesta. Nada cambia en los flujos existentes hasta que alguien añade una caja o «All conversations».
- **Blast radius:** los flujos que usen la caja; los flujos de descarga de FE011 y los flujos sin caja se comportan igual (sus suites siguen en verde sin cambios de comportamiento).
- **Rollback funcional:**
  - «Active» desmarcado o «Manual only» en la caja;
  - quitar la caja del flujo;
  - `FLOW_SCHEDULER=0` para apagar todo el programador.
- **Rollback de código:** volver a `v0.12.0`. La migración `0008` no estorba. Los flujos con caja dejan de aparecer hasta regresar a `v0.13.0` (ver la [entrega](../../vault/entregas/2026-10-13-plataforma-v0-13-0.md)).

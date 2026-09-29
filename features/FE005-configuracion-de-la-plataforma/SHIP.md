# FE005 — Ship

> Fase `/ship`. Fecha: 2026-09-29. Entrega: [Plataforma v0.5.0](../../vault/entregas/2026-09-29-plataforma-v0-5-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada (revisada tras v0.4.0), con una desviación aceptada documentada |
| [plan.md](plan.md) | T1–T9 hechas, con evidencia y mutaciones; recorrido en navegador validado por el usuario |
| [VERIFY.md](VERIFY.md) | Verde; un bug de privacidad y una afirmación falsa corregidos con regresión |
| [REVIEW.md](REVIEW.md) | Aprobado; sin critical ni major abiertos |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.4.0` a `v0.5.0`:

- **Backend:**
  - **configuración** (`app/config/`, `app/routers/config.py`): instantánea global versionada con auditoría `1AU`; secciones General, Fuentes, Taxonomía, KPIs, Cumplimiento, Privacidad y Modelos de IA; ruta pública (nombre, zona e idioma);
  - **privacidad** (`app/privacy/masking.py`): enmascarado de PII por patrones, activado por defecto; índice de búsqueda y prompts siempre enmascarados;
  - **propagación:** taxonomía y checks leídos en caliente (catálogo, explorador, intérprete, KPIs, drill-down, detalle, informes); estado y objetivo de los KPIs en el resumen; días en la zona configurada (`started_at` con la zona del banco); modelo por defecto en el catálogo de flujos;
  - **identificadores:** `1TP`, `1TS` (nuevo), `1CK`, `1CN` y `1AU` activos.
- **Front:**
  - `/configuracion` (diferida) con siete pestañas, errores por campo, confirmación en la fila, registro de cambios y solo lectura;
  - fechas en la zona de la plataforma desde `lib/format.ts`; nombre en cabecera y login; tarjetas de KPI con estado y objetivo según el dashboard; filtros solo con temas activos; modelo por defecto en Prompts nuevos.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault (42 archivos, 0 errores);
- 666 tests de backend;
- 267 tests de front, lint y build;
- `npm audit` y `pip-audit` sin vulnerabilidades.

Sin dependencias nuevas. `.github/workflows/ci.yml` sigue preparado y sin ejecutar, porque no hay remoto.

## Observabilidad

- Cada cambio de configuración queda en `GET /api/config/audit` (quién, cuándo, sección, elemento, antes y después), visible en cada pestaña; la versión de la configuración (`GET /api/config`) cuenta los cambios aceptados.
- `GET /api/config/public` sirve de sonda sin sesión de la configuración vigente.
- Códigos HTTP explícitos: `422` con un error por campo, `409` (elemento en uso o del análisis), `404` y `403`.
- **Pendiente con despliegue real:** logs estructurados de los cambios de configuración y alertas sobre cambios de privacidad (desactivar el enmascarado).

## Rollout y rollback

- **Rollout:** etiqueta local `v0.5.0`. FE001–FE004, FE007 y FE008 siguen verificadas en la misma suite (la propagación y el cambio de `started_at` los cubren sus tests).
- **Rollback:** `git checkout v0.4.0`. No hay datos persistentes; la configuración vive en memoria y vuelve a su estado inicial al reiniciar la API.

## Pendiente tras la entrega

- [FE009](../FE009-tests-independientes-del-dataset-mock/spec.md): tests de FE001–FE003 independientes del dataset mock (planificada).
- R4: revisar los checks por frases como posible oráculo de datos personales cuando FE006 permita roles editables.
- R13: fragilidad de algunos tests del front con la máquina muy cargada.

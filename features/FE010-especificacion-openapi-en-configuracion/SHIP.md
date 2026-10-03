# FE010 — Ship

> Fase `/ship`. Fecha: 2026-10-03. Entrega: [Plataforma v0.7.0](../../vault/entregas/2026-10-03-plataforma-v0-7-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Aprobada el 2026-10-03 |
| [plan.md](plan.md) | T1–T6 hechas, con evidencia, mutaciones y recorrido en Chrome |
| [VERIFY.md](VERIFY.md) | Verde; un fallo de búsqueda encontrado y corregido con regresión; versión de Swagger UI fijada |
| [REVIEW.md](REVIEW.md) | Aprobado; sin critical ni major abiertos (R1, token solo al origen de la API, resuelto) |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.6.0` a `v0.7.0`. Incluye también el OpenAPI 3.1 completo (`7887f24`, `c05d1af`), que estaba en `main` sin entregar.

- **Front:**
  - **pestaña:** `config/tabs/ApiTab.tsx`, la octava de Configuración (`?tab=api`), cargada con `lazy`, con estados de carga y error y sin registro de cambios (`useAudit(null)`);
  - **módulo `config/openapi/`:** `filterSpec` (todas las palabras en ruta, método, resumen, descripción o dominio), `withServer` (`VITE_API_URL`), `authInterceptor` (token de la sesión, solo hacia el origen de la API) y `useOpenApiSpec`;
  - **Swagger UI** con `persistAuthorization`, `deepLinking` y `tryItOutEnabled` desactivados y sin la sección «Schemas»;
  - **tests:** doble global de `swagger-ui-react` para jsdom (`test/swaggerStub.ts`);
  - **proxy de Vite:** reenvía `/openapi.json`.
- **Backend:** solo `API_VERSION = "0.7.0"` y `openapi.yaml` regenerado. Sin rutas nuevas.
- **Dependencias:** `swagger-ui-react` `5.33.1` exacto y `@types/swagger-ui-react` (desarrollo).

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault sin errores;
- 728 tests de backend con las dos combinaciones de dataset, incluido el contrato del OpenAPI y la comprobación de que el YAML está al día;
- 329 tests de front, lint y build;
- `npm audit` y `pip-audit` sin vulnerabilidades.

`.github/workflows/ci.yml` sigue preparado y sin ejecutar, porque no hay remoto.

## Observabilidad

- `GET /openapi.json` (público) refleja la versión entregada (`0.7.0`, 58 operaciones). Es la misma fuente que lee la pestaña.
- Las escrituras de «Try it out» quedan en la auditoría `1AU` de su sección: quién, cuándo, elemento, antes y después.
- Un fallo de carga se ve en la pestaña («No se ha podido cargar la especificación de la API.») sin afectar a las demás.
- **Pendiente con despliegue real:** distinguir en logs las llamadas hechas desde «Try it out» (hoy son indistinguibles de las de la UI) y medir el uso de la pestaña.

## Rollout y rollback

- **Rollout:** etiqueta local `v0.7.0`. La carga inicial no cambia; Swagger UI solo se descarga al abrir la pestaña. Quien no tiene `config:view` no la ve ni pide la especificación.
- **Rollback:** `git checkout v0.6.0`, o revertir `db87bd3..` para quitar solo FE010 y mantener el OpenAPI completo. No hay datos persistentes.

## Pendiente tras la entrega

- Los candados de Swagger se ven abiertos aunque el token se envía (deuda de VERIFY).
- Un `401` en «Try it out» no cierra la sesión de la app (R8, fuera de alcance).
- Antes de actualizar `swagger-ui-react`, comprobar en Chrome que el filtro sigue repintando (R7, lección 32).

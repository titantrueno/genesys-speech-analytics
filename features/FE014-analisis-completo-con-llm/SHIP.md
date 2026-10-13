# FE014 — Ship

> Fase `/ship`. Fecha: 2026-10-13. Entrega: [Plataforma v0.11.0](../../vault/entregas/2026-10-13-plataforma-v0-11-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Entregada; aprobada el 2026-10-13 sin cambios de criterios |
| [plan.md](plan.md) | T1–T8 hechas, cada una de rojo a verde, con notas por tarea (decisiones, comprobaciones con Gemini y hallazgos). T5 y T8 se cerraron en varios commits. |
| [VERIFY.md](VERIFY.md) | Verde: 17 criterios con evidencia, 29 de 29 mutaciones detectadas, fuentes oficiales citadas y un defecto corregido (la plantilla no llegaba a 40 campos) |
| [REVIEW.md](REVIEW.md) | Aprobada, sin critical ni major abiertos: K1 (conocimiento desactualizado), X1 (longitudes de los textos del LLM) y C1 (taxonomía demasiado grande para la plantilla) resueltos |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.10.0` a `v0.11.0`.

- **API:**
  - catálogo de destinos con grupos y checks activos;
  - tipo «lista» y 40 campos por esquema;
  - validación por destino (`app/flows/fields.py`) con rechazo campo a campo y `sin_valor`;
  - reglas del editor por tipo y `unknown_check`;
  - plantilla «Generar análisis completo»;
  - lectura campo a campo en el detalle, el cumplimiento (estado pendiente), los KPIs (`based_on`, `pending_kpis`), los filtros y el explorador.
- **Servicio de ingesta:**
  - `POST /analysis/fields` con todos los destinos;
  - combinación clave a clave;
  - motivos de los campos omitidos;
  - migración `0006` (`analysis.sentiment`).
- **Front:**
  - destinos agrupados y campo de origen filtrado por tipo;
  - «Lista» en el esquema;
  - resultado de la ejecución agrupado y con motivos;
  - detalle con análisis parcial;
  - dashboards con KPIs pendientes uno a uno.
- **OpenAPI:**
  - todos los códigos de validación (faltaban los de FE013);
  - `sin_valor`, `reasons`, `compliance_pending` y `pending_kpis`;
  - versión `0.11.0`.
- **Dependencias:** ninguna nueva.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0:

- vault sin errores;
- backend: 1.145 tests con cada dataset y 190 con PostgreSQL (`REQUIRE_PG=1`);
- OpenAPI al día y válido;
- front: 411 tests, lint y build;
- `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades «high»; siguen las 4 «moderate» de `sprintf-js`, que son anteriores.

`.github/workflows/ci.yml` ejecuta lo mismo. Ningún test usa red ni claves reales; las comprobaciones con Gemini están en el plan y en VERIFY.

## Observabilidad

- **Métrica de éxito/error:** recuentos por campo del Output «Guardar en campos» (`escrito`, `omitido`, `rechazado`, `sin_valor`, `error`) y motivo por campo y conversación.
- **Trazabilidad:** `analysis.llm_meta` por destino, también cada `compliance:<código>` y cada `entity:<tipo>`.
- **KPIs:** `based_on` y `pending_kpis` hacen visible cuánta parte del análisis existe ya.
- **Salud y logs:** los del servicio de LLM (FE013).

## Rollout y rollback

- **Rollout:** etiqueta `v0.11.0` en `main`, sin despliegue. La migración `0006` es aditiva y se aplica al arrancar el servicio de ingesta. No hay configuración nueva.
- **Cambio de comportamiento visible:** con datos reales, KPIs y detalle se rellenan campo a campo.
- **Rollback:**
  - en caliente: no ejecutar los flujos o pasar sus Prompts a «Simulado»;
  - datos: redescarga con «Sobrescribir»;
  - código: `git checkout v0.10.0`; ver la [entrega](../../vault/entregas/2026-10-13-plataforma-v0-11-0.md).

## Pendiente conocido

- Adaptadores de OpenAI y Anthropic con el esquema de lista y la plantilla completa sin probar contra sus APIs (no hay claves): hipótesis en [ADR-009](../../vault/decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md).
- El detalle no indica si el sentimiento viene de Genesys o del LLM ([REVIEW.md](REVIEW.md), C3).

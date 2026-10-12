# FE013 — Ship

> Fase `/ship`. Fecha: 2026-10-13. Entrega: [Plataforma v0.10.0](../../vault/entregas/2026-10-13-plataforma-v0-10-0.md).

## Trazabilidad

| Artefacto | Estado |
|---|---|
| [spec.md](spec.md) | Entregada; aprobada el 2026-10-12 y ampliada durante el ciclo (criterios 16 y 26–31) |
| [plan.md](plan.md) | T1–T9 hechas, cada una con rojo a verde y su commit; notas por tarea con la documentación contrastada y los recorridos |
| [VERIFY.md](VERIFY.md) | Verde: 31 criterios con evidencia, 30 de 30 mutaciones detectadas y 4 defectos corregidos |
| [REVIEW.md](REVIEW.md) | Aprobada, sin critical ni major abiertos: C1 (tiempo de espera de la API), X1 (aviso de resultados simulados en datos reales) y K1 (arquitectura) resueltos |

## Resumen del cambio

Integración trunk-based en `main`, de `v0.9.0` a `v0.10.0`.

- **Servicio de LLM** (`backend/llm/`): `LlmProvider` con Gemini, OpenAI, Anthropic y simulado por REST con `httpx`; token interno, reintentos, límite de concurrencia y logs sin datos sensibles.
- **API:** catálogo de proveedores y modelos (con `temperature`), `LlmPromptRunner` y enrutado por proveedor, valores permitidos, Output «Guardar en campos», escritor por lotes, plantillas, `GET /api/config/ai/status` y `POST /api/config/ai/test/{provider}`, protección de la taxonomía y lectura de summary y main topic con el análisis pendiente.
- **Servicio de ingesta:** «Sobrescribir» en los flujos de descarga, omisión de existentes, `POST /analysis/fields` y migraciones `0003` a `0005`.
- **Front:** Configuración → Modelos de IA con estado y «Probar», proveedor en el nodo Prompt, valores permitidos, panel y resultado de «Guardar en campos», plantillas en «Nuevo flujo» y «Sobrescribir» en las descargas.
- **Scripts:** `dev.sh` arranca el servicio de LLM si hay `LLM_TOKEN`; `.env.example` documenta sus claves.
- **Dependencias:** ninguna nueva.

## Pipeline con gates

`./scripts/ci.sh` termina con código 0: vault sin errores; 1033 tests de backend con cada dataset; 149 tests con PostgreSQL (`REQUIRE_PG=1`); OpenAPI al día y válido; 402 tests de front, lint y build; `pip-audit` y `npm audit --audit-level=high` sin vulnerabilidades «high» (siguen las 4 «moderate» de `sprintf-js`, anteriores). `.github/workflows/ci.yml` ejecuta lo mismo. Los tests del servicio de LLM no usan red ni claves reales.

## Observabilidad

- **Salud:** `GET /health` del servicio de LLM y Configuración → Modelos de IA («Clave configurada», «Probar»); la validación de un flujo marca `llm_unavailable` si el servicio no responde.
- **Logs:** logger `llm` con proveedor, modelo, intento, duración y resultado por llamada.
- **Métrica de éxito/error por ejecución:** recuentos `rejected` y `failed` de cada Prompt y estados `escrito`, `omitido`, `rechazado` y `error` por campo en «Guardar en campos».
- **Trazabilidad de datos:** `analysis.llm_meta` (proveedor, modelo, `1RN`, instante) y `skipped_existing` en las descargas.

## Rollout y rollback

- **Rollout:** etiqueta `v0.10.0` en `main`, sin despliegue. El servicio de LLM solo arranca con `LLM_TOKEN`; sin claves, todo funciona con el proveedor «Simulado». Las migraciones son aditivas y se aplican al arrancar el servicio de ingesta.
- **Cambio de comportamiento visible:** las descargas ya no actualizan conversaciones existentes salvo con «Sobrescribir».
- **Rollback:** en caliente, «Simulado» o parar el servicio de LLM; datos, redescarga con «Sobrescribir»; código, `git checkout v0.9.0` (las columnas nuevas se ignoran; ver la [entrega](../../vault/entregas/2026-10-13-plataforma-v0-10-0.md)).

## Pendiente conocido

- Adaptadores de OpenAI y Anthropic sin probar contra sus APIs reales (no hay claves): hipótesis en [ADR-009](../../vault/decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md).

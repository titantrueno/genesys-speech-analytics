# FE009 — Tests independientes del dataset mock

> Estado: **pendiente de aprobación**. Tarea técnica, sin cambios de producto. Surge de la [verificación de FE005](../FE005-configuracion-de-la-plataforma/VERIFY.md#deuda-encontrada-fuera-de-alcance).

## Objetivo

Que la batería de tests del backend pase con cualquier semilla y fecha de referencia del dataset mock, de modo que un test solo falle cuando se rompe el comportamiento que prueba.

## Situación actual (hecho medido el 2026-09-29)

`cd backend && DATA_SEED=<s> DATA_REFERENCE_DATE=<f> .venv/bin/pytest` sobre `main` (`4f908a1`):

| Semilla / fecha | Fallos |
|---|---|
| 42 / 2026-09-27 (la del `conftest.py`) | 0 de 662 |
| 7 / 2026-09-27 (solo cambia la semilla) | 53 |
| 42 / 2026-11-10 (solo cambia la fecha) | 59 |
| 7 / 2026-11-10 | 63 |
| 123 / 2026-04-15 | 64 |
| 2026 / 2025-12-31 | 62 |

Los mismos tests fallan en `v0.4.0`: la deuda es anterior a FE005. Hay tres causas:

1. **Fechas absolutas** en los tests: por ejemplo, `{"from": "2026-07-01", "to": "2026-09-26"}` o el periodo por defecto `2026-08-28`–`2026-09-26`.
2. **Datasets propios con semilla fija:** `test_conversations.py`, `test_metrics.py`, `test_query_engine.py` y `test_query_suggest.py` generan su dataset con `seed=42` y fecha 2026-09-27 para calcular el valor esperado, pero la API usa el del entorno.
3. **Hechos de una semilla concreta:** identificadores, recuentos o conversaciones elegidas a mano.

Ficheros afectados: `test_conversations.py`, `test_metrics.py`, `test_query_engine.py`, `test_query_interpreter.py`, `test_query_model.py`, `test_query_suggest.py`, `test_search_api.py` y `test_search_relevance.py` (FE001, FE002 y FE003). Los de FE004 y FE005 ya usan fechas relativas (`days_ago` en `tests/flow_fixtures.py`).

## Criterios de aceptación

1. La suite completa del backend pasa, sin tests omitidos ni marcados como fallo esperado, con al menos estas combinaciones: 42/2026-09-27, 7/2026-09-27, 42/2026-11-10, 7/2026-11-10, 123/2026-04-15 y 2026/2025-12-31. Las dos últimas cruzan los cambios de hora del 25 de octubre y del 29 de marzo.
2. **Fechas relativas:** ningún test fija una fecha del dataset. Las fechas se expresan relativas a `reference_date()` con un único helper compartido; `days_ago` se mueve de `tests/flow_fixtures.py` a un módulo común.
3. **Un solo dataset:** el valor esperado de un test se calcula sobre el mismo dataset que sirve la API (`get_dataset()`), no sobre uno generado aparte.
4. **Hechos buscados, no fijados:** cuando un test necesita una conversación con cierta propiedad (un topic, un canal, un DNI…), la busca en el dataset en lugar de fijar su identificador o su posición.
5. **Tests de calibración explícitos:** los tests que miden la relevancia de la búsqueda frente a consultas etiquetadas (FE003) dependen de verdad de un dataset concreto. Esos tests construyen su propio motor con semilla 42 y fecha 2026-09-27 de forma explícita, independiente del entorno, y lo documentan en su docstring. Siguen pasando con cualquier combinación del criterio 1.
6. **Mismo poder de detección:** ningún test pierde aserciones al hacerse relativo. Para cada fichero modificado, al menos una mutación del código que prueba sigue detectándose (se registra en el plan).
7. **Gate:** `./scripts/ci.sh` ejecuta la suite del backend una segunda vez con una combinación distinta de la del `conftest.py` (por ejemplo, 7/2026-11-10), para que la deuda no vuelva. El tiempo total del gate crece como mucho en lo que tarda esa segunda ejecución (unos 30 s).
8. Los tests de front no cambian (usan fixtures, no el dataset).

## Conocimiento afectado

- [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md): la lección 5 ya pedía fechas de referencia distintas de hoy; se amplía con «ni fechas ni hechos de una semilla» y se anota la segunda ejecución del gate.
- [Ciclo de entrega](../../vault/ingenieria/ciclo-de-entrega.md): el gate ejecuta el backend con dos combinaciones.
- [Estado operativo](../../vault/operaciones/estado-operativo.md): `DATA_SEED` y `DATA_REFERENCE_DATE` como forma de probar robustez.
- [ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md): los resultados de relevancia medidos se refieren al dataset con semilla 42 y fecha 2026-09-27.

## Alcance

- Tests del backend de FE001, FE002 y FE003, el helper común de fechas y `scripts/ci.sh`.

## Fuera de alcance

- Cambios en el código de la aplicación, salvo que un test relativo destape un bug real. En ese caso se corrige con su test de regresión y se anota en el plan.
- Tests del front.
- Cambiar la semilla o la fecha por defecto del `conftest.py`.

## Riesgos y asunciones

- **Riesgo:** al hacer un test relativo es fácil debilitarlo (por ejemplo, comparar con el propio resultado de la API). El criterio 6 lo mitiga con mutaciones.
- **Riesgo:** algunas propiedades estadísticas del generador (por ejemplo, que `cargo_no_reconocido` esté entre los cinco topics con más volumen, o el pico de fraude) podrían no cumplirse con cualquier semilla. Si una no se cumple, se documenta como propiedad de la semilla por defecto en lugar de relajarla sin más.
- **Asunción:** los tests relativos de FE004 y FE005 son el patrón a seguir.

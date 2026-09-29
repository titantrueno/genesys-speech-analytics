# FE009 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-09-29. Siguiente paso: `/build`, en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| `tests/conftest.py` | Fija `DATA_SEED=42` y `DATA_REFERENCE_DATE=2026-09-27` con `setdefault`, así que el entorno manda | Sin cambios: basta con exportar las variables para probar otra combinación (T4) |
| `tests/flow_fixtures.py` | `days_ago` relativo a `reference_date()` (FE004) | Se mueve a `tests/dates.py` con los helpers del periodo por defecto; `flow_fixtures.py` lo reexporta para no tocar FE004 y FE005 (T1) |
| `test_conversations.py`, `test_metrics.py` (FE001) | 25 fechas o semillas fijas; `test_metrics.py` genera su propio dataset con semilla 42 | T1 |
| `test_query_*.py` (FE002) | 29 fechas o semillas fijas; `test_query_engine.py` genera su propio dataset; el intérprete espera periodos absolutos («últimos 7 días» → `2026-09-20`) | T2 |
| `test_search_api.py`, `test_search_relevance.py` y `search_relevance.py` (FE003) | La relevancia usa `get_dataset()`, así que depende del entorno; sus consultas etiquetadas se midieron con la semilla 42 | T3: motor explícito con semilla 42 y fecha 2026-09-27 |
| `scripts/ci.sh` | Ejecuta `pytest -q` una vez | T4: segunda ejecución con 7/2026-11-10 |
| [Lecciones](../../vault/aprendizaje/lecciones-construccion-plataforma.md), [ciclo de entrega](../../vault/ingenieria/ciclo-de-entrega.md), [estado operativo](../../vault/operaciones/estado-operativo.md), [ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md) | Ver «Conocimiento afectado» de la spec | T4 |

## Decisiones de diseño

- **Un único helper de fechas** (`tests/dates.py`): `days_ago(n)`, `default_period()` (igual al del backend: los 30 días que acaban el día anterior a la fecha de referencia) y `day(conv)` (día local de una conversación).
- **El valor esperado sale del mismo dataset que la API** (`get_dataset()` y `reference_date()`), calculado de forma independiente: filtros escritos en el test, no la función del backend que se prueba.
- **Buscar, no fijar:** helpers como `first_conversation(predicate)` sustituyen identificadores y posiciones.
- **Calibración explícita:** los tests de relevancia de FE003 construyen su motor con `generate_dataset(seed=42, reference_date=date(2026, 9, 27))` y lo dicen en el docstring; no leen el entorno.
- **Mismo poder de detección:** en cada tarea se aplican las mismas mutaciones al código probado antes y después del cambio de los tests (criterio 6).

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Helper de fechas y tests de FE001 (listado, detalle, métricas) | — | 1–4, 6 |
| T2 | Tests de FE002 (motor, modelo, intérprete y sugerencias) | T1 | 1–4, 6 |
| T3 | Tests de FE003 (API de búsqueda y relevancia con motor explícito) | T1 | 1, 4, 5, 6 |
| T4 | Segunda ejecución en el gate, conocimiento y matriz de combinaciones | T1–T3 | 1, 7, 8 y conocimiento afectado |

### T1 — Helper y FE001

- **Qué:** `tests/dates.py`; `flow_fixtures.py` lo reexporta; `test_conversations.py` y `test_metrics.py` sin fechas ni semillas fijas, con los esperados calculados sobre `get_dataset()`.
- **Hecho cuando:** los dos ficheros pasan con las seis combinaciones del criterio 1 y la suite completa sigue en verde con la combinación por defecto. Las mutaciones de `services/kpis.py`, `services/filters.py` y `services/listing.py` (una por fichero de test, como mínimo) se detectan antes y después.

### T2 — FE002

- **Qué:** `test_query_engine.py` sin dataset propio; periodos del intérprete relativos a la fecha de referencia; `test_query_model.py` y `test_query_suggest.py` sin fechas fijas.
- **Hecho cuando:** los cuatro ficheros pasan con las seis combinaciones; mutaciones de `query/engine.py`, `query/interpreter.py` y del periodo por defecto detectadas antes y después.

### T3 — FE003

- **Qué:** `test_search_relevance.py` y `search_relevance.py` con motor explícito (semilla 42, 2026-09-27); `test_search_api.py` busca en el dataset los casos que hoy fija.
- **Hecho cuando:** los dos ficheros pasan con las seis combinaciones; los resultados de relevancia no cambian con la semilla por defecto (misma tasa que en ADR-005); mutaciones del diccionario de sinónimos y de `focus` detectadas.

### T4 — Gate, conocimiento y matriz

- **Qué:** `scripts/ci.sh` ejecuta el backend una segunda vez con `DATA_SEED=7 DATA_REFERENCE_DATE=2026-11-10`; vault (lecciones, ciclo de entrega, estado operativo y ADR-005); README.
- **Hecho cuando:** la suite completa pasa con las seis combinaciones (tabla en este plan); `./scripts/ci.sh` termina con código 0 y falla si se reintroduce una fecha fija en un test (comprobado a mano); `python scripts/audit_vault.py` con código 0.

## Riesgos del plan

- **Tests debilitados (T1–T3):** mitigado con las mutaciones antes y después.
- **Propiedades estadísticas de la semilla (T1):** si un test de distribución (por ejemplo, los cinco topics con más volumen) no se cumple con otra semilla, se documenta como propiedad de la semilla 42 y ese test genera su dataset de forma explícita, como la calibración de FE003.

## Progreso

| Id | Estado | Evidencia |
|---|---|---|
| T1 | Hecha | `tests/dates.py` (`day_ago`, `days_ago`, `default_period` calculado sin el backend y `weekday_on_or_before`); `flow_fixtures.py` reexporta `days_ago`. `test_metrics.py` y `test_conversations.py` sin fechas ni semillas fijas: el esperado sale de `get_dataset()` con filtros y recontacto calculados en el test; la semana parcial se construye a partir de un miércoles y se recortan los casos en que acabaría en domingo; la fecha de referencia se compara con `DATA_REFERENCE_DATE` (no con `reference_date()` del backend). **60/60 con las seis combinaciones** (antes fallaban 15–17 de estos dos ficheros). Mutaciones (escalado, periodo anterior, periodo por defecto, semanas, summary recortado, FCR y orden del listado): **7/7 antes y 7/7 después**, con 42/2026-09-27 y con 7/2026-11-10. |
| T2 | Hecha | `test_query_engine.py` y `test_query_suggest.py` usan `get_dataset()` en lugar de su dataset con semilla 42; periodos con `days_ago`, `day_ago` y `default_period`; el intérprete espera «últimos N días», «esta semana» (lunes de la semana del día anterior) y el tope de 3.650 días calculados a partir de la fecha de referencia; `test_query_model.py` sin fechas fijas. `test_query_saved.py` guarda y relee fechas arbitrarias (no son fechas del dataset) y no cambia. **122/122 con las seis combinaciones** (antes fallaban 36–40 de estos ficheros). Mutaciones del motor (`gte`, `or`, límite del periodo), del intérprete («últimos N días» y «esta semana»), de las sugerencias multivalor y de la validación de valores: **6/7 antes (`v0.5.0`, en un worktree) y 6/7 después**, con 42/2026-09-27 y 7/2026-11-10. La que sobrevive (contar dos veces un tema secundario repetido) es equivalente con estos datos: ninguna conversación repite un tema secundario en tres semillas. |
| T3 | Pendiente | |
| T4 | Pendiente | |

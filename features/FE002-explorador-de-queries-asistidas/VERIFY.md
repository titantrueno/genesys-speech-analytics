# FE002 — Verificación

> Fase `/test`. Fecha: 2026-09-28. Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde.** Los 18 criterios tienen evidencia. El fuzzing encontró 4 bugs del intérprete y la rutina de duda 1 caso de UI; los 5 están corregidos con test de regresión (commit `a4553bd`).

## Evidencia

| Comando | Resultado |
|---|---|
| `cd backend && .venv/bin/pytest` | **230 passed** |
| `cd frontend && npm test` | **109 passed** (11 ficheros) |
| `cd frontend && npm run lint` / `npm run build` | 0 avisos / OK |
| `python3 scripts/audit_vault.py` | Código 0 |
| `npm audit` / `pip-audit` | 0 vulnerabilidades |
| Fuzzing del intérprete (3.000 frases aleatorias, números hasta 10¹⁸) | Antes: 4 clases de fallo (un 500 y tres consultas no válidas). Después: **0** |
| Chrome contra la API real | **7/7** comprobaciones de T9 y 33 = 33 en T7b, sin errores de consola |

## Matriz de trazabilidad

| # | Criterio | Evidencia |
|---|---|---|
| 1 | Esquema con campos, tipos, operadores y valores | `test_schema_lists_every_field_with_type_and_valid_operators`, `test_schema_requires_explorer_permission` |
| 2 | Validación con `422` y resultado (total, KPIs, página) | `test_invalid_queries_report_the_offending_path` (20 casos), `test_all_errors_are_reported_at_once`, `test_invalid_query_returns_422_with_every_error_path`, `test_query_size_is_limited`, `test_empty_query_returns_the_whole_default_period` |
| 3 | Cada operador y `and`/`or` = filtrado independiente | `test_each_operator_matches_independent_filter` (31), `test_nested_and_or_groups`; mutaciones de `between` y del hablante detectadas |
| 4 | Sugerencias con recuento | `test_query_suggest.py` (10) |
| 5 | Intérprete con ≥ 12 frases y no entendido | 15 frases, no entendido, entrada no válida, números extremos y citas vacías, propiedad de 500 frases (32 tests) |
| 6 | Consultas guardadas privadas con `1QY` | `test_query_saved.py` (11) |
| 7 | Permiso `explorer:use` | Tests de `viewer` en esquema, ejecución y guardadas; tests de recorrido de rutas de FE001 |
| 8 | < 500 ms con 10 condiciones | `test_run_with_ten_conditions_responds_under_500ms` |
| 9 | Sección con intervalo, lenguaje natural, constructor y resultados | `ExplorerBuilder.test.tsx`, `ExplorerAssist.test.tsx`, `ExplorerResults.test.tsx` |
| 10 | Operadores y controles por tipo | «solo ofrece los operadores del tipo…», «los valores categóricos muestran sugerencias…», «es alguno de…», «agrupa condiciones con Y/O…» |
| 11 | Tiempo real, debounce y respuestas desordenadas | `hooks.test.tsx` (debounce y respuesta lenta anterior) |
| 12 | Lenguaje natural en la UI | `ExplorerAssist.test.tsx` (3 de lenguaje natural) |
| 13 | Texto legible y URL compartible | `queryModel.test.ts`; «al abrir un enlace con consulta…», «un enlace corrupto…» |
| 14 | Resultados, fila navegable y volver | `ExplorerResults.test.tsx` (recuento, KPIs y tabla; paginación y orden; fila y volver) |
| 15 | Consultas guardadas en la UI | `ExplorerAssist.test.tsx` (3 de consultas guardadas) |
| 16 | Estados de carga, error y vacío | `ExplorerResults.test.tsx` (vacío, error, carga), error `422` en fila y aviso general |
| 17 | `./scripts/ci.sh` en verde | Código 0 |
| 18 | Verificación en Chrome | 7/7 (T9): frase, total = listado FE001 (5 = 5), guardar y recargar, cargar, volver |

## Fundamentación

| Decisión | Fuente |
|---|---|
| Unión condición/grupo con discriminador invocable que acepta `dict` y modelo | [Pydantic · Unions](https://pydantic.dev/docs/validation/latest/concepts/unions/) |
| Consulta en la URL en base64url sin relleno | [RFC 4648 §5](https://www.rfc-editor.org/rfc/rfc4648#section-5) |
| Búsqueda sin tildes con NFKD y sin marcas combinantes | [Python · unicodedata](https://docs.python.org/3/library/unicodedata.html) |
| Resultados independientes por consulta (sin carreras) | [TanStack Query · Query keys](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys) |
| Borrador numérico ajustado en render, no en efecto | [React · You might not need an effect](https://react.dev/learn/you-might-not-need-an-effect) |

## Registro de duda

| Afirmación | Duda | Reconciliación | Conclusión |
|---|---|---|---|
| El intérprete siempre devuelve una consulta válida | ¿Solo con las 15 frases de ejemplo? | Fuzzing: un 500 y tres consultas no válidas | **Bugs 1–4** corregidos; propiedad de 500 frases en la suite |
| Todo error `422` se ve en su condición | ¿Y los errores sin fila, como el periodo? | Solo aparecía «Revisa las condiciones marcadas», sin ninguna marcada | **Bug 5** corregido: aviso general |
| El explorador y el listado cuentan igual | ¿Comparten filtros? | Mismo `services/listing.py`; test cruzado; Chrome 33 = 33 y 5 = 5 | Se cumple |
| Las consultas guardadas son privadas | ¿Se puede adivinar un identificador? | `404` para otro usuario; identificador aleatorio con `SystemRandom` | Se cumple |
| La API aguanta consultas grandes | ¿Sin límite de tamaño? | Sin límite, una consulta abusiva era posible | Límites de 50 condiciones y 200 valores (ver [REVIEW](REVIEW.md)) |

## Bugs encontrados en la verificación

| Bug | Causa raíz | Corrección | Regresión |
|---|---|---|---|
| 1. «últimos 10⁹ días» → 500 | `timedelta` sin tope desbordaba la fecha | Días acotados a [1, 3650] | Caso explícito + propiedad |
| 2. «últimos 0 días» → `from > to` | Rango no acotado por abajo | Mínimo 1 día | Caso explícito |
| 3. Duración enorme fuera de rango | Sin tope del campo | Acotada a 86.400 s | Caso explícito |
| 4. Cita vacía → texto vacío | No se filtraban citas en blanco | Se ignoran | Caso explícito |
| 5. `422` sin fila no se mostraba | Solo se mapeaban rutas de condición | Aviso general con el mensaje | «errores de validación sin condición asociada…» |

Durante `/build` también se corrigió que el valor anterior se arrastraba al cambiar de campo (`replaceCondition`, T7a), documentado en el plan.

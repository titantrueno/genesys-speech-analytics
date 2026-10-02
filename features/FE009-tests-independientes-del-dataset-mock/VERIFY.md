# FE009 — Verificación

> Fase `/test`. Fecha: 2026-10-02. Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde.** Los 8 criterios tienen evidencia. La suite completa del backend pasa con las seis combinaciones de semilla y fecha; antes fallaban entre 53 y 64 tests en cinco de ellas. No se encontraron bugs de la aplicación al hacer los tests relativos.

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `./scripts/ci.sh` | **Código 0**: vault (43 archivos, 0 errores), backend 666 con 42/2026-09-27 y 666 con 7/2026-11-10, front 267, lint, build y auditorías sin vulnerabilidades |
| Matriz de la suite completa del backend (ver el [plan](plan.md#matriz-de-combinaciones-suite-completa-del-backend-2026-10-02)) | 666 passed con 42/2026-09-27, 7/2026-09-27, 42/2026-11-10, 7/2026-11-10, 123/2026-04-15 y 2026/2025-12-31 |
| Mutaciones antes (`v0.5.0`, en un worktree) y después, con 42/2026-09-27 y 7/2026-11-10 | T1 7/7 → 7/7; T2 6/7 → 6/7 (la superviviente es equivalente con estos datos); T3 3/4 → **4/4** |
| Gate con una fecha fija reintroducida a propósito en `test_metrics.py` | Primera pasada 666 passed, segunda 1 failed, **código 1** |
| Relevancia de calibración con el entorno en 7/2026-11-10 | 23/24 = 96 % (como en ADR-005); despedidas por debajo del 10 % |

## Matriz de trazabilidad

| # | Criterio | Evidencia |
|---|---|---|
| 1 | Seis combinaciones en verde, sin omitir tests | Matriz del plan (666/666 en las seis; ningún `skip` ni `xfail` añadido) |
| 2 | Fechas relativas con un helper único | `tests/dates.py`; `flow_fixtures.py` lo reexporta. Las fechas literales que quedan no son del dataset (ver «Registro de duda») |
| 3 | Un solo dataset | `test_conversations.py`, `test_metrics.py`, `test_query_engine.py` y `test_query_suggest.py` usan `get_dataset()`; el recontacto esperado se calcula en el test |
| 4 | Hechos buscados, no fijados | Conversación de muestra por posición relativa; casos del motor que se comprueban no vacíos y filtrantes; resaltado con 100 resultados y comprobación por resultado |
| 5 | Calibración explícita | `calibration_dataset()` con semilla 42 y 2026-09-27 en `test_search_relevance.py`, con docstring; ADR-005 lo recoge |
| 6 | Mismo poder de detección | Mutaciones antes y después por tarea (arriba) |
| 7 | Segunda pasada en el gate | `scripts/ci.sh` y `.github/workflows/ci.yml`; prueba con la fecha fija reintroducida |
| 8 | Tests del front sin cambios | Ningún test del front cambia en FE009. Aparte, `vite.config.ts` sube el límite por test a 15 s (`0eef317`, ver REVIEW R1) |

## Fundamentación

| Decisión | Fuente |
|---|---|
| Variables de entorno en el `conftest.py` con `setdefault`, sobrescribibles desde el gate | [pytest · conftest.py](https://docs.pytest.org/en/stable/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files) |
| `env` por paso en GitHub Actions | [GitHub Actions · `jobs.<job_id>.steps[*].env`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsenv) |
| Límite por test de Vitest | [Vitest · testTimeout](https://vitest.dev/config/#testtimeout) |

## Registro de duda

| Afirmación | Duda | Reconciliación | Conclusión |
|---|---|---|---|
| Ningún test fija una fecha del dataset | ¿Quedan fechas literales? | Búsqueda en `tests/`: `conftest.py` (valor por defecto), `test_dataset.py` (prueba el generador con semilla explícita y huella documentada), calibración de FE003, un texto del enmascarado, fechas guardadas y releídas en consultas guardadas y un intervalo invertido que debe dar `422` | Ninguna es un hecho del dataset; todas pasan con las seis combinaciones |
| Los tests relativos no son más débiles | Al calcular el esperado con el mismo dataset es fácil acabar comparando la API consigo misma | Esperados con filtros escritos en el test; mutaciones antes y después | Igual o mejor (T3 detecta una más) |
| La deuda no volverá | Basta con que alguien escriba una fecha fija | Gate con segunda pasada; prueba con la fecha reintroducida | Se detecta (código 1) |
| La relevancia no depende del entorno | Antes leía `get_dataset()` | Motor de calibración explícito; 96 % con el entorno en 7/2026-11-10 | Se cumple |
| Los fallos intermitentes del gate eran del código | Tests que «tardaban» 68–87 s | `pmset -g log`: reposos de 25–87 s con batería | Eran reposos del Mac; documentado en el runbook |

## Bugs encontrados

Ninguno en la aplicación. En el entorno: el reposo del Mac con batería congelaba los procesos durante el gate (runbook actualizado).

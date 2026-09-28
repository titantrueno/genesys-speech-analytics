# FE003 — Verificación

> Fase `/test`. Fecha: 2026-09-28. Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde, con una limitación medida.** Los 20 criterios tienen evidencia con el dataset por defecto (`DATA_SEED=42`).

La rutina de duda no encontró errores de código. Sí encontró tres cosas:

- una cifra de memoria desactualizada en la documentación, ya corregida;
- un caso sin test (umbral no válido en la URL), ya cubierto con un test de regresión;
- que los criterios 3 y 18 dependen del dataset concreto: con otras semillas, el par «me han cobrado algo que no he comprado» sale del top 5.

Lo último se documenta como limitación (ver [ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md)) y no se corrige ajustando pesos al conjunto de test.

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `cd backend && .venv/bin/pytest` | **317 passed** |
| `cd frontend && npm test` | **149 passed** (14 ficheros; 144 más 5 de regresión añadidos en esta fase) |
| `cd frontend && npm run lint` / `npm run build` | 0 avisos / OK |
| `python3 scripts/audit_vault.py` | Código 0 |
| `npm audit` / `pip-audit` | 0 vulnerabilidades |
| `./scripts/ci.sh` | Código 0 |
| Fuzzing de la API (3.000 textos: vocabulario del dominio, metacaracteres de regex, emojis, diacríticos sueltos, espacios de ancho cero; agrupación, umbral y límite aleatorios) | **0 fallos**: sin `500`, puntuaciones y `max_score` en 0–1, orden descendente, `total ≥` resultados y todos los resaltados presentes en su fragmento |
| Peor caso de rendimiento (consultas de 500 caracteres, `group=fragment`, `limit=100`, 90 días) | **55 ms** (vocabulario del corpus), 33 ms (expresiones del diccionario), 12 ms (una palabra repetida), 11 ms (caracteres aleatorios) |
| Memoria del índice (`tracemalloc`) | 52 MB retenidos y 263 MB de pico durante la construcción; construcción en 2,44 s |
| Chrome contra la API real (Playwright con el Chrome instalado) | Recorridos de T5, T5c, T6 y T7 (criterio 17) sin errores de consola |

## Matriz de trazabilidad

| # | Criterio | Evidencia |
|---|---|---|
| 1 | TF-IDF por fragmentos detrás de `SearchEngine` | `test_search_engine.py` (fragmentos, puntuación, tildes y flexión, candidatos, similares, interfaz); `test_api_only_depends_on_the_search_engine_interface` y `test_uses_the_injected_engine` con motores falsos |
| 2 | Índice al arrancar, sin dependencias nuevas | `test_index_is_built_at_startup_before_the_first_search`; `backend/requirements.txt` sin cambios desde `v0.2.0` |
| 3 | ≥ 8 pares encontrados solo con el diccionario | `test_pair_shares_no_content_word_with_its_topic` y `test_pair_is_found_only_thanks_to_the_dictionary` (9 pares, contra los turnos reales); mutación `EXPANSION_WEIGHT = 0` detectada. Ver la limitación entre semillas más abajo |
| 4 | Parámetros, orden, total y forma del resultado | `test_result_shape_metadata_turns_and_expansions`, `test_highlights_*`, `test_results_are_sorted_and_rounded`, `test_group_by_conversation_scores_each_conversation_by_its_best_fragment`, `test_min_score_filters_and_total_counts_before_limit`, `test_default_limit_is_twenty`, `test_filters_match_an_independent_filtering` (4), `test_default_period_is_the_platform_default` |
| 5 | `422` y propiedad sin `500` | `test_invalid_parameters_return_422` (14); `test_random_texts_never_fail` (300) y fuzzing de 3.000 en esta fase |
| 6 | 10 similares sin la propia conversación, `404` | `test_search_similar.py` (8) |
| 7 | Permiso `search:use` | `test_viewer_gets_403` en ambas rutas; recorrido de rutas del OpenAPI en `test_auth.py` |
| 8 | ≥ 80 % en el top 5 | `test_labelled_queries_reach_eighty_percent_in_top_five`: **23/24 (96 %)**; 83 % sin diccionario |
| 9 | < 500 ms por consulta | `test_each_labelled_query_answers_in_under_500_ms`; mediana de 12 ms y peor caso de 55 ms |
| 10 | Sección, filtros y búsqueda en la URL | `SearchPage.test.tsx` (formulario y URL, 6 + 5 de umbral no válido) |
| 11 | Resaltado, puntuación, metadatos y expansión | «muestra el fragmento resaltado, la puntuación y los metadatos» |
| 12 | Umbral, agrupación y respuestas desordenadas | «el umbral relanza la búsqueda con debounce», «agrupar por fragmentos…», `api.test.tsx` (respuesta lenta anterior) |
| 13 | Detalle en el turno, volver y fila navegable | `SearchNavigation.test.tsx` (turno, turnos no válidos, volver) y `SearchPage.test.tsx` (clic, un enlace, Ctrl/Cmd, clic central, selección) |
| 14 | Botón de similares con permiso | `SearchNavigation.test.tsx` (botón, viewer, vista, `404`, error, salir con una búsqueda) |
| 15 | Estados | inicial, «Buscando…», error con el formulario usable y sin resultados |
| 16 | `./scripts/ci.sh` en verde | Código 0 |
| 17 | Verificación en Chrome | Recorrido de T7: par de cajeros 5/5, umbral y agrupación, turno, volver, similares y sin errores de consola |
| 18 | Representantes con < 10 % de despedidas | `test_closing_template_is_rarely_the_best_fragment`: **9,7 %** (35 % antes de T5b) |
| 19 | `max_score` y umbral en contexto | `test_max_score_*` (2) y «umbral en contexto» (3) |
| 20 | Limitación documentada | [ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md), «Limitaciones del enfoque léxico» y «Migración a embeddings» |

## Robustez frente al dataset

Las métricas se midieron con varias semillas y fechas de referencia para comprobar si dependían del dataset concreto:

| Semilla y fecha de referencia | Relevancia (criterio 8) | Pares (criterio 3) | Despedidas (criterio 18) |
|---|---|---|---|
| 42, 2026-09-27 (por defecto) | 23/24 | 9/9 | 9,7 % |
| 42, 2026-03-01 | 23/24 | 9/9 | 9,7 % |
| 7, 2026-09-27 | 23/24 | 7/9 | 9,1 % |
| 123, 2026-09-27 | 22/24 | 8/9 | 7,9 % |
| 2026, 2026-09-27 | 23/24 | 9/9 | 10,9 % |

- **La relevancia es robusta:** 92–96 %, con holgura sobre el 80 %.
- **Los pares son frágiles, por dos causas distintas:**
  - «me han cobrado algo que no he comprado»: con las semillas 7 y 123, el primer resultado de `cargo_no_reconocido` queda en la posición 8 y 15, por detrás de conversaciones de `comisiones` cuyos clientes dicen literalmente «cobrado». Es la limitación 4 del ADR-005, ahora cuantificada;
  - «la máquina no soltó los billetes»: con la semilla 7 se encuentra también sin diccionario (posición 5), así que deja de ser un par válido para ese dataset. Es un problema de la prueba, no del motor.
- **Las despedidas** quedan cerca del 10 % en todas las semillas y lo superan en una (10,9 %).

**Decisión:** no se ajustan `EXPANSION_WEIGHT` ni `CUSTOMER_WEIGHT` con estas consultas, porque sería sobreajustar el motor a su propio conjunto de evaluación. Los criterios se consideran cumplidos para el dataset por defecto, y la fragilidad queda como evidencia para la migración a embeddings.

## Fundamentación

| Decisión | Fuente |
|---|---|
| Índice construido en el arranque con `lifespan` | [FastAPI · Lifespan events](https://fastapi.tiangolo.com/advanced/events/) |
| Motor sustituible en los tests | [FastAPI · Testing dependencies with overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/) |
| TF sublineal, IDF y coseno sobre vectores normalizados | [Manning, Raghavan y Schütze · Introduction to Information Retrieval, cap. 6](https://nlp.stanford.edu/IR-book/html/htmledition/sublinear-tf-scaling-1.html) |
| Normalización con pivote, probada y descartada en T5 | [Introduction to Information Retrieval · Pivoted normalized document length](https://nlp.stanford.edu/IR-book/html/htmledition/pivoted-normalized-document-length-1.html) |
| Postings compactos con `array` | [Python · array](https://docs.python.org/3/library/array.html) |
| Normalización sin tildes (NFKD sin marcas combinantes) | [Python · unicodedata](https://docs.python.org/3/library/unicodedata.html) |
| Barra de puntuación con rol `meter` | [WAI-ARIA 1.2 · meter](https://www.w3.org/TR/wai-aria-1.2/#meter) |
| Control del umbral con `input type="range"` | [MDN · input type="range"](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/range) |
| Desplazar solo el chat con `Element.scrollTo` | [MDN · Element.scrollTo()](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollTo) |
| Borradores ajustados durante el render, no en un efecto | [React · Storing information from previous renders](https://react.dev/reference/react/useState#storing-information-from-previous-renders) |
| Búsqueda desactivada sin consulta (`enabled`) | [TanStack Query · Disabling queries](https://tanstack.com/query/latest/docs/framework/react/guides/disabling-queries) |
| Navegador de verificación: Chrome instalado | [Playwright · Google Chrome](https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge) |

## Registro de duda

| Afirmación | Duda | Reconciliación | Conclusión |
|---|---|---|---|
| Responde en menos de 500 ms | ¿Solo con frases normales? | Consultas de 500 caracteres: peor caso de 55 ms | Se cumple con holgura |
| Nunca da `500` y las puntuaciones están en 0–1 | ¿Solo con 300 textos de la suite? | Fuzzing de 3.000 textos, con resaltados y `max_score` incluidos: 0 fallos | Se cumple |
| El índice ocupa unos 45 MB | La cifra se midió antes del índice del cliente (T5b) | 52 MB retenidos y 263 MB de pico | **Documentación corregida** (arquitectura y ADR-005) |
| El bundle principal ocupa 397 kB | Cifra anterior a FE003 | Build actual: 437 kB | **Documentación corregida** |
| El umbral de la URL siempre es válido | ¿Y `abc`, `5`, `NaN`? | Se ignoraba bien, pero sin test | **Regresión añadida** (5 casos) |
| Los criterios 3, 8 y 18 son propiedades del motor | ¿O del dataset con semilla 42? | Tabla de robustez: la relevancia aguanta; los pares y las despedidas no del todo | **Limitación medida y documentada**; sin ajustar pesos |
| Un representante nunca queda bajo el umbral | ¿El umbral se aplica antes o después de agrupar? | `semantic()` filtra por `score` antes de `best_per_conversation` | Se cumple |
| Las búsquedas simultáneas no se interfieren | ¿El motor tiene estado mutable? | El índice es de solo lectura tras construirse y cada búsqueda crea sus propios diccionarios | Se cumple |
| El turno del fragmento es el del detalle | Los índices de los fragmentos cuentan los turnos de `sistema` | Chrome: el texto del turno activo coincide con el del fragmento | Se cumple |

## Bugs encontrados en la verificación

No se encontraron errores de comportamiento. Los fallos corregidos durante `/build` están en el [plan](plan.md#progreso):

- el texto común pesaba más que el tema (T1);
- pares no válidos por comercios y el PIN (T2);
- supuestos erróneos en tests de la API (T3);
- aviso de lint `set-state-in-effect` (T5);
- la despedida plantillada salía como fragmento (T5b);
- el texto de ayuda descuadraba la fila de filtros (T5c).

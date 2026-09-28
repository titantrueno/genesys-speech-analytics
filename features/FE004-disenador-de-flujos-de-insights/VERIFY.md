# FE004 — Verificación

> Fase `/test`. Fecha: 2026-09-28. Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde.** Los 21 criterios tienen evidencia. La rutina de duda encontró un error real y una fragilidad de los tests, y los dos quedan corregidos con regresión:

- **Error:** un nodo con `type` no hashable (una lista o un objeto) hacía que `parse_graph` lanzara `TypeError`, así que `PUT …/graph` y `POST /api/flows/validate` respondían `500`. Lo encontró un fuzzing de 9.000 peticiones (170 respuestas `500`). Tras corregirlo, 0 `500`, y hay 6 tests de regresión.
- **Fragilidad:** los tests de flujos fijaban fechas de septiembre de 2026 y fallaban (22) con otra fecha de referencia del dataset. Ahora usan fechas relativas (`days_ago`) y pasan con 4 combinaciones de semilla y fecha.

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `cd backend && .venv/bin/pytest` | **508 passed** (191 de FE004, con el límite del historial añadido en `/review`) |
| `cd frontend && npm test` | **230 passed** (20 ficheros; 81 de FE004) |
| `npm run lint` / `npm run build` | Código 0 / código 0 (comprobados por código de salida, no por salida filtrada) |
| `python3 scripts/audit_vault.py` | Código 0: 40 archivos, 0 errores |
| `npm audit` / `pip-audit` | 0 vulnerabilidades |
| `./scripts/ci.sh` | **Código 0** |
| Fuzzing de la API (3.000 grafos aleatorios mutados con tipos erróneos, textos de 5.000 caracteres, números extremos y cuerpos que no son objetos, en `validate` y `PUT …/graph`; 3.000 estimaciones con consultas mutadas) | **0 respuestas `5xx`** en 9.000 peticiones (7.875 `422` y 1.125 `200`). Cada `200` de `PUT` se relee y coincide con lo guardado |
| Robustez frente al dataset (tests de flujos con semilla y fecha de referencia 42/2026-09-27, 7/2026-09-27, 123/2026-03-01 y 2026/2025-12-31) | 190/190 en las cuatro |
| Rendimiento (sin retardo simulado) | Ejecución de 1.000 conversaciones con 2 prompts en cadena y 2 outputs: 21 ms; detalle de 0,92 MB en 4 ms; listado de 62 flujos (valida cada uno): 2 ms; validar un grafo de 50 nodos: 1,7 ms |
| Servidor real (uvicorn) | `202` en 1 ms, `409` durante la ejecución y progreso visible por polling; 40 conversaciones con 2 prompts en 1,9 s |
| Chrome contra la API real (Playwright con el Chrome instalado) | Recorridos de T6, T7 y del criterio 21 (T9) sin errores de consola |

## Matriz de trazabilidad

| # | Criterio | Evidencia |
|---|---|---|
| 1 | CRUD y listado | `test_flows_api.py`: crear, listar (columnas y orden), leer, renombrar, duplicar, borrar, `404` y `422` |
| 2 | Integridad y reglas de conexión | `test_flow_rules.py`: 21 casos compartidos (`rules.cases.json`), estructura y rangos (22 casos), errores de conexión con su ruta, ciclos, límites, todos los errores a la vez y propiedad de 500 grafos; `rules.test.ts` con los mismos casos |
| 3 | Configuración, catálogo y estimación | Rangos en `test_flow_rules.py`; `test_catalog_lists_the_configuration_options`; estimación comparada con `run_query` y `422` (5 casos) |
| 4 | Validación | 11 códigos en `test_flow_rules.py`; `test_validate_returns_the_issues_of_an_unsaved_graph` |
| 5 | Ejecución simulada | `test_flow_engine.py` (43: métodos, semilla, estratos a ±1 y restos mayores, primeros N, prompt determinista y coherente, JSON y outputs); `test_flow_runs.py` (flujo completo, `422`, `409`, `PromptRunner` sustituido) |
| 6 | Progreso | `test_progress_is_observable_step_by_step_and_never_goes_back`, lecturas desde otro hilo, muestra vacía, prompt que falla, fallo inesperado; uvicorn real |
| 7 | Historial | `test_history_lists_runs_newest_first_with_their_summary`, grafo de una ejecución pasada inmutable, borrado en cascada |
| 8 | Ida y vuelta | `test_saving_and_reading_returns_exactly_the_same_json`, `test_temporary_keys_become_node_ids_and_edges_are_rewritten`; front: `graph.test.ts` y «al recargar reconstruye exactamente lo guardado» |
| 9 | Permisos | Rol con solo `flows:view` (lecturas `200`, 5 escrituras y ejecutar `403`), `viewer` sin acceso, `schema`/`suggest` con `flows:view`; recorrido de rutas del OpenAPI en `test_auth.py` |
| 10 | Listado en el front | `FlowsPage.test.tsx` (10) |
| 11 | Editor drag & drop | `FlowEditorPage.test.tsx` (soltar, botón, Supr, `Controls` y `MiniMap`); Chrome: arrastre, mover, zoom (control y rueda) y desplazamiento |
| 12 | Paneles | `NodePanels.test.tsx` (14) |
| 13 | Conexión rechazada con aviso | `rules.test.ts`; «conecta desde el panel aplicando las reglas…»; Chrome con el ratón («Un Sampling solo puede conectarse a un Prompt.», «El Prompt ya tiene una entrada…») |
| 14 | Validar y Ejecutar | «Validar lista los errores, marca sus nodos…», revalidación, «Ejecutar guarda…», «un flujo no válido no se ejecuta», `409` |
| 15 | Guardar, recargar y avisar | Tests de guardar, recargar, `useBlocker` y `beforeunload`; Chrome: recarga idéntica |
| 16 | Vista de ejecución | `RunPage.test.tsx`: polling hasta el final y sin peticiones después, insignias y procesados |
| 17 | Resultados | Pestañas en orden y con flechas, métrica con gráfico y tabla, tabla navegable y «Volver a la ejecución» |
| 18 | Historial en el front | «lista fecha, usuario… y reabre una ejecución», vacío y enlace desde el editor |
| 19 | Solo lectura | Listado, editor, panel y lienzo de la ejecución con `USERS.lector` |
| 20 | CI | `./scripts/ci.sh` con código 0 |
| 21 | Chrome | Recorrido completo de T9 (ver el [plan](plan.md#progreso)) |

## Fundamentación

| Decisión | Fuente |
|---|---|
| Ejecución en segundo plano con `BackgroundTasks` | [FastAPI · Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) |
| `PromptRunner` sustituible en los tests | [FastAPI · Testing dependencies with overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/) |
| Unión discriminada de nodos y `extra="forbid"` | [Pydantic · Discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions) |
| Lienzo, `isValidConnection`, `onConnectEnd`, `screenToFlowPosition` | [React Flow · API reference](https://reactflow.dev/api-reference/react-flow), verificado contra los tipos instalados de `@xyflow/react` 12.12.0 |
| Mock de React Flow en jsdom (con `contentRect` añadido) | [React Flow · Testing](https://reactflow.dev/learn/advanced-use/testing) y `@xyflow/system/dist/esm/index.mjs` |
| Arrastre HTML5 desde la paleta | [MDN · HTML Drag and Drop API](https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API) |
| Aviso de cambios sin guardar | [React Router · useBlocker](https://reactrouter.com/api/hooks/useBlocker) y [MDN · beforeunload](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event) |
| Polling que se detiene al terminar | [TanStack Query · refetchInterval](https://tanstack.com/query/latest/docs/framework/react/reference/useQuery) |
| Pestañas accesibles | [WAI-ARIA APG · Tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) |
| Reparto por restos mayores | [Método de Hamilton (restos mayores)](https://en.wikipedia.org/wiki/Largest_remainder_method) |

## Registro de duda

| Afirmación | Duda | Reconciliación | Conclusión |
|---|---|---|---|
| Un grafo no válido nunca da `500` | ¿Solo con los 500 grafos de la propiedad? | Fuzzing de 9.000 peticiones con tipos arbitrarios: 170 `500` por un `type` no hashable | **Bug corregido** con regresión; 0 `500` |
| Los tests de flujos prueban el motor | ¿O el dataset con semilla 42 y fecha 2026-09-27? | Con otra fecha fallaban 22 por fechas absolutas | **Fixtures relativos**; 190/190 con 4 combinaciones |
| El progreso es visible | `TestClient` ejecuta las tareas antes de responder | Gancho por paso, hilo real y uvicorn | Se cumple |
| Nunca hay dos ejecuciones a la vez del mismo flujo | ¿Carrera entre comprobar y crear? | Test determinista con 8 hilos y ventana ensanchada | Se cumple |
| El JSON vuelve idéntico | ¿Con otro orden de claves en la respuesta? | `sameJson` independiente del orden; test con claves invertidas | Se cumple |
| Borrar un nodo no deja conexiones | React Flow no pinta conexiones huérfanas | Test sobre el JSON guardado | Se cumple |
| La carga inicial no crece | React Flow ocupa unos 176 kB | Rutas diferidas: la carga inicial sigue en unos 448 kB | Se cumple |
| El lienzo se comporta en un navegador | jsdom no tiene layout | Chrome: tres fallos encontrados y corregidos (`fitView`, estilo del `output`, nodos apilados) | Se cumple tras corregirlos |
| Los resultados del prompt son coherentes | ¿Solo en los ejemplos? | 120 conversaciones: etiquetas de main topic y sentimiento siempre coinciden; resolución sin confusiones | Se cumple (simulado; ver ADR-006) |

## Bugs encontrados

| Bug | Causa raíz | Regresión |
|---|---|---|
| `500` con `type` no hashable | `raw.get("type") in NODE_TYPES` con una lista | `test_non_string_node_types_are_integrity_errors_not_crashes` (5) y `test_non_string_ids_and_edge_endpoints_are_integrity_errors` |
| Ejecutar con cambios pedía confirmar la salida (T6) | `navigate` antes del render con el estado guardado | «Ejecutar guarda los cambios pendientes y abre la ejecución» |
| Nodos superpuestos al soltar en un lienzo vacío (T6) | `fitView` con el primer nodo | Verificación en Chrome; `fitView` solo con nodos al abrir |
| Marco del nodo `output` (T6) | Estilo del nodo integrado de React Flow | Verificación en Chrome; reseteo en `.insight-flow` |
| Nodos añadidos con botón apilados (T7) | Desplazamiento fijo de 20 px | `freePosition` con test |
| Error de tipos oculto en el build (T8) | Salida filtrada con `grep` | Build por código de salida |

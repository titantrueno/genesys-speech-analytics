# FE004 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-09-28. Siguiente paso: `/build`, en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md) | `1FL`, `1ND` y `1RN` reservados para FE004 y ya en `PREFIXES` | Pasan a activos (T9). Los nodos del editor usan claves temporales y el backend asigna el `1ND` al guardar (T2), porque solo `app/ids.py` genera identificadores. |
| [ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md) y `app/auth.py` | `flows:view` y `flows:edit` ya existen; `analista`, `supervisor` y `admin` tienen los dos; `viewer`, ninguno | Sin cambios en la matriz. La solo lectura se prueba con un rol creado en el test (T2, T8). |
| [ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md) | Front con React Router, TanStack Query y Recharts; backend sin dependencias pesadas | Se añade `@xyflow/react` (MIT) al front (T6). El backend no añade dependencias: la ejecución usa `BackgroundTasks` de FastAPI y `threading`. |
| [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md) | Describe dataset, motor de consultas y búsqueda | Se amplía con los flujos (T9); no se crea una entrada nueva. |
| [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md) | 15 lecciones | Se aplican: rutas vía OpenAPI (T2), tres estados de datos remotos (T5–T8), gráfico con vista de tabla (T8), fecha de referencia distinta de hoy (T3), test de propiedad para lo que convierte entrada libre en estructura (T1, validador de grafos), copias antes de mutar y verificación en navegador (T6–T9). |
| `backend/app/query/model.py`, `engine.py` | `parse_query` y `run_query` | El Sampling guarda una consulta de FE002 y el backend la valida y evalúa con ellos (T1, T3). |
| `backend/app/routers/query.py` | Router entero con `explorer:use` | `schema` y `suggest` pasan a aceptar `explorer:use` o `flows:view` (T2). |
| `backend/app/query/saved.py` | Store en memoria con `reset_*` para los tests | Mismo patrón para flujos y ejecuciones (T2, T4). |
| `backend/tests/test_auth.py` | Recorre las rutas del OpenAPI | Cubre automáticamente auth y permisos de las rutas nuevas. |
| `frontend/src/explorer/GroupEditor.tsx`, `queryModel.ts`, `api.ts` | Constructor de condiciones desacoplado de la URL | El panel de Sampling lo reutiliza tal cual con su propio estado (T7). |
| `frontend/src/conversations/useRowNavigation.ts` y `BackLink` | Fila navegable; «Volver a» por `pathname` exacto | La tabla de resultados reutiliza el hook; `BackLink` admite rutas de ejecución con parámetros (T8). |
| `frontend/src/dashboards/ChartCard.tsx` | Gráfico con «Ver tabla» | La métrica agregada lo reutiliza (T8). |
| `frontend/src/router.tsx` | `/flujos` muestra `ComingSoonPage` | Se sustituye por el listado, el editor y la ejecución (T5, T6, T8). |

## Decisiones de diseño

- **Dos niveles de validación:**
  - la **integridad** (tipos, identificadores, rangos y reglas de conexión) se exige siempre al guardar, así que un borrador incompleto se puede guardar pero nunca un grafo imposible;
  - la **completitud** (criterio 4) solo bloquea la ejecución.
- **Reglas compartidas:** las reglas de conexión deben responder al instante en el lienzo, así que existen en Python y en TypeScript. `frontend/src/flows/rules.cases.json` contiene los casos de conexión (grafo, conexión propuesta y código esperado) y lo ejecutan `backend/tests/test_flow_rules.py` y `frontend/src/flows/rules.test.ts`, para que las dos implementaciones no diverjan.
- **Validación en el backend:** «Validar» envía el grafo actual, aunque no esté guardado, a `POST /api/flows/validate`. Así la completitud (que incluye validar la consulta de FE002) tiene una sola implementación.
- **Ejecución:** `BackgroundTasks` ejecuta el flujo sobre una copia del grafo guardado. El ritmo lo marca un retardo por elemento configurable (`FLOW_RUN_STEP_DELAY_MS`, 0 en los tests), para que el progreso sea visible en la demo. El estado se lee siempre como copia, bajo un cerrojo.
- **Vista de ejecución:** al ejecutar, el editor navega a `/flujos/{id}/ejecuciones/{runId}`. Esa misma vista sirve para el progreso, los resultados y reabrir una ejecución del historial.

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Modelo del flujo, integridad, reglas de conexión y validación | — | 2, 3 (configuración), 4 |
| T2 | Store y API de flujos: CRUD, catálogo, estimación, validación y permisos | T1 | 1, 3 (catálogo y estimación), 8, 9 |
| T3 | Motor: sampling por método, prompt simulado y outputs | T1 | 5 |
| T4 | Ejecuciones: API, segundo plano, progreso e historial | T2, T3 | 5, 6, 7, 9 |
| T5 | Front: listado de flujos con CRUD | T2 | 10, 19 (listado) |
| T6 | Front: editor con paleta, lienzo, reglas, guardar y validar | T5 | 2, 11, 13, 14, 15 |
| T7 | Front: paneles de configuración por nodo | T6 | 3, 12 |
| T8 | Front: ejecución con progreso, resultados, historial y solo lectura | T4, T7 | 16, 17, 18, 19 |
| T9 | Conocimiento, CI y verificación en Chrome | T1–T8 | 20, 21 y conocimiento afectado |

### T1 — Modelo, integridad y validación

- **Qué:**
  - `app/flows/model.py`: modelos Pydantic del grafo (`version`, `nodes`, `edges`) y de la configuración de cada tipo, con los rangos del criterio 3 y `extra="forbid"`;
  - `app/flows/rules.py`:
    - `check_integrity(graph)`, que devuelve **todos** los errores de integridad con su ruta y nodo;
    - `can_connect(graph, source, target)`, con el motivo del rechazo;
    - `validate(graph)` con los códigos del criterio 4;
  - `frontend/src/flows/rules.cases.json` con los casos compartidos.
- **Hecho cuando:** hay tests para:
  - cada regla de conexión (pares admitidos y rechazados, entradas máximas, duplicados, bucle y ciclo en una cadena de prompts);
  - cada código de validación, sobre grafos mínimos;
  - los rangos de configuración (tamaño, temperatura, etiquetas y campos del esquema) y la consulta de FE002 validada con `parse_query`;
  - un test de propiedad con semilla fija sobre 500 grafos aleatorios (tipos, conexiones y configuraciones arbitrarias): nunca lanza una excepción, todo grafo que pasa la integridad es acíclico y un grafo que `validate` da por válido tiene al menos un sampling y un output conectados.

### T2 — API de flujos

- **Qué:**
  - `app/flows/store.py`: flujos en memoria con autor y fechas, y asignación de `1ND` a las claves temporales;
  - `app/routers/flows.py`: CRUD, `duplicate`, `PUT …/graph`, `catalog`, `sampling/estimate` y `validate`, con `flows:view` o `flows:edit` según el criterio 9;
  - `schema` y `suggest` de FE002 abiertos a `flows:view`.
- **Hecho cuando:** hay tests para:
  - crear, listar (columnas del criterio 1 y orden por última modificación), leer, renombrar, duplicar (nodos nuevos, conexiones reescritas, sin historial) y borrar;
  - `404` para identificadores inexistentes, mal formados o de otro tipo, y `422` para nombres y grafos no válidos (con la lista de errores);
  - la **ida y vuelta**: guardar y leer devuelve el mismo JSON, y las claves temporales pasan a `1ND` con las conexiones reescritas;
  - la estimación comparada con `run_query` sobre el dataset;
  - un rol con solo `flows:view`: `200` en las lecturas y `403` en cada escritura; `schema` y `suggest` accesibles con `flows:view`.

### T3 — Motor de ejecución

- **Qué:**
  - `app/flows/sampling.py`: `aleatorio` con semilla, `estratificado` proporcional (restos mayores) y `primeros_n` por criterio;
  - `app/flows/prompting.py`: interfaz `PromptRunner` y `MockPromptRunner`, determinista y derivado del análisis (texto, etiqueta, JSON);
  - `app/flows/outputs.py`: tabla, métrica e informe.
- **Hecho cuando:** hay tests para:
  - cada método: los filtros se respetan, el tamaño es el mínimo entre el pedido y los disponibles, la misma semilla da la misma muestra y otra semilla una distinta, el reparto estratificado queda a ±1 del proporcional y `primeros_n` coincide con una ordenación independiente;
  - el prompt: determinismo, una etiqueta siempre de la lista y coherente con el main topic o el sentimiento cuando alguna los nombra, JSON con los campos y tipos del esquema y los campos conocidos iguales al análisis, y `{{resultado_anterior}}` en un prompt encadenado;
  - los outputs: la métrica suma el tamaño de la muestra y el 100 % e incluye las etiquetas sin apariciones; el informe incluye tamaño, reparto y sentimiento medio.

### T4 — Ejecuciones

- **Qué:**
  - `app/flows/runs.py`: store de ejecuciones (`1RN`) con cerrojo y el ejecutor por orden topológico, que actualiza el estado y los procesados de cada nodo;
  - rutas `POST/GET /api/flows/{id}/runs` y `GET …/runs/{run_id}`.
- **Hecho cuando:** hay tests para:
  - `202` y el resultado final con los outputs de un flujo con dos prompts en cadena y dos outputs;
  - `422` si la versión guardada no es válida y `409` con una ejecución en curso;
  - estados intermedios observados paso a paso, con procesados que no decrecen;
  - muestra vacía y fallo de un prompt: el nodo y la ejecución acaban en `error` y los dependientes, en `pendiente`;
  - un `PromptRunner` sustituido sin cambiar la API;
  - el historial (orden, usuario, tamaño, duración y estado) y que editar el flujo después no cambia el grafo de la ejecución;
  - `404` de una ejecución de otro flujo y `403` sin `flows:edit` al ejecutar.

### T5 — Listado de flujos

- **Qué:** `flows/api.ts` y `flows/FlowsPage.tsx` en `/flujos`, en lugar de `ComingSoonPage`.
- **Hecho cuando:** hay tests para las columnas, crear (y abrir el editor), duplicar, renombrar, borrar con confirmación, los estados cargando, error y vacío, y un usuario sin `flows:edit` sin acciones.

### T6 — Editor

- **Qué:**
  - `@xyflow/react`;
  - `flows/graph.ts`: conversión JSON ↔ lienzo y claves temporales; `flows/rules.ts`: reglas de conexión, con los casos compartidos;
  - `flows/FlowEditorPage.tsx`: paleta (arrastrar o botón), lienzo con zoom, desplazamiento, `Controls` y `MiniMap`, conexión con `isValidConnection` y aviso del motivo, borrar con Supr, Guardar, Validar (lista y marcas) y aviso de cambios sin guardar.
- **Hecho cuando:** hay tests para:
  - las reglas del front con `rules.cases.json`;
  - la ida y vuelta JSON → lienzo → JSON;
  - soltar un nodo de la paleta (evento `drop`) y añadirlo con el botón;
  - rechazar una conexión no válida con su aviso;
  - guardar (con la respuesta del backend que sustituye las claves temporales) y reconstruir el lienzo al recargar;
  - Validar: la lista, las marcas y seleccionar el nodo al pulsar un error.

  Además, verificación en Chrome del arrastre, la conexión con el ratón, el zoom y el desplazamiento.

### T7 — Paneles de configuración

- **Qué:** `flows/panels/`:
  - **Sampling:** intervalo y `GroupEditor` de FE002, método, criterio, tamaño y estimación con debounce;
  - **Prompt:** plantilla con inserción de variables, modelo, temperatura y formato (etiquetas o esquema);
  - **Output:** tipo, agregación y destino;
  - en todos, la lista de conexiones con «Desconectar» y un selector para conectar con otro nodo que aplica las mismas reglas;
  - botón «Eliminar nodo».
- **Hecho cuando:** hay tests de cada panel (valores en el grafo, estimación con debounce, etiquetas y campos del esquema, inserción de variables), de conectar y desconectar desde el panel y de eliminar el nodo.

### T8 — Ejecución, resultados, historial y solo lectura

- **Qué:**
  - `flows/RunPage.tsx` en `/flujos/{id}/ejecuciones/{runId}`: lienzo de solo lectura con el estado de cada nodo, polling mientras la ejecución no termina y pestañas por output (tabla navegable, `ChartCard` con barras y tabla, e informe);
  - historial en el editor;
  - «Volver a la ejecución» desde el detalle de una conversación;
  - modo solo lectura sin `flows:edit`.
- **Hecho cuando:** hay tests para:
  - el polling hasta el estado final, con temporizadores falsos, y sin más peticiones después;
  - las insignias de estado y los procesados;
  - las tres pestañas de resultados y la fila que navega al detalle con «Volver a la ejecución»;
  - el historial y reabrir una ejecución;
  - el error y `404` de una ejecución;
  - la solo lectura en el editor (sin paleta, lienzo sin arrastrar ni conectar, panel deshabilitado, sin Guardar ni Ejecutar).

### T9 — Conocimiento, CI y navegador

- **Qué:**
  - vault:
    - ADR-006 (prompt simulado detrás de `PromptRunner`);
    - ADR-002 (React Flow);
    - arquitectura, glosario, registro de identificadores (`1FL`, `1ND`, `1RN` activos), patrones de interfaz y lecciones;
  - READMEs con los endpoints y la sección.
- **Hecho cuando:**
  - `python scripts/audit_vault.py` y `./scripts/ci.sh` terminan con código 0;
  - el recorrido del criterio 21 funciona en Chrome contra la API real, sin errores de consola.

## Riesgos del plan

- **React Flow en jsdom (T6–T8):** necesita medidas del DOM. Se sigue la guía de testing de React Flow (stubs de `ResizeObserver`, `DOMMatrixReadOnly` y medidas de los nodos) y la lógica se extrae a funciones puras. Si un comportamiento no se puede probar en jsdom, se verifica en Chrome y queda anotado.
- **Hilos (T4):** la ejecución en segundo plano y las lecturas concurrentes. El estado se copia bajo cerrojo y hay un test de lecturas durante la ejecución.
- **Divergencia de reglas (T1, T6):** mitigada con los casos compartidos.

## Progreso

| Id | Estado | Evidencia |
|---|---|---|
| T1 | Hecha | `tests/test_flow_rules.py`: 88 tests en verde (rojo previo: 87 fallos con stubs; pasaba solo el que comprueba que los casos compartidos cubren todos los códigos); suite de 405. `app/flows/`: `catalog.py` (opciones y límites), `connections.py` (reglas de conexión en tipos primitivos, con `Rejection(code, message)`), `model.py` (Pydantic con `extra="forbid"` y sin `inf`/`nan`; `parse_graph` valida el sobre, cada nodo por separado y las conexiones de forma incremental, y devuelve **todos** los errores con su ruta) y `rules.py` (`can_connect` y `validate` con 11 códigos). `frontend/src/flows/rules.cases.json`: 21 casos de conexión compartidos (7 códigos). Propiedad con semilla fija sobre 500 grafos (la mitad, flujos válidos con mutaciones): sin excepciones, los guardables son acíclicos, sin duplicados, con pares admitidos y una entrada como máximo; los válidos tienen un output y todos sus nodos alcanzables desde un sampling (151 guardables y 72 válidos). Mutaciones detectadas (12 de 12): sin ciclo, sin entrada única, sin duplicadas, `resultado_anterior` sin cadena, prompt sin salida, identificadores repetidos, destinos repetidos, métrica sin etiquetas, una sola etiqueta, límite de nodos, filtros sin validar e `inf` admitido. `ids.py`: constantes `FLOW`, `NODE` y `RUN`. |
| T2 | Hecha | `tests/test_flows_api.py`: 32 tests en verde (rojo previo: 32 fallos con el router sin registrar); suite de 437. `app/flows/store.py`: flujos en memoria con autor y fechas (hora estrictamente creciente, para que el orden por modificación sea estable), `assign_node_ids` (claves temporales → `1ND`, conexiones reescritas; al duplicar, todos los nodos nuevos) y `reset_flow_store` en el fixture `api`. `app/routers/flows.py`: listado (columnas del criterio 1 con `last_run` a `null` hasta T4 y `status` `valido`/`con_errores`), crear, leer, renombrar, `PUT …/graph` (devuelve `id_map`), duplicar («Copia de …» truncado a 80), borrar, `catalog`, `validate` (grafo sin guardar; `422` si no es íntegro) y `sampling/estimate` (igual a `run_query`; tamaño efectivo = mínimo). Ida y vuelta: con identificadores `1ND` el JSON vuelve idéntico; con claves temporales, vuelve con `1ND` y conexiones reescritas, y guardarlo otra vez no cambia nada. Un grafo imposible devuelve `422` con la ruta y conserva la versión anterior. `404` para inexistente, mal formado y `1RN`. Permisos: un rol con solo `flows:view` lee todo (incluidos `schema` y `suggest` de FE002) y recibe `403` en las 5 escrituras y en `POST /api/query/run`; `viewer` no ve los flujos. El router de FE002 pasa a declarar el permiso por ruta. Mutaciones detectadas (7 de 7): `schema` sin `flows:view`, guardar con `flows:view`, duplicar sin renovar nodos, `exclude_none=False`, conexiones sin reescribir, tamaño efectivo sin mínimo y guardar sin actualizar la fecha. |
| T3 | Pendiente | |
| T4 | Pendiente | |
| T5 | Pendiente | |
| T6 | Pendiente | |
| T7 | Pendiente | |
| T8 | Pendiente | |
| T9 | Pendiente | |

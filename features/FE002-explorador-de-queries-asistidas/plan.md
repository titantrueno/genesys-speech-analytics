# FE002 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-09-27. Siguiente paso: `/build`, en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md) | `1QY` reservado | Se activa en T4, con test de sincronía con el vault. |
| [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md) | Describe los filtros de FE001 | Se amplía con el motor de consultas (T9). |
| [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md) | 8 lecciones | Se aplican: estados de error (T7), fecha de referencia del catálogo para el intervalo (T5), comparar con un cálculo independiente (T2) y tablas enlazables en lugar de clics en gráficos (T7). |
| [Patrones de interfaz](../../vault/ingenieria/patrones-de-interfaz.md) | Fila navegable | Se reutiliza en los resultados (T7). |
| `backend/app/services/kpis.py` | `compute_kpis(convs, followups)` | Se reutiliza tal cual para los KPIs del subconjunto. |
| `backend/app/routers/conversations.py` | `_list_item` y orden del listado | Se extraen a `services/listing.py` para compartirlos con `/api/query/run` (T2). |
| `frontend/src/conversations/ConversationsPage.tsx` | Tabla, cabeceras de orden, fila y paginación dentro de la página | Se extraen a `ConversationTable` y `Pagination` reutilizables (T7). |
| `ConversationDetailPage.tsx` · `BackLink` | Solo vuelve a `/conversaciones` | Se generaliza a cualquier `state.from` (volver al explorador) (T7). |
| `KpiTile` | Exige `href` (drill-down) | `href` pasa a ser opcional; en el explorador las tarjetas no navegan (T7). |

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Modelo de consulta, esquema de campos y validación | — | 1, 2 (validación) |
| T2 | Motor de evaluación y `POST /api/query/run` | T1 | 2, 3, 8 |
| T3 | Sugerencias por campo | T1 | 4 |
| T4 | Consultas guardadas por usuario (`1QY`) | T1 | 6, 7 |
| T5 | Intérprete de lenguaje natural mock | T1 | 5 |
| T6 | Front: estado de la consulta, URL, texto legible y ejecución en tiempo real | T2 | 11, 13 |
| T7 | Front: constructor visual y panel de resultados | T3, T6 | 9, 10, 14, 16 |
| T8 | Front: lenguaje natural y consultas guardadas | T4, T5, T7 | 12, 15 |
| T9 | Conocimiento, CI y verificación en navegador | T1–T8 | 17, 18 y conocimiento afectado |

### T1 — Modelo de consulta, esquema y validación

- **Qué:**
  - `app/query/model.py`: modelos Pydantic de `Condition` y `Group` recursivos, `Query` con `from`/`to` y validación de profundidad (≤ 2 niveles);
  - `app/query/fields.py`: registro de campos (tipo, etiqueta, operadores, extractor de valor y valores posibles);
  - `GET /api/query/schema` con el permiso `explorer:use`.
- **Hecho cuando:** hay tests para:
  - el esquema: cada campo de la spec con su tipo y operadores, y cola y agente con `{id, name}`;
  - la validación: campo desconocido, operador no válido para el tipo, valor de tipo incorrecto, identificador de cola que no es `1QU`, `between` sin dos valores, profundidad 3 y `from > to`, cada uno con `422` y el índice o ruta de la condición en el detalle.

### T2 — Motor y ejecución

- **Qué:**
  - `app/query/engine.py`: `evaluate(conv, node)` recursivo con normalización de texto (minúsculas y sin tildes);
  - `POST /api/query/run` que devuelve `total`, `kpis` (13, con etiqueta y unidad, sin periodo anterior) e `items` paginados y ordenados;
  - `_list_item` y el orden se extraen a `services/listing.py`, compartidos con el listado.
- **Hecho cuando:**
  - un test por operador de cada tipo compara con un filtrado independiente del dataset;
  - hay tests de `and`/`or` anidados, de la búsqueda de texto limitada a un hablante y del check con `fails`/`not_applicable`;
  - el test cruzado de que una consulta equivalente a filtros de FE001 da el mismo total que `/api/conversations` pasa;
  - responde en menos de 500 ms con 10 condiciones;
  - los tests de FE001 siguen en verde tras la extracción.

### T3 — Sugerencias

- **Qué:** `GET /api/query/suggest?field=&from=&to=` para los campos categóricos: valores presentes con etiqueta y recuento, ordenados.
- **Hecho cuando:**
  - los recuentos coinciden con un cálculo independiente;
  - un campo no categórico o desconocido devuelve `422`;
  - cola y agente devuelven identificadores con su nombre.

### T4 — Consultas guardadas

- **Qué:**
  - `1QY` activo en `app/ids.py` y en el registro del vault;
  - almacén en memoria por propietario;
  - `GET/POST /api/query/saved` y `GET/PATCH/DELETE /api/query/saved/{id}`.
- **Hecho cuando:** hay tests para:
  - crear, listar, obtener, renombrar y borrar;
  - validación de la consulta al guardar (`422`) y nombre vacío (`422`);
  - `404` al acceder a la consulta de otro usuario;
  - identificador válido `1QY`;
  - los tests de recorrido exigen auth y permiso en las rutas nuevas;
  - `viewer` recibe `403`.

### T5 — Intérprete de lenguaje natural

- **Qué:** `app/query/interpreter.py` con reglas y sinónimos:
  - canal, sentimiento, resolución, riesgo, main topics por sus palabras clave;
  - colas y agentes por nombre;
  - «más de N minutos», «CSAT bajo o alto», «sin verificar identidad» y «esta semana / últimos N días» respecto a la fecha de referencia.

  `POST /api/query/interpret` devuelve `{query, unrecognized: [...]}`.
- **Hecho cuando:**
  - un test con al menos 12 frases compara con su consulta esperada;
  - una frase sin nada reconocible devuelve una consulta vacía y el texto en `unrecognized`;
  - la consulta devuelta siempre pasa la validación de T1.

### T6 — Estado, URL y ejecución en tiempo real

- **Qué:**
  - `explorer/queryModel.ts`: tipos, construcción, edición inmutable, texto legible y codificación base64url del JSON en `q`;
  - hook `useExplorerQuery` (URL ↔ estado con debounce de 300 ms);
  - hook `useQueryRun` sobre TanStack Query con `keepPreviousData`.
- **Hecho cuando:** hay tests para:
  - codificar y decodificar sin pérdida y rechazar un `q` corrupto (vuelve a la consulta por defecto con aviso);
  - el texto legible con grupos anidados;
  - el debounce: varias ediciones seguidas dan una sola petición;
  - las **respuestas desordenadas**: una respuesta lenta anterior no sustituye a la actual.

### T7 — Constructor y resultados

- **Qué:**
  - página `/explorador`: intervalo, constructor (añadir y quitar condición o grupo, cambiar Y/O, operadores por tipo, control de valor por tipo con sugerencias y recuento) y panel de resultados;
  - se extraen `ConversationTable` y `Pagination` del listado, `KpiTile.href` pasa a ser opcional y `BackLink` se generaliza.
- **Hecho cuando:** hay tests para:
  - añadir, editar y quitar condiciones y grupos;
  - que solo se ofrecen operadores válidos;
  - las sugerencias con recuento;
  - los resultados (recuento, KPIs y tabla);
  - la fila navegable y volver al explorador con la misma consulta;
  - los estados de carga, error y vacío.

  Además, los tests del listado de FE001 y FE007 siguen en verde tras la extracción.

### T8 — Lenguaje natural y consultas guardadas en la UI

- **Qué:** el campo de frase carga en el constructor la consulta interpretada y muestra aviso de lo no entendido; panel de consultas guardadas (guardar, cargar, renombrar y borrar).
- **Hecho cuando:** hay tests para la frase → condiciones visibles y editables → ejecución, el aviso de partes no entendidas y el ciclo completo de consultas guardadas con la API mockeada.

### T9 — Conocimiento, CI y navegador

- **Qué:**
  - vault: arquitectura (motor, modelo e intérprete), glosario, registro con `1QY` activo y nota de R9 resuelta con el campo de check;
  - README del backend con los endpoints nuevos.
- **Hecho cuando:**
  - `./scripts/ci.sh` termina con código 0;
  - en Chrome contra la API real:
    - construir y editar una consulta;
    - interpretar una frase;
    - guardar y recargar la página, que conserva la consulta;
    - abrir un resultado y volver;
    - el total de una consulta equivalente a filtros de FE001 coincide con el listado;
  - sin errores de consola.

## Riesgos del plan

- **La extracción del listado (T2, T7) toca código entregado:** la cubren los tests existentes de FE001 y FE007, que deben seguir en verde en cada commit.
- **UI del constructor:** es la pieza más grande. Si T7 no cabe en una sesión, se divide en T7a (constructor) y T7b (resultados) sin cambiar los criterios.

## Progreso

| Id | Estado | Evidencia |
|---|---|---|
| T1 | Hecha | `tests/test_query_model.py`: 26 tests en verde (rojo previo: 26 fallos con stub); suite de 134 tests. Esquema con 20 campos (6 checks) y operadores por tipo; validación de campo, operador, valor, lista, número, rango, `between`, identificadores de otro tipo, texto vacío, hablante, booleano, profundidad > 2 y `from > to`, con la ruta de la condición y todos los errores a la vez. `/api/query/schema` protegido por `explorer:use` (los tests de recorrido lo cubren). Los temas secundarios pasan al catálogo (`SECONDARY_TOPICS`), sin cambiar la huella del dataset. |
| T2 | Hecha | `tests/test_query_engine.py`: 42 tests en verde (rojo previo: 42 fallos). Suite de 176 tests. 31 casos por operador comparados con un filtrado independiente (cada caso comprueba que filtra algo y no todo); grupos `and`/`or` anidados; consulta vacía = periodo por defecto; total y KPIs iguales al listado y al resumen de FE001 para una consulta equivalente; paginación y orden idénticos al listado; `422` con rutas; `403` sin `explorer:use`; < 500 ms con 10 condiciones. Mutaciones detectadas: `between` exclusivo y hablante ignorado. Listado y orden extraídos a `services/listing.py`; los tests de FE001 siguen en verde. |
| T3 | Hecha | `tests/test_query_suggest.py`: 10 tests en verde (rojo previo: 10 fallos); suite de 186. Recuentos iguales a un cálculo independiente (main topic, temas secundarios multivalor, colas con identificador y nombre), orden descendente, solo valores presentes en el intervalo, `422` para campos no categóricos o desconocidos y `from > to`. |

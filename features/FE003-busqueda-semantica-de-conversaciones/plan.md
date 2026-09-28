# FE003 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-09-28. Siguiente paso: `/build`, en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| [Decisiones](../../vault/decisiones/Index.md) | ADR-001 a ADR-004 | Se crea ADR-005 (T7). [ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md) mantiene un backend sin dependencias pesadas: TF-IDF y coseno se implementan en Python puro con índice invertido, sin scikit-learn ni numpy. |
| [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md) | Describe dataset, filtros y motor de consultas | La spec original pedía una entrada nueva; ya existe y se amplía con la búsqueda (T7). |
| [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md) | Sin prefijo para búsquedas | Sin cambios: los fragmentos se referencian por `1CO` y turnos. Los filtros de cola aceptan solo `1QU`. |
| [Patrones de interfaz](../../vault/ingenieria/patrones-de-interfaz.md) | Fila navegable dentro de `ConversationTable` | Los resultados son tarjetas, no filas de tabla: la lógica se extrae a un hook reutilizable (T5) y se documenta el enlace a un turno (T7). |
| [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md) | 10 lecciones | Se aplican: test de propiedad para texto libre (T3), respuestas desordenadas (T5), tres estados de datos remotos (T5), `container.scrollTo` para el turno (T6), fecha de referencia distinta de hoy en los tests (T3), rutas vía OpenAPI (T3) y validar con códigos de error antes de cada commit. |
| `backend/app/data/generator.py` | 15 main topics con 2 o 3 guiones; texto común en todas las conversaciones | El diccionario es la pieza de la que depende la calidad (T2). El IDF debe anular saludo, verificación y despedida (T1). |
| `backend/app/data/store.py` | Dataset con `@cache` perezosa | El índice también se cachea y se construye en el `lifespan` de `create_app` (T3). |
| `backend/app/query/fields.py` | `normalize_text` (minúsculas y sin tildes) | Se reutiliza para normalizar corpus y consultas. |
| `backend/app/services/filters.py` | `ConversationFilters` y periodo por defecto | Se reutilizan para intervalo, canal y cola (T3). |
| `backend/app/query/interpreter.py` | Patrones para frases **sobre** un tema | No sirve para paráfrasis de clientes; el diccionario de búsqueda es propio, en `app/search/`. |
| `backend/tests/test_auth.py` | Recorre las rutas del OpenAPI | Cubre automáticamente auth y permisos de las rutas nuevas. |
| `frontend/src/conversations/ConversationDetailPage.tsx` | `selectTurn` con `container.scrollTo` y anillo del turno activo | Se reutiliza para `?turn=N`. `BackLink` se amplía a `/busqueda` (T6). |
| `frontend/src/lib/highlight.tsx` | Resaltado por términos literales | Se reutiliza con los términos que devuelve el backend tal y como aparecen en el fragmento. |
| `frontend/src/explorer/hooks.ts`, `components/MultiSelect.tsx` | Debounce, claves de TanStack Query y selector múltiple | Se reutilizan en el formulario y los filtros (T5). |

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Fragmentación, TF-IDF, coseno e interfaz `SearchEngine` | — | 1 |
| T2 | Diccionario de sinónimos, expansión y relevancia | T1 | 3, 8 |
| T3 | `GET /api/search/semantic` con filtros, umbral y agrupación | T2 | 2, 4, 5, 7, 9 |
| T4 | `GET /api/search/similar/{id}` | T3 | 6, 7 |
| T5 | Front: sección de búsqueda y resultados | T3 | 10, 11, 12, 15 |
| T6 | Front: detalle en el turno, volver y similares | T4, T5 | 13, 14 |
| T7 | Conocimiento, CI y verificación en navegador | T1–T6 | 16, 17 y conocimiento afectado |

### T1 — Motor de búsqueda

- **Qué:**
  - `app/search/engine.py`: protocolo `SearchEngine` (`search(text, candidates, …)`, `similar(conversation_id, k)`), tipos `Fragment` y `Hit`;
  - `app/search/tfidf.py`: implementación en Python puro con:
    - fragmentos de 3 turnos con paso 2 (sin turnos de `sistema`);
    - tokens de palabra normalizados y n-gramas de caracteres de 3 a 5 dentro de cada palabra;
    - TF sublineal, IDF suavizado, vectores normalizados L2 e índice invertido para el producto escalar;
    - vectores por conversación (centroide de sus fragmentos) para los similares.
- **Hecho cuando:** hay tests unitarios sobre un corpus pequeño y sobre el dataset para:
  - los límites de los fragmentos (turno de inicio y de fin, último fragmento incompleto, sin `sistema`);
  - puntuaciones en 0–1, 1 para un fragmento idéntico y 0 sin términos comunes;
  - el orden por puntuación y el desempate estable;
  - la tolerancia a tildes, mayúsculas y variantes morfológicas («bloqueada» encuentra «bloquear»);
  - el **texto común**: una consulta de saludo o despedida no supera la puntuación de una consulta del tema;
  - el tamaño del índice y el tiempo de construcción sobre el dataset, que quedan registrados como evidencia.

### T2 — Diccionario y relevancia

- **Qué:**
  - primero, `tests/search_relevance.py` con al menos 20 consultas etiquetadas y los 8 pares del criterio 3, redactados antes de tocar el diccionario (asunción de la spec);
  - después, `app/search/synonyms.py`: grupos de expresiones equivalentes del dominio (cobrar ↔ cargo, «no he comprado» ↔ «no reconozco», irse a otra entidad ↔ baja, etc.) y expansión de la consulta con peso menor que los términos originales. La expansión devuelve los términos añadidos.
- **Hecho cuando:**
  - los 8 pares encuentran su main topic en el top 5 con el diccionario y no sin él (el test comprueba ambos lados);
  - un test comprueba que ninguna frase de los pares comparte palabras con contenido con los guiones de su main topic;
  - al menos el 80 % de las consultas etiquetadas tiene un resultado de su main topic en el top 5; el porcentaje obtenido queda en la evidencia;
  - todo grupo del diccionario tiene al menos un término que aparece en el corpus (un test lo exige, para evitar sinónimos muertos).

### T3 — Endpoint de búsqueda

- **Qué:**
  - `app/routers/search.py` con `GET /api/search/semantic`, protegido por `search:use`, que depende de `get_search_engine()` (sustituible con `app.dependency_overrides`);
  - filtros con `ConversationFilters` (intervalo, canal y cola), umbral, agrupación y límite;
  - metadatos del resultado reutilizando `services/listing.py` donde encaje;
  - índice construido en el `lifespan` de `create_app`.
- **Hecho cuando:** hay tests para:
  - cada filtro comparado con un filtrado independiente del dataset;
  - `min_score` (ningún resultado por debajo), `group=conversation` (una por conversación, su mejor fragmento) frente a `fragment`, `limit` y total;
  - la forma de cada resultado: metadatos, turnos, términos resaltables que existen literalmente en el texto del fragmento y términos de la expansión;
  - `422` por cada parámetro no válido de la spec;
  - la API con un motor falso vía `dependency_overrides` (criterio 1);
  - que el índice existe tras arrancar la app y antes de la primera búsqueda;
  - la propiedad con semilla fija de 300 textos (sin `500`, puntuaciones en 0–1 y ordenadas);
  - `viewer` recibe `403` y el recorrido de rutas exige auth;
  - menos de 500 ms por consulta del conjunto de relevancia en 90 días.

  Los tests usan una `DATA_REFERENCE_DATE` distinta de hoy.

### T4 — Conversaciones similares

- **Qué:** `GET /api/search/similar/{conversation_id}` sobre los vectores por conversación.
- **Hecho cuando:** hay tests para:
  - 10 resultados ordenados, sin la propia conversación y con los metadatos de T3;
  - que la mayoría de los similares comparte main topic con la de origen (una muestra fija de conversaciones);
  - `404` para un identificador inexistente, mal formado o de otro tipo (`1QU-…`);
  - `403` para `viewer`.

### T5 — Sección de búsqueda

- **Qué:**
  - `search/api.ts` y `search/SearchPage.tsx` en `/busqueda` (sustituye a `ComingSoonPage`), con la búsqueda en la URL (`q`, `from`, `to`, `channel`, `queue`, `min_score`, `group`);
  - formulario, filtros, umbral (control deslizante con debounce) y agrupación;
  - resultados como tarjetas con fragmento resaltado, barra y porcentaje, metadatos y términos de la expansión;
  - la lógica de fila navegable se extrae de `ConversationTable` a un hook `useRowNavigation`, compartido por la tabla y las tarjetas.
- **Hecho cuando:** hay tests para:
  - enviar el formulario (sin petición al escribir) y restaurar la búsqueda desde la URL;
  - el resaltado y la barra de puntuación;
  - el umbral y la agrupación, que relanzan la búsqueda;
  - una respuesta lenta anterior que no sustituye a la actual;
  - los estados inicial, cargando, error y sin resultados;
  - el clic, los modificadores y la selección de texto en las tarjetas, con `state.from` y `?turn=N`.

  Además, los tests de listado, fila navegable y explorador siguen en verde tras la extracción.

### T6 — Detalle en el turno y similares

- **Qué:**
  - `ConversationDetailPage` lee `?turn=N`, llama a `selectTurn` al cargar e ignora valores no válidos o fuera de rango;
  - `BackLink` reconoce `/busqueda` («Volver a la búsqueda»);
  - botón «Buscar conversaciones similares», visible solo con `search:use`, que navega a `/busqueda?similar=<id>`;
  - vista de similares en la sección de búsqueda.
- **Hecho cuando:** hay tests para:
  - desplazamiento con `scrollTo` y anillo en el turno indicado, y `turn` no válido sin error;
  - volver a la búsqueda con la misma URL;
  - el botón visible para `analista` y oculto para `viewer`;
  - la vista de similares: 10 resultados, título con la conversación de origen, abrir un resultado y estados de error y `404`.

### T7 — Conocimiento, CI y navegador

- **Qué:**
  - vault: ADR-005 (con alternativas: embeddings locales, base de datos vectorial y BM25), arquitectura, glosario y patrones de interfaz;
  - READMEs con los endpoints y la sección nueva;
  - `python scripts/audit_vault.py` en verde.
- **Hecho cuando:**
  - `./scripts/ci.sh` termina con código 0;
  - en Chrome contra la API real:
    - buscar «me han cobrado algo que no he comprado» y ver `cargo_no_reconocido` en los primeros resultados con los términos resaltados;
    - subir el umbral y cambiar la agrupación;
    - abrir un resultado en su turno y volver con la búsqueda intacta;
    - buscar similares desde el detalle;
    - sin errores de consola.

## Riesgos del plan

- **Calidad del diccionario (T2):** si el 80 % no se alcanza sin sobreajustar, se amplía el diccionario con expresiones del dominio y no con las frases de test; si aun así no llega, se para y se replantea con el humano en lugar de rebajar el umbral.
- **N-gramas de caracteres (T1):** pueden inflar el índice y el tiempo de consulta. T1 mide ambos antes de construir la API; si hace falta, se descartan los n-gramas de frecuencia documental muy alta.
- **Extracción de la fila navegable (T5):** toca código entregado en FE007; la cubren sus tests, que deben seguir en verde en cada commit.

## Progreso

| Id | Estado | Evidencia |
|---|---|---|
| T1 | Hecha | `tests/test_search_engine.py`: 18 tests en verde (rojo previo: 4 fallos y 14 errores con stubs); suite de 248. Fragmentos de 3 turnos con paso 2 sin `sistema` (límites, ventana final incompleta, conversación solo de sistema, todos los turnos cubiertos en el dataset); puntuación 1 para un fragmento idéntico, 0–1, vacío sin términos comunes, orden con desempate estable; tildes, mayúsculas y flexión («bloqueada» → «bloquear») con puntuaciones idénticas; candidatos; similares sin la propia conversación. **Texto común:** con IDF suavizado por fragmento, una consulta de saludo + «bizum» devolvía `recibos_domiciliaciones` (rojo); se corrige con IDF **por conversación y sin +1**, y 5 consultas del tema dan su main topic en los 5 primeros. Mutaciones detectadas: sin normalizar (tras reforzar el test, que no la detectaba), ventana final y similares sin excluir; `score >= 0` es equivalente. Dataset: 7.152 fragmentos, 2.148 términos de palabra, 14.517 n-gramas, 1,95 M de postings; construcción de unos 2 s, 43 MB tras pasar los postings a `array` (eran 305 MB con tuplas); peor búsqueda de 4 frases: 14,5 ms, similares: 28 ms. Desviación del plan: los similares usan TF-IDF por conversación completa en lugar del centroide de fragmentos (misma interfaz, más simple). |
| T2 | Hecha | `tests/search_relevance.py` (9 pares y 24 consultas etiquetadas, escritos antes del diccionario) y `tests/test_search_relevance.py`: 23 tests en verde (rojo previo: 10 fallos con el diccionario vacío); suite de 271. **Relevancia de base sin diccionario: 20/24 (83 %)**; con él: **23/24 (96 %)** (falla «me interesa pedir un préstamo para comprar un coche»). Los 9 pares encuentran su main topic en el top 5 con el diccionario y ninguno sin él. Al validar los pares salieron tres no válidos: dos ya se encontraban sin diccionario gracias a los n-gramas («duplicada» ≈ «duplicado») y dos compartían palabras con el texto real («Eléctrica del Norte» es un comercio que rellena los guiones y el PIN aparece en cualquier main topic). Se sustituyeron, y el test de solapamiento compara ahora con los turnos reales del dataset en vez de con las plantillas. El ejemplo de la spec «quiero irme a otra entidad» tampoco cumplía el criterio y se cambió. `app/search/synonyms.py`: 33 grupos por concepto del dominio (las expresiones con `*` solo disparan el grupo) y todos alcanzan el corpus; los términos añadidos pesan `EXPANSION_WEIGHT = 0,5` y `SearchEngine.expansions()` los expone. La mutación `EXPANSION_WEIGHT = 0` rompe los 9 pares. La búsqueda más lenta de las 33 frases tarda 19 ms. Los tests de T1 del modelo vectorial usan un motor sin expansión, porque con ella una consulta idéntica ya no puntúa 1. |
| T3 | Hecha | `tests/test_search_api.py`: 32 tests en verde (rojo previo: 31 fallos; el que pasaba comprueba que la fecha de referencia no es hoy); suite de 303. `GET /api/search/semantic` con `search:use`: forma del resultado (turnos sin `sistema` con índice, metadatos de `list_item`, `1CO`), términos de la expansión, resaltado literal en el fragmento (con la expansión y la flexión por los 5 primeros caracteres), orden y redondeo a 4 decimales; agrupación por conversación igual al mejor fragmento; umbral sobre la puntuación mostrada; total antes de `limit`; límite de 20 por defecto; 4 combinaciones de filtros iguales a un filtrado independiente y periodo por defecto de 30 días; 14 casos de `422` (incluidos solo espacios, `nan`, `1AG` en `queue` y nombre de cola); `403` para `viewer` (y el recorrido de rutas por OpenAPI cubre auth y permiso); motor falso vía `dependency_overrides`; índice construido en el `lifespan`; propiedad de 300 textos con semilla fija (vocabulario del dominio y caracteres arbitrarios, emojis y metacaracteres de regex): sin `500`, puntuaciones en 0–1 y ordenadas. Mutaciones detectadas: sin agrupar, sin umbral, sin filtros, sin índice al arrancar, resaltado sin expansión y sin validar blancos. Arranque con índice: 2,3 s; API sobre 90 días con las 33 frases: mediana de 12 ms y peor de 40 ms. La tokenización pasa a `app/search/text.py`, compartida por el motor y el resaltado, para no acoplar la API al TF-IDF. Observación para T7: con «me han cobrado algo que no he comprado», el primer resultado es de `comisiones` y los de `cargo_no_reconocido` aparecen dentro del top 5, que es lo que exige el criterio 3. |
| T4 | Hecha | `tests/test_search_similar.py`: 8 tests en verde (rojo previo: 5 fallos; los 3 de `404` pasaban solo porque la ruta no existía); suite de 311. `GET /api/search/similar/{id}`: 10 vecinos sin la propia conversación, sin repetir, ordenados, con puntuación en 0–1 redondeada y los metadatos de `list_item`; identificador en minúsculas aceptado; `404` para inexistente, mal formado y `1QU`; motor inyectado vía `dependency_overrides` (con `k = 10`); `403` para `viewer`. Calidad medida antes de fijar el test: en 40 conversaciones de muestra, 10 de 10 vecinos comparten main topic (esperable con guiones plantillados); el test exige al menos 8 de 10 en 20 conversaciones. |
| T5 | Hecha | `search/SearchPage.test.tsx` y `search/api.test.tsx`: 19 tests en verde (rojo previo: módulos inexistentes); suite de front de 128, tipos, lint y build limpios. Sección `/busqueda`: búsqueda al enviar (escribir no llama a la API; una consulta en blanco no se envía), consulta, filtros, umbral y agrupación en la URL y restaurados al cargar, intervalo por defecto calculado con la fecha de referencia del catálogo, canal, cola e intervalo relanzan la búsqueda, umbral con debounce de 300 ms, agrupación, tarjetas con resaltado (`<mark>`), barra `meter` y porcentaje, metadatos y términos de la expansión, estados inicial, buscando, error (formulario usable) y sin resultados; respuesta lenta anterior que no sustituye a la actual. Tarjeta navegable a `/conversaciones/{id}?turn=N` con `state.from`, un único enlace, Ctrl/Cmd+clic, clic central y selección de texto. `useRowNavigation` extraído de `ConversationTable` (los 73 tests de listado, fila y explorador siguen en verde). Mutaciones detectadas: búsqueda sin consulta, navegar con selección, enlace sin turno y umbral sin debounce (tras endurecer el test, que no la detectaba). Lint: un aviso `set-state-in-effect` corregido con el patrón de FE002 (sincronizar el borrador durante el render). Bundle principal: de 397 a 434 kB. **Chrome contra la API real** (Playwright con el Chrome instalado): «me han cobrado algo que no he comprado» → 326 conversaciones con los 5 primeros de «Cargo no reconocido», expansión visible y resaltado; «Todos los fragmentos» y umbral del 20 % en la URL (34 fragmentos); abrir un resultado → `?turn=17`; volver restaura la URL exacta; sin errores de consola. **Hallazgo de calidad (pendiente de decisión):** el mejor fragmento suele ser la despedida plantillada «Resumiendo, hemos revisado su consulta sobre cargo no reconocido…», porque con el IDF de T1 el texto común pesa cero y ese fragmento queda concentrado en el tema. La normalización con pivote solo lo reduce de 58 a 41 de 165 fragmentos del top 5 y pierde un par del criterio 3, así que no se aplica. Además, las mejores puntuaciones reales están entre 0,25 y 0,76, así que un umbral del 40 % deja sin resultados muchas consultas. |
| T6 | Pendiente | — |
| T7 | Pendiente | — |

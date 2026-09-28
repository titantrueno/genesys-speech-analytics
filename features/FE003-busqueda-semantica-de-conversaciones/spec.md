# FE003 — Búsqueda semántica de conversaciones

> Estado: **aprobada** el 2026-09-28 (revisada tras la entrega de `v0.2.0`). Depende de FE001, FE007 y FE008.

## Objetivo

Encontrar conversaciones por significado y no solo por palabras exactas, llegando directamente al fragmento relevante.

## Conceptos

- **Fragmento:** ventana de turnos consecutivos de una conversación (cliente, agente y bot; los turnos de `sistema` no se indexan). Se identifica por la conversación (`1CO-…`) y su turno de inicio y de fin. No es una entidad, así que no lleva prefijo propio (ver [registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md), «Límites y excepciones»).
- **Puntuación de similitud:** similitud coseno entre la consulta expandida y el fragmento, en el rango 0–1.
- **Expansión de consulta:** términos añadidos a la consulta desde un diccionario de sinónimos y expresiones del dominio bancario.

## Criterios de aceptación

### Backend

1. El backend indexa por fragmentos con una representación vectorial ligera (TF-IDF de palabras y n-gramas de caracteres, sin tildes ni mayúsculas) y similitud coseno. El motor implementa una interfaz `SearchEngine` (indexar, buscar, similares) y la API solo depende de esa interfaz; un test sustituye el motor por uno falso sin cambiar la API.
2. El índice se construye al arrancar la API (evento de arranque), no en la primera búsqueda, y no se añaden dependencias nuevas al backend.
3. Un diccionario de sinónimos y expresiones del dominio amplía la consulta. Hay un test con **al menos 8 pares** frase → main topic en los que la frase no comparte ninguna palabra con contenido con los guiones de ese main topic: con el diccionario, el main topic esperado aparece en el top 5, y sin él, no. Por ejemplo:
   - «me han cobrado algo que no he comprado» → `cargo_no_reconocido` («cargo que no reconozco»);
   - «quiero irme a otra entidad» → `baja_cancelacion` («me voy a otro banco»).
4. `GET /api/search/semantic` acepta:
   - `q`: texto de 1 a 500 caracteres;
   - `from` y `to`: por defecto, el periodo por defecto de la plataforma (30 días hasta la fecha de referencia);
   - `channel` y `queue` (uno o varios identificadores `1QU`), con la misma semántica que los filtros de FE001;
   - `min_score`: entre 0 y 1, 0 por defecto;
   - `group`: `conversation` (mejor fragmento de cada conversación, por defecto) o `fragment` (todos los fragmentos);
   - `limit`: entre 1 y 100, 20 por defecto.

   Devuelve los resultados ordenados por puntuación descendente y el total antes de `limit`. Cada resultado incluye el identificador de la conversación, el texto del fragmento por turnos (hablante y texto), el turno de inicio y de fin, la puntuación, los términos que coinciden tal y como aparecen en el fragmento (para resaltarlos) y los metadatos: fecha, canal, cola, main topic con su etiqueta, summary y sentimiento. La respuesta incluye además los términos añadidos por la expansión.
5. Parámetros no válidos (texto vacío o largo, `from > to`, `min_score` fuera de rango, `group` desconocido o identificador de cola de otro tipo) devuelven `422`. Un test de propiedad con semilla fija y al menos 300 textos aleatorios del vocabulario del dominio y de caracteres arbitrarios no produce ningún `500`, y siempre devuelve puntuaciones en 0–1 y ordenadas.
6. `GET /api/search/similar/{conversation_id}` devuelve las **10** conversaciones más cercanas de todo el dataset, excluida ella misma, con puntuación y los mismos metadatos. Un identificador inexistente, mal formado o de otro tipo devuelve `404`.
7. Las dos rutas exigen el permiso `search:use`: `viewer` recibe `403`, y los tests que recorren las rutas de la API lo verifican automáticamente.
8. **Relevancia:** en un conjunto de **al menos 20 consultas etiquetadas** con su main topic, redactadas como las diría un cliente, al menos el **80 %** tiene un resultado de ese main topic en el top 5.
9. **Rendimiento:** con el índice ya construido, cada consulta del conjunto de relevancia responde en menos de **500 ms** sobre el dataset completo (90 días).

### Front

10. La sección **Búsqueda semántica** (`/busqueda`) tiene un campo de consulta en lenguaje natural y filtros de intervalo, canal y cola. La búsqueda se lanza al enviar el formulario. La consulta, los filtros, el umbral y la agrupación viven en la URL, de modo que recargar, compartir o volver desde el detalle reproduce la misma búsqueda.
11. Cada resultado muestra el fragmento con los términos coincidentes resaltados, la puntuación como barra y porcentaje, y los metadatos (fecha, canal, cola, main topic, summary y sentimiento). La respuesta indica también qué términos ha añadido la expansión.
12. Un control de umbral mínimo de puntuación filtra los resultados, y un selector permite agrupar por conversación (mejor fragmento) o ver todos los fragmentos. Ambos vuelven a lanzar la búsqueda, y una respuesta antigua nunca sustituye a una más reciente (test con respuestas desordenadas).
13. Al pulsar un resultado se abre el detalle tipo chat de FE001 en `/conversaciones/{id}?turn=N`, desplazado y resaltado en el turno de inicio del fragmento. Un `turn` no válido o fuera de rango se ignora sin error. Desde ahí, «Volver a la búsqueda» restaura la búsqueda. El resultado sigue el patrón de fila navegable (Ctrl/Cmd+clic y clic central abren una pestaña nueva; no se navega si hay texto seleccionado).
14. En el detalle de una conversación, el botón «Buscar conversaciones similares» (solo visible con el permiso `search:use`) abre en la sección de búsqueda las 10 conversaciones más cercanas, excluida ella misma.
15. Estados: cargando, error de la API (aviso sin bloquear el formulario), sin resultados (sugerencia de bajar el umbral o ampliar el intervalo) y estado inicial sin consulta.

### Calidad

16. `./scripts/ci.sh` en verde.
17. Verificación en Chrome contra la API real: buscar una frase del par del criterio 3, ajustar el umbral y la agrupación, abrir un resultado en su turno, volver, y buscar similares desde el detalle, sin errores de consola.

## Conocimiento afectado

- [Decisiones](../../vault/decisiones/Index.md): crear **ADR-005** (búsqueda vectorial ligera en memoria, sustituible por embeddings reales detrás de `SearchEngine`).
- [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): añadir el índice por fragmentos, la interfaz `SearchEngine`, el diccionario de sinónimos, la construcción al arrancar y el enlace al turno del detalle.
- [Glosario](../../vault/glosario/terminos-del-harness.md): añadir «búsqueda semántica», «fragmento», «puntuación de similitud» y «expansión de consulta».
- [Patrones de interfaz](../../vault/ingenieria/patrones-de-interfaz.md): los resultados reutilizan la fila navegable; añadir el enlace profundo a un turno (`?turn=N`).
- [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md): revisar al planificar (estados de error, respuestas desordenadas, `container.scrollTo`, test de propiedad para texto libre, fechas de referencia distintas de hoy).
- [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md): sin cambios; los fragmentos no son entidades.

## Alcance

- Índice en memoria construido al arrancar, endpoints de búsqueda y de conversaciones similares.
- Sección de búsqueda con resultados, enlace al turno del detalle y botón de similares en el detalle.

## Fuera de alcance

- Modelos de embeddings reales o una base de datos vectorial.
- Búsqueda híbrida con reranking de un LLM.
- Respuestas generativas tipo «pregunta al corpus».
- Búsqueda mientras se escribe, búsquedas guardadas e historial de búsquedas.
- Reindexado incremental: el dataset es estático mientras la API está en marcha.

## Riesgos y asunciones

- **Riesgo:** TF-IDF más sinónimos es una aproximación léxica. La calidad «semántica» depende del diccionario, y para el piloto real habrá que migrar a embeddings (ADR-005). El test sin diccionario del criterio 3 hace visible cuánto aporta.
- **Riesgo:** el dataset tiene solo 2 o 3 guiones por main topic y un texto común (saludo, verificación, despedida) en todas las conversaciones. El IDF debe anular ese texto común; se comprueba con un test de que una consulta de saludo no puntúa por encima de una del tema.
- **Riesgo:** hay que medir el tamaño del índice de n-gramas de caracteres (unos 15.000 turnos). Si penaliza el arranque o el umbral de 500 ms, se limita el rango de n-gramas o se descartan los de frecuencia documental muy alta, sin cambiar la API.
- **Asunción:** las consultas etiquetadas del criterio 8 se redactan antes de ajustar el diccionario, para no sobreajustarlo a ellas.

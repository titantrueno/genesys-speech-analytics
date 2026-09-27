# FE003 — Búsqueda semántica de conversaciones

> Estado: **pendiente de aprobación**. Depende de FE001.

## Objetivo

Encontrar conversaciones por significado y no solo por palabras exactas, llegando directamente al fragmento relevante.

## Criterios de aceptación

1. La sección **Búsqueda semántica** tiene un campo de consulta en lenguaje natural y filtros de intervalo, canal y cola.
2. El backend indexa por fragmentos (ventanas de turnos) con una representación vectorial ligera (TF-IDF de palabras y n-gramas de caracteres) y similitud coseno. El motor implementa una interfaz `SearchEngine` que permite sustituirlo por embeddings reales sin cambiar la API.
3. Un diccionario de sinónimos y expresiones del dominio amplía la consulta, de modo que se encuentran resultados sin coincidencia literal. Hay un test con al menos 8 pares; por ejemplo, «me han cobrado algo que no he comprado» debe recuperar conversaciones con main topic `cargo_no_reconocido` que dicen «cargo que no reconozco», y «quiero irme a otro banco» debe recuperar `baja_cancelacion`.
4. `GET /api/search/semantic` devuelve resultados ordenados por puntuación (0–1). Cada uno incluye id de conversación, fragmento, turno de inicio, puntuación y metadatos (fecha, canal, cola, main topic, summary y sentimiento).
5. La UI muestra el fragmento con los términos relevantes resaltados y la puntuación como barra o porcentaje. Al pulsar un resultado se abre el detalle tipo chat de FE001 desplazado y resaltado en ese turno.
6. Un control de umbral mínimo de puntuación filtra los resultados, y un selector permite agrupar por conversación (mejor fragmento) o ver todos los fragmentos.
7. Desde el detalle de una conversación, «Buscar conversaciones similares» devuelve las 10 conversaciones más cercanas, excluida ella misma.
8. En un test de relevancia sobre un conjunto de consultas etiquetadas, al menos el 80 % de las consultas tiene un resultado relevante en el top 5.
9. Una búsqueda sobre el dataset completo responde en menos de 500 ms en local, con el índice construido al arrancar.

## Conocimiento afectado

- [Decisiones](../../vault/decisiones/Index.md): hay que crear ADR-004 (búsqueda vectorial ligera sustituible por embeddings reales).
- La nueva entrada de arquitectura de la plataforma debe incluir el índice, la interfaz `SearchEngine` y el diccionario de sinónimos.
- [Glosario](../../vault/glosario/terminos-del-harness.md): hay que añadir «búsqueda semántica», «fragmento» y «puntuación de similitud».

## Alcance

- Indexación en memoria al arrancar, endpoint de búsqueda y de conversaciones similares, y pantalla de búsqueda con resultados.

## Fuera de alcance

- Modelos de embeddings reales o una base de datos vectorial.
- Búsqueda híbrida con reranking de un LLM.
- Respuestas generativas tipo «pregunta al corpus».

## Riesgos y asunciones

- **Riesgo:** TF-IDF más sinónimos es una aproximación léxica. La calidad «semántica» depende del diccionario, y para el piloto real habrá que migrar a embeddings (ADR-004).
- **Asunción:** el dataset mock contiene frases variadas por main topic bancario, de modo que la búsqueda tiene sentido.

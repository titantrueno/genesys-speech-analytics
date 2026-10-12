---
title: "ADR-005 — Búsqueda vectorial ligera sustituible por embeddings"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, busqueda, tf-idf, embeddings, fe003]
created: 2026-09-28
updated: 2026-10-12
---

# ADR-005 — Búsqueda vectorial ligera sustituible por embeddings

## Contexto

FE003 pide encontrar conversaciones por significado y llegar al fragmento relevante. El piloto usa un dataset mock de 1.000 conversaciones con 2 o 3 guiones por main topic, sin base de datos y con un backend deliberadamente ligero ([ADR-002](adr-002-stack-vite-fastapi-mock.md)). No hay todavía un modelo de embeddings aprobado ni infraestructura para servirlo.

## Decisión

- **Motor léxico en memoria, detrás de una interfaz.** La API solo conoce `SearchEngine` (`search`, `expansions` y `similar`, en `backend/app/search/engine.py`) y lo obtiene con `get_search_engine()`, sustituible con `dependency_overrides`. La implementación actual es `TfidfEngine`.
- **Fragmentos:** ventanas de 3 turnos con paso 2, sin turnos de `sistema`.
- **Puntuación:** TF-IDF en Python puro de palabras y n-gramas de caracteres (3–5), con coseno en 0–1 e índice invertido compacto (`array`). El índice se construye al arrancar la API: unos 2,5 s y unos 52 MB retenidos (fragmentos, turnos del cliente y conversaciones), con un pico transitorio de unos 260 MB durante la construcción.
- **IDF por conversación y sin suavizado:** el texto que aparece en casi todas las conversaciones (saludo, verificación, despedida) pesa casi cero.
- **Diccionario de sinónimos del dominio** (`backend/app/search/synonyms.py`): los términos añadidos pesan la mitad que los de la consulta y se devuelven a la UI.
- **Dos puntuaciones por fragmento:**
  - `score` (fragmento completo) ordena, filtra y se muestra;
  - `focus` (80 % lo que dice el cliente, 20 % el fragmento completo) elige el fragmento que representa a cada conversación.
- **Similares:** TF-IDF de la conversación completa.
- **Texto indexado siempre enmascarado** (desde FE005): el índice se construye sobre la copia enmascarada de cada conversación, esté o no activado el interruptor de Privacidad, así que buscar un DNI o un IBAN no encuentra nada ([ADR-007](adr-007-configuracion-global-y-enmascarado.md)). Enmascarar el dataset añade unos 0,11 s al arranque.

## Alternativas

- **Embeddings locales** (un modelo de *sentence embeddings* multilingüe servido por el backend): descartada para el piloto. Añade una dependencia pesada, tiempo de arranque y un modelo por evaluar y aprobar. Es la migración prevista (ver «Consecuencias»).
- **Base de datos vectorial:** descartada. Con unos 7.000 fragmentos en memoria no aporta nada y añade infraestructura.
- **BM25:** descartada por ahora. Mejora la saturación de términos y la longitud, pero sigue siendo léxica y no resuelve la limitación de fondo. Además, el coseno da de forma natural la puntuación en 0–1 que pide la spec.
- **Aplicar el peso del cliente a la puntuación de ranking:** descartada en T5b. Bajaba los pares del criterio 3 de 9/9 a 6/9 y la relevancia de 23/24 a 21/24.

## Consecuencias

### Resultados medidos

- Relevancia en el top 5: **83 % sin diccionario y 96 % con él** (24 consultas etiquetadas). Las consultas y los pares se midieron contra el dataset con semilla 42 y fecha 2026-09-27; desde FE009, `tests/test_search_relevance.py` construye su motor con ese dataset de forma explícita, independiente del entorno.
- Los 9 pares de paráfrasis sin palabras en común con su main topic solo se encuentran gracias al diccionario.
- Latencia por la API, sobre 90 días: mediana de 12 ms y peor caso de 40 ms.

### Limitaciones del enfoque léxico

Son hechos medidos en FE003:

1. **No entiende el significado.** Cualquier «semántica» sale del diccionario: una paráfrasis que el diccionario no cubre no se encuentra, y ampliarlo es trabajo manual que no escala a un vocabulario real.
2. **Puntuaciones absolutas bajas y poco comparables.** La mejor coincidencia de las consultas de prueba está entre 0,25 y 0,76, así que un umbral del 40 % deja muchas búsquedas vacías. La UI lo compensa mostrando la mejor puntuación de cada búsqueda junto al umbral y ofreciendo ajustarlo (criterio 19), pero la escala sigue sin tener un significado estable entre consultas.
3. **Sesgo hacia el texto plantillado.** La despedida «Resumiendo, hemos revisado su consulta sobre {tema}» nombra el main topic, así que parte del acierto por tema viene de esa frase del generador y no de lo que cuenta el cliente. El `focus` del cliente evita mostrarla como fragmento en el 90 % de los casos, pero no cambia el ranking.
4. **Coincidencias literales engañosas.** «Me han cobrado algo que no he comprado» puntúa alto en conversaciones de comisiones porque sus clientes dicen literalmente «cobrado».
5. **Dependencia del dataset mock.** Los resultados se han medido sobre guiones sintéticos con poca variedad. Con transcripciones reales, la calidad puede ser distinta en cualquiera de los dos sentidos.

### Migración a embeddings

Las limitaciones 1, 2 y 4 se resolverían con **embeddings semánticos**: una paráfrasis queda cerca de su significado aunque no comparta palabras, las similitudes de un mismo modelo son comparables entre consultas y el diccionario deja de ser imprescindible. La limitación 3 se reduce indexando sobre todo los turnos del cliente.

La migración no cambia la API: basta con otra implementación de `SearchEngine` que vectorice los mismos fragmentos, y con un índice vectorial si el volumen crece. Los tests de relevancia (`backend/tests/search_relevance.py`) sirven como línea base para comparar ambos motores. Mientras tanto, el diccionario se amplía con expresiones del dominio y no con las frases de test.

## Ampliaciones

- **FE012 (2026-10-12):** hay un índice por origen de datos (`app/search/index.py`). La primera vez que se usa un origen se construye en línea; si cambia su versión, una sola reconstrucción en un hilo sustituye al índice de forma atómica y la búsqueda sigue con el anterior hasta entonces. Mientras reconstruye (unos 2,5 s con 1.000 conversaciones) compite por el procesador y las peticiones tardan más: es un **hecho** medido en los tests de rendimiento, que miden el régimen estable. Se indexan los turnos de cliente, bot y agente, también los mensajes no entregados, siempre con texto enmascarado.

## Fuentes

- [ADR-007](adr-007-configuracion-global-y-enmascarado.md)
- [Spec FE003](../../features/FE003-busqueda-semantica-de-conversaciones/spec.md) (criterios 1, 3, 8, 18, 19 y 20)
- [Plan y evidencia de FE003](../../features/FE003-busqueda-semantica-de-conversaciones/plan.md)
- [Motor](../../backend/app/search/tfidf.py) y [diccionario](../../backend/app/search/synonyms.py)
- [Conjunto de relevancia](../../backend/tests/search_relevance.py)

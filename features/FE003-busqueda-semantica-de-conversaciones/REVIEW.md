# FE003 — Revisión

> Fase `/review`. Fecha: 2026-09-28. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Siguiente paso: `/ship`.

## Resultado

**Aprobado.** No hay hallazgos critical ni major abiertos. Dos hallazgos minor se aceptan de forma consciente: la fragilidad del motor léxico frente al dataset y la búsqueda por DNI hasta FE005. Los dos quedan documentados.

## Tamaño del cambio

El cambio supera las ~100 líneas recomendadas. Se entregó en 11 commits atómicos (spec y plan, T1–T7 con T5b y T5c, y la verificación), cada uno con su evidencia de rojo a verde en el [plan](plan.md#progreso). La verificación comprueba que `VERIFY.md` incluye la auditoría del vault en verde.

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Corrección | minor | Los criterios 3 y 18 dependen del dataset. Con otras semillas, un par sale del top 5 (coincidencia literal «cobrado» en comisiones), otro deja de ser válido y las despedidas llegan al 10,9 %. La relevancia general se mantiene entre el 92 y el 96 % | **Aceptado y documentado** ([VERIFY](VERIFY.md#robustez-frente-al-dataset), limitaciones 4 y 5 de [ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md)). No se ajustan pesos con el conjunto de evaluación. Se resolvería con embeddings |
| R2 | Adherencia a la spec | minor | El criterio 18 cambió de redacción durante T5b: el peso del cliente elige el fragmento representativo y no ordena. La versión aprobada lo aplicaba a la puntuación | **Justificado** con evidencia (el ranking bajaba los pares de 9/9 a 6/9) y anotado en la spec como «Ajuste en T5b». Se comunica al humano en la entrega |
| R3 | Adherencia a la spec | nit | El ejemplo del criterio 3 («quiero irme a otra entidad») se sustituyó porque no cumplía el propio criterio | **Resuelto** en T2, anotado en la spec |
| R4 | Seguridad | minor | Los números se indexan como palabras, así que buscar un DNI ficticio encuentra sus conversaciones. Es la misma información que ya muestra el detalle a quien tiene `conversations:view`, pero la búsqueda lo hace más fácil | **Aceptado hasta FE005** (enmascarado de datos personales). El dataset es ficticio. Se añade a la nota de privacidad de la arquitectura |
| R5 | Seguridad | — | Permiso `search:use` en las dos rutas (`403` para `viewer` y recorrido de rutas del OpenAPI); `q` ≤ 500 caracteres y `limit` ≤ 100; colas validadas como `1QU`; el texto del usuario nunca se compila como regex (el diccionario es constante y se escapa); el front escapa los términos resaltados y no usa `innerHTML`; el identificador de similares va codificado en la URL | Correcto |
| R6 | Rendimiento | minor | La construcción del índice tiene un pico de unos 260 MB y retrasa el arranque unos 2,5 s | **Aceptado** en un mock en memoria de 1.000 conversaciones. Documentado en la arquitectura y el runbook. Con datos reales, el índice se construiría fuera del proceso de la API |
| R7 | Rendimiento | — | Mediana de 12 ms, peor caso de 55 ms, 52 MB retenidos; el bundle principal crece 40 kB (de 397 a 437 kB) | Correcto |
| R8 | Simplicidad | nit | `useSearchState` devuelve `search` (validado) y `raw` (valores de los controles), que repiten parte del análisis de la URL | **Justificado:** los controles deben mostrar filtros aunque aún no haya consulta, y `search` es `null` en ese caso |
| R9 | Simplicidad | — | La navegación de fila se extrajo a `useRowNavigation` en lugar de duplicarla; `best_per_conversation` es la única regla de agrupación, compartida por la API y los tests; la tokenización vive en `app/search/text.py` | Correcto |
| R10 | Corrección | — | Mutaciones detectadas en cada tarea; dos tests débiles endurecidos (tildes y debounce); dos mutaciones equivalentes justificadas (`score >= 0` y el límite del turno) | Correcto |
| R11 | Conocimiento | minor | La documentación decía 45 MB de índice y 397 kB de bundle | **Resuelto en `/test`**: 52 MB y 437 kB |
| R12 | Conocimiento | — | ADR-005 (decisión, alternativas, cinco limitaciones y migración a embeddings), arquitectura, glosario, patrones de interfaz (enlace a un turno), runbook y lecciones 11 a 15 | Correcto |

## Revisión por ejes

- **Corrección:** ver R1 y R10.
  - Filtros comparados con un filtrado independiente.
  - Propiedad de 300 textos en la suite y fuzzing de 3.000 en la verificación.
  - Relevancia medida sin y con diccionario.
- **Adherencia a la spec:** los 20 criterios están trazados en [VERIFY](VERIFY.md#matriz-de-trazabilidad). El fuera de alcance se respeta: sin embeddings, base de datos vectorial, LLM, búsqueda mientras se escribe, búsquedas guardadas ni reindexado. Ver R2 y R3.
- **Simplicidad:** ver R8 y R9.
- **Seguridad:** ver R4 y R5.
- **Rendimiento:** ver R6 y R7.
- **Conocimiento:** ver R11 y R12.

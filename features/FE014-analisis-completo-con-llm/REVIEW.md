# FE014 — Revisión

> Fase `/review` (2026-10-13). Veredicto: **aprobada**. No queda ningún hallazgo critical ni major abierto: el único major (conocimiento desactualizado) está resuelto, y los minor están resueltos o aceptados con su justificación.

## Alcance y evidencia

- **Tamaño:** unas 2.100 líneas añadidas y 260 quitadas en 51 ficheros de código, dos tercios de ellas tests, además de documentación y OpenAPI. Supera con mucho las ~100 líneas que se revisan bien de una vez, pero ya va partido en commits por tarea (T1–T8 y `/test`), y se ha revisado commit a commit: escritura (T1), modelo (T2), validación (T3), lectura (T4), plantilla (T5), front (T6–T7) y documentación (T8). No se reparte más: cada commit es un slice que se puede revertir por separado.
- **Verificación:** [VERIFY.md](VERIFY.md) está al día. La auditoría del vault terminó con código 0, `ci.sh` con código 0, mueren 29 de 29 mutaciones y hay un recorrido en navegador con Gemini.
- **Gate tras las correcciones de esta fase:** `./scripts/ci.sh` termina con código 0:
  - backend: 1.145 tests, también con la otra semilla, y 190 con PostgreSQL;
  - front: 411 tests, lint y build;
  - OpenAPI al día;
  - vault: 55 archivos, 0 errores.

## Hallazgos por eje

### Corrección

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| C1 | minor | Si los temas secundarios activos pasan de `MAX_OPTIONS` (100), `templates.build` lanza `GraphError` sin capturar y «Nuevo flujo» responde `500`. | **Resuelto:** `TemplateError` con el motivo → `422`. Test `test_a_taxonomy_too_large_for_the_template_is_explained`, en rojo antes del arreglo. |
| C2 | minor (aceptado) | En una conversación real sin resultados del LLM, los checks personalizados se evalúan por frases y los base quedan pendientes: `compliance_rate` puede calcularse solo con los personalizados. | **Aceptado:** es lo que pide la spec (criterio 12: «sin él, se mantiene la evaluación actual: los personalizados, por frases; los base, pendientes»). Consta en ADR-007. Con la configuración por defecto (solo checks base) el KPI sigue «pendiente» hasta que un flujo escribe resultados. |
| C3 | nit (aceptado) | El detalle dice «Sentimiento global» sin indicar si viene de Genesys o del LLM. | **Aceptado:** la spec solo fija la precedencia, que está probada. Se puede mostrar el origen en una feature futura. |

### Adherencia a la spec

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| S1 | — | Los 17 criterios tienen evidencia ([VERIFY.md](VERIFY.md), tabla de cobertura). Se respeta el fuera de alcance: sin LLM en la ingesta, sin escritura en sintéticos, sin `sentiment_timeline` del LLM, sin temas ni entidades nuevos y sin `status = completo`. | — |
| S2 | — | Decisiones de diseño tomadas en `/build` y anotadas en el [plan](plan.md): el sentimiento de Genesys manda también con «Sobrescribir»; FCR y recontacto usan las conversaciones con resolución; una lista vacía cuenta como `sin_valor`. Ninguna contradice la spec. | Se someten a la persona usuaria en el resumen de esta fase. |

### Simplicidad

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| P1 | nit | `catalog.TARGET_GROUPS` se definió y no se usa (el front tiene sus etiquetas). | **Resuelto:** eliminado. |
| P2 | nit | Una línea de `routers/flows.py` pasaba de 120 caracteres. | **Resuelto.** |
| P3 | — | La validación de cada destino está en un solo sitio (`app/flows/fields.py`), y las reglas del editor reutilizan `accepts_option`. La forma del valor se comprueba dos veces (API y servicio de ingesta) a propósito: el servicio es el único escritor y no confía en quien lo llama (ADR-008). | Correcto. |

### Seguridad (OWASP Top 10)

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| X1 | minor | **A04/A05 (validación de entrada):** los textos libres del LLM (entidades, palabras clave) no tenían longitud máxima. Una respuesta desbocada o manipulada por la propia transcripción (inyección en el prompt) podía guardar textos enormes. | **Resuelto:** la API rechaza palabras clave de más de 80 caracteres y entidades de más de 200. El servicio de ingesta rechaza textos de más de 4.000 caracteres y listas de más de 100 elementos. Tests `test_free_text_from_the_llm_has_a_maximum_length` y `test_the_ingestion_service_refuses_oversized_values`. |
| X2 | — | **A03 (inyección SQL):** los nombres de columna salen de listas blancas; las claves de `compliance` y `entities` pasan por expresiones regulares (`^compliance:[a-z][a-z0-9_]{1,39}$` y los cuatro tipos de entidad) y van como parámetros dentro de `Jsonb`, nunca concatenadas. Hay un test con `compliance:Saludo; DROP` que da `422`. | Correcto. |
| X3 | — | **A01 (control de acceso):** `/analysis/fields` sigue exigiendo el token interno; las rutas de flujos, los permisos de FE013. No hay rutas nuevas. | Correcto. |
| X4 | — | **Inyección en el prompt:** una transcripción puede intentar dirigir la respuesta, pero los valores quedan acotados por `enum`, rangos y taxonomía. Como mucho falsea un análisis de esa conversación, que queda trazado en `llm_meta`. Las transcripciones salen enmascaradas (ADR-007). | Aceptado, como en FE013. |
| X5 | — | Secretos: las claves no aparecen en el código, los tests, el vault ni los logs; los scripts de comprobación real no imprimen claves ni prompts. | Correcto. |

### Rendimiento

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| R1 | minor (aceptado) | `kpi_pending` y `kpi_bases` recorren las conversaciones una vez por KPI del análisis (7), y `has_compliance` construye un diccionario por conversación. El coste es lineal y sobre resultados ya cacheados. | **Medido:** los tests de rendimiento existentes (cada endpoint por debajo de 500 ms con 1.000 conversaciones) siguen en verde con las dos semillas. Se acepta: no hay coste evidente que optimizar. |
| R2 | — | La escritura sigue siendo una transacción y un `UPDATE` por conversación, en lotes de 100; el esquema de 19 campos cuesta una llamada por conversación (3,2 s para 3 en el recorrido). | Correcto. |

### Conocimiento

| # | Severidad | Hallazgo | Decisión |
|---|---|---|---|
| K1 | **major** | Tres textos decían que, con datos reales, el análisis «aparece como pendiente» o que un flujo solo genera summary y main topic: el `README.md` (introducción y servicio de LLM), [estado operativo](../../vault/operaciones/estado-operativo.md) y el aviso de Configuración → Fuentes de datos. Inducían a pensar que el resto del análisis no se puede generar. | **Resuelto:** los tres actualizados con FE014. |
| K2 | minor | ADR-009 no recogía los límites de longitud nuevos. | **Resuelto.** |
| K3 | — | ADR-009, ADR-007, arquitectura, contrato de la API y runbook del servicio de LLM se actualizaron en T8, con fuentes. La auditoría da 0 errores. La fila de FE014 en la tabla de features del README se añade en `/ship`, como en entregas anteriores. | Correcto. |

## Pendiente fuera de esta feature

- Probar OpenAI y Anthropic contra sus APIs cuando haya claves (hipótesis en ADR-009).
- Mostrar el origen del sentimiento en el detalle (C3), si se pide.

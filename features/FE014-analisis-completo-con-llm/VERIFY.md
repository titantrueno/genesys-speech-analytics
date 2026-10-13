# FE014 — Verificación

> Evidencia del criterio 16 (recorrido en navegador con datos reales y Gemini), recogida en `/build` T8. La fase `/test` amplía este documento con casos límite y mutaciones.

## Recorrido en navegador (2026-10-13)

**Entorno:** `./scripts/dev.sh` en los puertos 18000 (API), 18001 (ingesta), 18002 (LLM) y 15173 (web); PostgreSQL de desarrollo con 13 conversaciones reales del 12 de octubre (11 con transcripción, ninguna con resolución); Gemini con clave y `gemini-3.5-flash-lite`; usuario demo administrador; origen «Real (Genesys Cloud)».

| Paso | Resultado |
|---|---|
| «Nuevo flujo» → plantilla «Generar análisis completo» | El menú ofrece la plantilla. El flujo creado tiene Sampling (aleatorio, 12 filtros «está vacío»), Prompt (Gemini 3.5 Flash-Lite, JSON) y Output «Guardar en campos». |
| Panel del Output | 19 asignaciones; el desplegable de destino agrupa **Análisis (9), Cumplimiento (6) y Entidades (4)**. |
| Muestra de 3, «Guardar» y «Validar» | «13 conversaciones disponibles · muestra de 3»; «El flujo es válido.» |
| «Ejecutar» | Ejecución `ok` en 3,2 s, con 3 de 3 procesadas en cada nodo. |
| Recuentos por campo | Resolución, CSAT, esfuerzo, riesgo, los 6 checks y palabras clave: **3 escritos**. Temas secundarios y las 4 entidades: 2 escritos y 1 sin valor. Summary y main topic: 3 omitidos (ya los tenían de FE013). Sentimiento: 3 omitidos (Genesys ya lo da). **0 rechazados y 0 con error en todos los campos.** |
| Tabla de la ejecución | Cabecera de grupos: Análisis (7), Cumplimiento (6), Temas (2) y Entidades (4). La tabla (2.839 px) se desplaza dentro de su contenedor (1.551 px); la página no desborda (`scrollWidth` igual a `clientWidth`). |
| Detalle de `1CO-EA47555A-…` | Resultado: Escalada, CSAT 2,0 / 5, esfuerzo 3,0 / 5, riesgo Alto, sentimiento de Genesys. Cumplimiento: los 6 checks con Cumple, No cumple o No aplica. Temas secundarios: fraude, compras online y seguridad. Entidades: fecha, importe (58,32 euros), comercio y producto. 5 palabras clave. |
| Detalle de `1CO-889E6DFE-…` | La conversación con temas y entidades «sin valor» (llamada corta): Resultado y cumplimiento rellenos; sin secciones de temas ni de entidades. |
| Dashboard «Visión general» | Tasa de resolución, escalado, FCR y CSAT «Calculado sobre 3 conversaciones». Tras la corrección de abajo, la distribución por main topic muestra sus 2 grupos y la tabla «KPIs por main topic» da sus valores. |
| Consola del navegador | Sin errores. |

## Hallazgos del recorrido y correcciones

- **Desglose por main topic oculto:** el dashboard decía «Sin datos · pendiente de análisis» aunque 11 conversaciones ya tenían main topic. Causa: `breakdown.pending` seguía significando «a alguna conversación le falta análisis» y el front lo aplicaba a todo el gráfico. Ahora la respuesta lleva `pending_kpis` (los KPIs sin datos) y, por main topic, `pending` solo es `true` si ninguna conversación lo tiene. Hay un test de regresión en el backend (`test_the_breakdown_says_which_kpis_are_still_pending`) y otro en el front («el desglose por main topic se pinta…»). Comprobado de nuevo en el navegador.
- **Pestaña del Output de 432 caracteres:** el nombre era los 19 destinos unidos con «+». Ahora, con más de 3, lleva los dos primeros y «y N campos más». Test de regresión: `test_a_long_list_of_targets_gets_a_short_destination`.

## Pendiente para `/test`

- OpenAI y Anthropic con el esquema de lista y la plantilla completa: sin claves, solo contrastados con su documentación (hipótesis de la spec).
- La base de desarrollo conserva lo que escribió esta ejecución en 3 conversaciones, con su trazabilidad en `llm_meta` (ejecución `1RN-2305A807-…`).

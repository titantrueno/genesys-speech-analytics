# FE004 — Diseñador de flujos de insights

> Estado: **pendiente de aprobación**. Depende de FE001 y reutiliza los filtros de FE002.

## Objetivo

Diseñar visualmente, con cajas drag & drop, flujos que toman una muestra de conversaciones, les aplican un prompt específico y producen un output de insights, y ejecutarlos de forma simulada.

## Criterios de aceptación

1. La sección **Flujos de insights** muestra el listado de flujos (nombre, autor, última modificación, última ejecución y estado) y permite crear, duplicar, renombrar y borrar.
2. El editor tiene una paleta de nodos y un lienzo (React Flow). Los nodos se arrastran de la paleta al lienzo, se mueven, se conectan, se desconectan y se eliminan; el lienzo admite zoom y desplazamiento.
3. Tipos de nodo y su configuración (panel lateral al seleccionar un nodo):
   - **Sampling:** intervalo, filtros (reutilizando el constructor de FE002), método (`aleatorio`, `estratificado` por canal, cola o main topic, o `primeros N` por un criterio) y tamaño de muestra. Muestra una estimación del nº de conversaciones disponibles.
   - **Prompt:** plantilla de texto con variables (`{{transcripcion}}`, `{{summary}}`, `{{main_topic}}`, `{{metadatos}}`), modelo (lista mock), temperatura y formato de salida esperado (texto, etiqueta de una lista o JSON con esquema).
   - **Output:** tipo `tabla de insights por conversación`, `métrica agregada` (recuento o % por etiqueta) o `informe resumen`, con un nombre de destino.
4. Reglas de conexión: `Sampling → Prompt → Output`. Se admiten varios prompts en cadena y varios outputs desde un prompt; no se admiten ciclos. Las conexiones inválidas se rechazan con un aviso, y hay tests de las reglas.
5. El botón **Validar** lista los errores (nodo sin configurar, prompt sin variables, flujo sin output, nodos sueltos) y los marca en el lienzo. No se puede ejecutar un flujo inválido.
6. El flujo se guarda como JSON (nodos, posiciones, conexiones y configuración) en el backend en memoria. Al recargarlo se reconstruye idéntico (test de ida y vuelta).
7. **Ejecución simulada:** `POST /api/flows/{id}/runs` ejecuta el flujo en el backend. El sampling es real sobre el dataset mock y respeta el método y el tamaño (tests por método). El prompt no llama a ningún LLM: produce resultados mock deterministas coherentes con el formato de salida y el análisis de cada conversación.
8. Durante la ejecución, cada nodo muestra su estado (`pendiente`, `en curso`, `ok`, `error`) y el nº de elementos procesados. La UI refleja el progreso mediante polling.
9. El resultado de cada output se ve en una pestaña: tabla con enlace al detalle de cada conversación, gráfico para métricas agregadas o texto para el informe.
10. Hay historial de ejecuciones por flujo, con fecha, usuario, tamaño de muestra, duración y estado; cada ejecución se puede reabrir.
11. Solo los roles con permiso de edición de flujos pueden modificar y ejecutar; los demás ven el flujo en solo lectura (test de permisos).

## Conocimiento afectado

- [Glosario](../../vault/glosario/terminos-del-harness.md): hay que añadir «flujo de insights», «sampling», «nodo» y «ejecución».
- La nueva entrada de arquitectura de la plataforma debe incluir el formato JSON del flujo y el motor de ejecución simulado.
- [Decisiones](../../vault/decisiones/Index.md): hay que crear ADR-006 (ejecución de prompts simulada y punto de extensión para un LLM real).

## Alcance

- CRUD de flujos, editor drag & drop, validación, ejecución simulada con progreso, resultados e historial.

## Fuera de alcance

- Llamadas reales a un LLM y gestión de claves de proveedor.
- Programación periódica de flujos.
- Nodos de transformación de código o condicionales.
- Edición colaborativa simultánea.

## Riesgos y asunciones

- **Asunción:** los resultados del prompt son simulados; el valor del piloto es validar la experiencia de diseño y no la calidad del insight.
- **Riesgo:** el editor drag & drop es la pieza de UI más compleja. Si el plan supera 9 tareas, se divide en una feature nueva para la ejecución.

# FE004 — Diseñador de flujos de insights

> Estado: **aprobada** el 2026-09-28 (revisada tras la entrega de `v0.3.0`). Depende de FE001, reutiliza el constructor de filtros de FE002 y aplica FE007 y FE008.

## Objetivo

Diseñar visualmente, con cajas drag & drop, flujos que toman una muestra de conversaciones, les aplican un prompt específico y producen un output de insights, y ejecutarlos de forma simulada.

## Conceptos

- **Flujo de insights** (`1FL`): grafo dirigido y acíclico de nodos con nombre, autor y fechas. Los flujos son compartidos por el equipo: cualquier persona con `flows:edit` puede editar cualquier flujo.
- **Nodo** (`1ND`): caja del flujo de tipo `sampling`, `prompt` u `output`, con posición en el lienzo y configuración.
- **Conexión:** arista `origen → destino` entre dos nodos. No es una entidad: se identifica por sus dos nodos.
- **Ejecución** (`1RN`): ejecución simulada de la versión guardada de un flujo, con el estado de cada nodo, los resultados de cada output y una copia del grafo ejecutado.
- **Formato JSON del flujo** (versión 1):

  ```json
  {
    "version": 1,
    "nodes": [{ "id": "1ND-…", "type": "sampling", "position": { "x": 0, "y": 0 }, "config": {} }],
    "edges": [{ "source": "1ND-…", "target": "1ND-…" }]
  }
  ```

  El editor crea los nodos con claves temporales (`tmp-…`) y el backend les asigna su identificador `1ND` al guardar, porque los identificadores solo se generan con `backend/app/ids.py`.

## Criterios de aceptación

### Backend

1. **CRUD:** `GET/POST /api/flows`, `GET/PATCH/DELETE /api/flows/{id}`, `PUT /api/flows/{id}/graph` y `POST /api/flows/{id}/duplicate`. El listado devuelve, por flujo, nombre, autor, última modificación, última ejecución (fecha y estado) y estado del flujo (`valido` o `con_errores`, según la validación del criterio 5). Duplicar crea una copia «Copia de …» con nodos nuevos y sin historial. Un identificador inexistente, mal formado o de otro tipo devuelve `404`; un nombre vacío o de más de 80 caracteres, `422`.
2. **Integridad del grafo** (se exige al guardar; si no se cumple, `422` con la lista de errores): tipos de nodo conocidos, identificadores únicos (`1ND` o temporales), conexiones entre nodos existentes, configuración con los tipos y rangos del criterio 3 (aunque esté incompleta), como máximo 50 nodos y 100 conexiones, y las **reglas de conexión**:
   - se admiten `sampling → prompt`, `prompt → prompt` (prompts en cadena) y `prompt → output`;
   - un `prompt` y un `output` tienen como máximo una entrada; un `sampling` o un `prompt` pueden tener varias salidas;
   - no se admiten conexiones duplicadas, bucles sobre el mismo nodo ni ciclos.

   Las reglas están en un fichero de casos compartido que ejecutan los tests del backend y los del front.
3. **Configuración por tipo:**
   - **Sampling:** filtros con el modelo de consulta de FE002 (intervalo y árbol de condiciones), método (`aleatorio`, `estratificado` por `canal`, `cola` o `main_topic`, o `primeros_n` por fecha, duración, sentimiento o CSAT, ascendente o descendente) y tamaño de muestra de 1 a 1.000. `POST /api/flows/sampling/estimate` devuelve el nº de conversaciones que cumplen los filtros y el tamaño efectivo de la muestra.
   - **Prompt:** plantilla de 1 a 4.000 caracteres con variables `{{transcripcion}}`, `{{summary}}`, `{{main_topic}}` y `{{metadatos}}` (y `{{resultado_anterior}}` en un prompt encadenado), modelo de una lista mock, temperatura de 0 a 1 y formato de salida: `texto`, `etiqueta` (de 2 a 20 etiquetas distintas) o `json` (esquema de 1 a 20 campos con nombre y tipo `texto`, `numero` o `booleano`).
   - **Output:** tipo `tabla` (insights por conversación), `metrica` (`recuento` o `porcentaje` por etiqueta) o `informe` (informe resumen), y un nombre de destino de 1 a 80 caracteres.

   `GET /api/flows/catalog` devuelve los modelos, variables, métodos, criterios y tipos disponibles.
4. **Validación** (`POST /api/flows/validate` con un grafo, sin guardarlo): devuelve la lista de errores con su código, mensaje y nodo afectado, como mínimo para: nodo sin configurar o con un valor no válido, prompt sin variables o con una variable desconocida, `{{resultado_anterior}}` en un prompt que no está encadenado, flujo sin sampling, flujo sin output, nodo suelto (sampling sin salida, prompt sin entrada o sin salida, output sin entrada), métrica cuya entrada no produce etiquetas y nombres de destino repetidos. Un flujo vacío es no válido.
5. **Ejecución simulada:** `POST /api/flows/{id}/runs` valida la versión guardada (`422` con los errores si no es válida; `409` si ya hay una ejecución en curso de ese flujo), crea la ejecución en estado `pendiente`, responde `202` y la ejecuta en segundo plano:
   - **Sampling real** sobre el dataset mock: respeta los filtros, el método y el tamaño (el efectivo es el mínimo entre el pedido y los disponibles). `aleatorio` es reproducible con la semilla que guarda la ejecución; `estratificado` reparte la muestra de forma proporcional a cada estrato (con un margen de ±1) y `primeros_n` devuelve las N primeras según el criterio. Hay tests por método.
   - **Prompt simulado**, sin llamar a ningún LLM: resultados deterministas (mismas entradas, mismo resultado) que respetan el formato de salida y se derivan del análisis de cada conversación. Una `etiqueta` es siempre una de la lista y, si alguna nombra el main topic o el sentimiento de la conversación, se elige esa; un `json` tiene exactamente los campos y tipos del esquema, y los campos con nombre conocido (`main_topic`, `sentimiento`, `resolucion`, `csat`, `riesgo_abandono`, `canal`, `cola`, `resumen`) toman el valor del análisis.
   - **Outputs:** `tabla`, una fila por conversación con el resultado de su prompt; `metrica`, recuento y porcentaje de cada etiqueta de la lista (también las que no aparecen), que suman el tamaño de la muestra y el 100 %; `informe`, un texto con el tamaño de la muestra, el reparto por main topic, el sentimiento medio y los resultados más frecuentes.
   - El motor del prompt está detrás de una interfaz (`PromptRunner`) que un test sustituye por otra sin cambiar la API: es el punto de extensión para un LLM real (ADR-006).
6. **Progreso:** cada nodo pasa por `pendiente → en_curso → ok` (o `error`) e informa del nº de elementos procesados y del total. `GET /api/flows/{id}/runs/{run_id}` devuelve el estado en cada momento. Un test observa estados intermedios y comprueba que los procesados no decrecen. Si la muestra queda vacía o un nodo falla, ese nodo y la ejecución acaban en `error` con un mensaje y los nodos que dependen de él quedan en `pendiente`.
7. **Historial:** `GET /api/flows/{id}/runs` lista las ejecuciones de un flujo (más reciente primero) con fecha, usuario, tamaño de muestra, duración y estado. El detalle de una ejecución incluye el grafo ejecutado, de modo que editar el flujo después no cambia lo que muestra.
8. **Persistencia en memoria:** guardar un grafo y leerlo devuelve exactamente el mismo JSON (test de ida y vuelta), también después de que el backend asigne los identificadores `1ND` a las claves temporales y reescriba las conexiones.
9. **Permisos:** las lecturas (listado, detalle, catálogo, estimación, validación e historial) exigen `flows:view`; crear, duplicar, renombrar, guardar, borrar y ejecutar exigen `flows:edit`. Un test con un rol que solo tiene `flows:view` recibe `403` en cada escritura y `200` en las lecturas, y el recorrido de rutas del OpenAPI cubre las rutas nuevas. El esquema y las sugerencias de campos de FE002 (`/api/query/schema` y `/api/query/suggest`) aceptan también `flows:view`, porque los usa el nodo Sampling.

### Front

10. La sección **Flujos de insights** (`/flujos`) lista los flujos con las columnas del criterio 1 y permite crear, duplicar, renombrar y borrar (con confirmación). Estados: cargando, error, vacío y sin permiso de edición (sin acciones).
11. El editor (`/flujos/{id}`) tiene una paleta de nodos y un lienzo de React Flow. Los nodos se arrastran de la paleta al lienzo (y, como alternativa accesible, se añaden con un botón), se mueven, se conectan arrastrando entre sus conectores, se desconectan y se eliminan (tecla Supr o botón). El lienzo admite zoom y desplazamiento.
12. Al seleccionar un nodo se abre su panel de configuración (criterio 3). El de Sampling reutiliza el constructor de filtros de FE002 y muestra la estimación de conversaciones disponibles. El panel también lista las conexiones del nodo, permite desconectarlas y conectar el nodo con otro desde un selector.
13. Una conexión que incumple las reglas del criterio 2 se rechaza con un aviso que explica el motivo; las reglas del front se prueban con el fichero de casos compartido.
14. **Validar** lista los errores del criterio 4 y marca en el lienzo los nodos afectados; al pulsar un error se selecciona su nodo. **Ejecutar** guarda los cambios pendientes, valida y, si el flujo no es válido, muestra los errores sin ejecutar.
15. **Guardar** envía el JSON del flujo; al recargar la página el lienzo se reconstruye idéntico (nodos, posiciones, conexiones y configuración). El editor avisa de los cambios sin guardar antes de salir de la página.
16. **Ejecución** (`/flujos/{id}/ejecuciones/{runId}`): muestra el grafo ejecutado con el estado de cada nodo (`pendiente`, `en curso`, `ok`, `error`) y los elementos procesados, y lo actualiza mediante polling hasta que la ejecución termina.
17. El resultado de cada output se ve en una pestaña con su nombre de destino: una tabla con una fila navegable al detalle de cada conversación (patrón de FE007, con «Volver a la ejecución»), un gráfico de barras con vista de tabla para las métricas y el texto para el informe.
18. El historial de ejecuciones del flujo muestra fecha, usuario, tamaño de muestra, duración y estado, y cada ejecución se puede reabrir.
19. Sin `flows:edit`, el listado y el editor están en solo lectura: sin paleta ni acciones, sin arrastrar, conectar ni borrar, y con el panel de configuración deshabilitado (test de permisos).

### Calidad

20. `./scripts/ci.sh` en verde.
21. Verificación en Chrome contra la API real: crear un flujo arrastrando Sampling, dos Prompts en cadena y dos Outputs, conectarlos con el ratón, intentar una conexión no válida, validar un flujo incompleto, guardar y recargar, ejecutar viendo el progreso, abrir los resultados de cada output y una conversación desde la tabla, y reabrir la ejecución desde el historial, sin errores de consola.

## Conocimiento afectado

- [Glosario](../../vault/glosario/terminos-del-harness.md): añadir «flujo de insights», «nodo», «conexión», «sampling» y «ejecución».
- [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): la entrada ya existe (la spec original pedía crearla); se amplía con el formato JSON del flujo, las reglas de conexión, el motor de ejecución simulado, el progreso por polling y los permisos.
- [Decisiones](../../vault/decisiones/Index.md): crear **ADR-006** (ejecución de prompts simulada y punto de extensión `PromptRunner` para un LLM real). [ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md) registra la dependencia nueva del front (React Flow).
- [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md): `1FL`, `1ND` y `1RN` pasan de reservados a activos; las conexiones no son entidades.
- [Patrones de interfaz](../../vault/ingenieria/patrones-de-interfaz.md): la tabla de resultados reutiliza la fila navegable; «Volver a» admite rutas con parámetros.
- [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md): revisar al planificar y añadir las nuevas.

## Alcance

- CRUD de flujos, editor drag & drop, validación, ejecución simulada con progreso, resultados e historial.

## Fuera de alcance

- Llamadas reales a un LLM y gestión de claves de proveedor.
- Programación periódica de flujos.
- Nodos de transformación de código o condicionales.
- Edición colaborativa simultánea: si dos personas guardan el mismo flujo, gana el último guardado.
- Cancelar una ejecución en curso y persistir flujos o ejecuciones entre reinicios de la API.
- Exportar los resultados de un output a un destino real: el nombre de destino solo identifica el resultado.

## Riesgos y asunciones

- **Asunción:** los resultados del prompt son simulados; el valor del piloto es validar la experiencia de diseño y no la calidad del insight.
- **Riesgo:** el editor drag & drop es la pieza de UI más compleja. Si el plan supera 9 tareas, se divide en una feature nueva para la ejecución.
- **Riesgo:** React Flow mide los nodos con el DOM y jsdom no tiene layout. Los tests de front cubren la lógica (reglas, conversión JSON ↔ lienzo, paneles, alternativas accesibles) y el arrastre real se verifica en Chrome (criterio 21).
- **Asunción:** con los roles por defecto de [ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md), todo rol con `flows:view` tiene también `flows:edit`, y `viewer` no ve la sección. La solo lectura se prueba con un rol creado en el test; FE006 permitirá crearlo desde la UI.
- **Riesgo:** la ejecución en segundo plano comparte memoria con las peticiones. El estado de cada ejecución se protege con un cerrojo y se devuelve como copia.

---
title: "Patrones de interfaz"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [ingenieria, frontend, ux, accesibilidad]
created: 2026-09-27
updated: 2026-10-13
---

# Patrones de interfaz

## Resumen

Patrones de UI reutilizables del front. Cada patrón indica cuándo usarlo, cómo se implementa y cómo se prueba.

## Conocimiento confirmado

### Fila de tabla navegable

**Cuándo:** tablas o tarjetas donde cada elemento representa una entidad con página de detalle: conversaciones del listado y del explorador, resultados de la búsqueda semántica, flujos de insights y filas de la tabla de resultados de una ejecución (FE004) y, en el futuro, usuarios de FE006.

**Cómo:**

- La lógica vive en el hook `useRowNavigation(href)` (`frontend/src/conversations/useRowNavigation.ts`), que devuelve `onClick`, `onAuxClick` y el `state` del enlace. Lo usan `ConversationTable` y `ResultCard`.
- La fila (`<tr>`) o la tarjeta (`<article>`) tiene un `onClick` que navega al detalle y pasa `state.from` con la ubicación actual, para que volver restaure filtros, página y orden.
- Un único enlace real en la primera celda es el punto de foco con teclado y el destino accesible. La fila no recibe `role="link"` ni `tabindex`, para no romper la semántica de tabla ni duplicar paradas de tabulación.
- Se ignoran los clics que salen de elementos interactivos internos (`a`, `button`, `input`…), para no navegar dos veces.
- Ctrl+clic, Cmd+clic y el clic central (`auxclick`, botón 1) abren `window.open(href, '_blank', 'noopener')`.
- Si hay texto seleccionado (`window.getSelection().toString()`), no se navega, para poder copiar contenido de la fila.
- Estilo: `cursor-pointer` y fondo al pasar el ratón.

**Cómo se prueba:** clic en cada columna, una sola navegación desde el enlace, ausencia de `role` y `tabindex` en la fila, modificadores con `window.open` espiado y selección simulada con `getSelection`.

### Enlace profundo a un turno

**Cuándo:** para abrir el detalle de una conversación en un punto concreto (resultados de la búsqueda semántica).

**Cómo:**

- La URL es `/conversaciones/{id}?turn=N`, con `N` el índice del turno en la conversación (incluidos los de sistema).
- El turno activo se deriva de la URL, sin `setState` en un efecto. Un efecto solo desplaza el contenedor del chat con `container.scrollTo`, no con `scrollIntoView` (ver [lecciones](../aprendizaje/lecciones-construccion-plataforma.md), punto 3).
- Un `turn` que no es un entero dentro de la conversación se ignora sin error. Elegir otro turno desde el análisis sustituye al de la URL.
- «Volver» usa `state.from`: `BackLink` reconoce listado, explorador y búsqueda por su ruta exacta, y la ejecución de un flujo por patrón (`/flujos/{id}/ejecuciones/{runId}`, «Volver a la ejecución»).

**Cómo se prueba:** `offsetTop` simulado por turno y `scrollTo` espiado sobre el contenedor; turnos no válidos (`99`, `-1`, `abc`, `2.5`); verificación en Chrome de `scrollTop` y de que la cabecera sigue visible.

### Lienzo de nodos (React Flow)

**Cuándo:** editores visuales de grafos (diseñador de flujos de FE004).

**Cómo:**

- El estado de React Flow (nodos con sus medidas y selección) es la fuente de verdad en el editor y el JSON se deriva con `fromCanvas`. No se regeneran los nodos en cada render: se perderían las medidas.
- Toda acción de ratón tiene una alternativa accesible: añadir con un botón además de arrastrar, y conectar, desconectar y eliminar desde el panel del nodo.
- Una conexión rechazada muestra el motivo (`onConnectEnd`), también si se suelta sobre un nodo sin conector de entrada.
- `fitView` solo al abrir un grafo con nodos. Los nodos añadidos con botón van al primer hueco libre.
- El tipo de nodo `output` coincide con un nodo integrado de React Flow: su estilo se neutraliza dentro de `.insight-flow`, con foco visible para teclado.
- En modo lectura: `nodesDraggable`, `nodesConnectable` y `deleteKeyCode` desactivados, y el panel en un `fieldset` deshabilitado.

**Cómo se prueba:** en jsdom con el mock de `frontend/src/test/reactFlow.ts` (clic para seleccionar con `fireEvent`, Supr, `drop` con `dataTransfer` simulado); el arrastre real, las conexiones con el ratón, el zoom y el desplazamiento, en Chrome.

### Pestañas de resultados

**Cuándo:** varias vistas del mismo nivel (outputs de una ejecución).

**Cómo:** patrón de pestañas de WAI-ARIA: `tablist`, `tab` con `aria-selected` y `aria-controls`, un único `tab` con `tabIndex` 0 y flechas izquierda y derecha en ciclo. En Configuración (FE005) y en Usuarios y roles (FE006) la pestaña activa vive en la URL (`?tab=`): `components/Tabs.tsx` y `components/useTabParam.ts`.

### Formulario con errores del backend

**Cuándo:** formularios que valida el backend (Configuración, FE005; Usuarios y roles, FE006).

**Cómo:** `ConfigField` (`frontend/src/config/controls.tsx`) muestra el mensaje del `422` bajo su campo, lo enlaza con `aria-describedby` y marca el control con `aria-invalid`; lo escrito se conserva. `fieldErrors` convierte `loc` en claves (`platform_name`, `keywords.0`), tanto de un `422` como de un `409` por duplicado (email, código). Un `409` con texto (una protección, un rol en uso) se muestra como alerta con el motivo. Guardar solo se habilita con cambios y confirma «Cambios guardados» con `role="status"`. Sin permiso de edición, un `fieldset` deshabilitado y sin botones.

### Confirmación en la fila

**Cuándo:** acciones destructivas o que ocultan algo (borrar, desactivar) en una tabla.

**Cómo:** `ConfirmAction`: el primer clic sustituye el botón por la pregunta y «Confirmar» / «No» en la propia fila; no hay diálogos modales. Una acción imposible (borrar un tema en uso, borrar un check del análisis) no se ofrece.

### Matriz que guarda al cambiar

**Cuándo:** casillas que se guardan una a una sin botón Guardar (matriz de permisos, FE006).

**Cómo:** mientras se guarda, la columna afectada muestra lo pulsado (variables de la mutación) y se deshabilita; la mutación sigue pendiente hasta que termina la recarga de datos, así que no hay parpadeo. Si el backend lo rechaza, vuelve al valor guardado y se muestra el motivo. Cada casilla tiene nombre accesible «permiso · rol».

### Fechas

**Cómo:** toda fecha con hora se formatea con `frontend/src/lib/format.ts` en la zona de la plataforma (`GET /api/config/public`); un test impide usar `Intl.DateTimeFormat` fuera de ese módulo.

### Análisis pendiente y datos reales (FE012)

- Un campo del análisis que aún no existe se muestra como «Análisis pendiente» (cursiva gris), nunca como 0 ni «—»; los KPIs, «Sin datos · pendiente de análisis».
- En el chat, una línea separadora (`role="separator"`) marca la transferencia del asistente virtual al agente y un mensaje no entregado conserva su texto con la marca «No entregado».
- Las columnas y la búsqueda de Genesys solo aparecen con el origen `real` (`catalog.origin`). Un `503` de datos se muestra en un aviso único sobre el contenido.

### Textos de la interfaz (FE016, [ADR-010](../decisiones/adr-010-idioma-de-la-interfaz-y-api-en-ingles.md))

**Cuándo:** siempre que un componente muestre un texto fijo. **Ningún texto de interfaz va escrito en el código**: sale de los diccionarios.

**Cómo:**

- Diccionarios por área en `frontend/src/i18n/es/<área>.ts` y `en/<área>.ts`, con claves planas con prefijo (`conv.title`, `dash.w.volume`). `es` define las claves; `en` debe tener las mismas y los mismos `{parámetros}`.
- En un componente, `const { t, tOr } = useI18n()`. Plurales: `t('conv.count', { count, n: formatInteger(count) })` con `conv.count_one` y `conv.count_other`. Fuera de un componente, la función recibe `t` (o `Labeler`) como parámetro, con el español por defecto (`DEFAULT_I18N`).
- Las etiquetas que llegan del backend (catálogos) se traducen por clave con `tOr('prefijo.<clave>', etiquetaDelBackend)`: una clave nueva del backend se ve con su etiqueta hasta que se añada al diccionario.
- Números, porcentajes, fechas y duraciones salen de `lib/format.ts`, que sigue el idioma activo; nunca `toLocaleString('es-ES')` ni `Intl` directo en un componente.
- No se traducen los datos (transcripciones, resúmenes, main topics, palabras clave, nombres de colas, agentes, roles, flujos, checks…). Un mensaje de la API se muestra tal cual (llega en inglés).
- Añadir una pantalla: crear las claves en `es` y `en`, usar `t`, y comprobar con un test de render en inglés que cabeceras y botones salen en inglés y que los datos no cambian (ver `i18n/EnglishScreens.test.tsx`).

**Cómo se prueba:** el test de paridad (`i18n/dictionaries.test.ts`), el que impide texto en español escrito a mano en cualquier archivo de `frontend/src` (`i18n/noHardcodedSpanish.test.ts`) y los tests de render en inglés por pantalla. En `es` los textos no cambian: la suite en español no se toca.

## Límites y excepciones

- El idioma lo fija solo Configuración → General; no hay selector en el login ni en el panel.
- No se aplica a tablas cuyas filas llevan a un listado filtrado (tablas de los dashboards): ahí el enlace está en la etiqueta de la fila.
- La navegación por filas con las flechas del teclado queda fuera de alcance.

## Fuentes

- [Spec FE007](../../features/FE007-fila-completa-abre-detalle-conversacion/spec.md)
- [Implementación](../../frontend/src/conversations/ConversationsPage.tsx)
- [Tests](../../frontend/src/conversations/RowNavigation.test.tsx)
- [Tests de la búsqueda](../../frontend/src/search/SearchNavigation.test.tsx) (FE003)
- [Tests de la matriz de permisos](../../frontend/src/users/RolesTab.test.tsx) (FE006)
- [Spec FE004](../../features/FE004-disenador-de-flujos-de-insights/spec.md)
- [Spec FE005](../../features/FE005-configuracion-de-la-plataforma/spec.md)
- [Spec FE016](../../features/FE016-idioma-ingles-de-la-interfaz/spec.md)
- [ADR-010](../decisiones/adr-010-idioma-de-la-interfaz-y-api-en-ingles.md)
- [React Flow · Testing](https://reactflow.dev/learn/advanced-use/testing)
- [WAI-ARIA APG · Tabs](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)

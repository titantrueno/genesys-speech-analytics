---
title: "Patrones de interfaz"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [ingenieria, frontend, ux, accesibilidad]
created: 2026-09-27
updated: 2026-09-28
---

# Patrones de interfaz

## Resumen

Patrones de UI reutilizables del front. Cada patrón indica cuándo usarlo, cómo se implementa y cómo se prueba.

## Conocimiento confirmado

### Fila de tabla navegable

**Cuándo:** tablas o tarjetas donde cada elemento representa una entidad con página de detalle: conversaciones del listado y del explorador, resultados de la búsqueda semántica y, en el futuro, usuarios de FE006.

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
- «Volver» usa `state.from`: `BackLink` reconoce listado, explorador y búsqueda.

**Cómo se prueba:** `offsetTop` simulado por turno y `scrollTo` espiado sobre el contenedor; turnos no válidos (`99`, `-1`, `abc`, `2.5`); verificación en Chrome de `scrollTop` y de que la cabecera sigue visible.

## Límites y excepciones

- No se aplica a tablas cuyas filas llevan a un listado filtrado (tablas de los dashboards): ahí el enlace está en la etiqueta de la fila.
- La navegación por filas con las flechas del teclado queda fuera de alcance.

## Fuentes

- [Spec FE007](../../features/FE007-fila-completa-abre-detalle-conversacion/spec.md)
- [Implementación](../../frontend/src/conversations/ConversationsPage.tsx)
- [Tests](../../frontend/src/conversations/RowNavigation.test.tsx)
- [Tests de la búsqueda](../../frontend/src/search/SearchNavigation.test.tsx) (FE003)

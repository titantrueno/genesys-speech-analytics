# FE007 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-09-27. Se construye después de FE008, porque las filas usan los nuevos identificadores.

## Contraste con el vault

No hay entradas afectadas salvo la nueva de patrones de interfaz. El criterio 23 de FE001 (volver al listado conservando su estado) ya está implementado con `location.state.from` en [ConversationsPage.tsx](../../frontend/src/conversations/ConversationsPage.tsx) y se reutiliza.

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Clic en toda la fila navega al detalle | FE008 | 1, 2, 3, 4, 7 |
| T2 | Modificadores de pestaña nueva y selección de texto | T1 | 5, 6 |
| T3 | Patrón en el vault y verificación en navegador | T2 | Conocimiento afectado |

### T1 — Clic en toda la fila

- **Qué:** un manejador `onClick` en `<tr>` navega con `state.from`. Ignora los clics que salen de un `<a>` o `<button>` interno para no navegar dos veces. La fila recibe `cursor-pointer` y fondo al pasar el ratón. El único elemento enfocable sigue siendo el enlace de la fecha.
- **Hecho cuando:** hay tests para el clic en cada una de las 10 columnas, la vuelta al listado conservando su estado, una sola navegación al pulsar el enlace de la fecha y que la fila no tenga `role=link` ni `tabindex`.

### T2 — Modificadores y selección

- **Qué:** con Ctrl, Cmd o el botón central (`auxclick`), abre `window.open(href, '_blank', 'noopener')`. Si `window.getSelection()` contiene texto seleccionado, no navega.
- **Hecho cuando:** hay tests para Ctrl+clic y Cmd+clic, que llaman a `window.open` con la URL del detalle y no navegan; para el clic central; y para que un clic con texto seleccionado no navegue.

### T3 — Patrón y verificación

- **Qué:** entrada `vault/ingenieria/patrones-de-interfaz.md` enlazada desde el índice de ingeniería.
- **Hecho cuando:** la auditoría del vault devuelve `0` y, en Chrome contra la API real, el clic en la celda del summary abre el detalle y volver restaura el listado.

## Progreso

| Id | Estado | Evidencia |
|---|---|---|
| T1 | Hecha | `npm test`: 66 tests en verde (rojo previo: 11 fallos). Clic en cada una de las 10 columnas abre el detalle conservando `state.from`; el enlace de la fecha navega una sola vez; la fila no tiene `role` ni `tabindex` y mantiene un único enlace. |
| T2 | Hecha | `npm test`: 70 tests en verde (rojo previo: 4 fallos). Ctrl+clic, Cmd+clic y clic central llaman a `window.open(detalle, '_blank', 'noopener')` sin navegar; con texto seleccionado no se navega. |
| T3 | Hecha | Entrada `vault/ingenieria/patrones-de-interfaz.md` enlazada; auditoría `0`. En Chrome contra la API real: el clic en la celda del summary abre el detalle; volver restaura `?resolution=escalada&page=2&sort=sentiment&order=asc`; Ctrl/Cmd+clic abre una pestaña nueva sin mover la actual; arrastrar para seleccionar texto no navega; sin errores de consola. |

**FE007 completada.** Siguiente: FE001 T9.

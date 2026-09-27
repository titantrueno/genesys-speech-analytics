# FE007 — Fila completa abre el detalle de la conversación

> Estado: **pendiente de aprobación**. Fase `/spec`. Modifica el listado de FE001 (T7), que todavía no se ha entregado.

## Objetivo

Que pulsar en cualquier parte de una fila del listado de conversaciones abra su detalle, y no solo el enlace de la fecha.

## Criterios de aceptación

1. Un clic en cualquier celda de la fila (Fecha, Canal, Cola, Agente, Main topic, Summary, Duración, Sentimiento, Resolución o CSAT) navega a `/conversaciones/{id}` de esa fila (test por cada columna).
2. La navegación desde la fila conserva el estado del listado: al volver desde el detalle se recuperan filtros, página y orden, igual que en el criterio 23 de FE001 (test).
3. La fila muestra `cursor: pointer` y un fondo al pasar el ratón, para indicar que es clicable.
4. Pulsar el enlace de la fecha sigue funcionando y navega una sola vez; el clic no se procesa dos veces (test).
5. Ctrl+clic o Cmd+clic y el clic central en la fila abren el detalle en una pestaña nueva, igual que un enlace, sin cambiar la pestaña actual (test).
6. Si el usuario arrastra para seleccionar texto dentro de la fila (por ejemplo, copiar el summary), no se navega (test).
7. **Accesibilidad:** cada fila mantiene un único punto de foco (el enlace de la fecha), que abre el detalle con Enter. No se añaden paradas de tabulación extra ni se convierte la fila en un enlace, para no romper la semántica de tabla (test de roles).

## Conocimiento afectado

- [Ciclo de entrega](../../vault/ingenieria/ciclo-de-entrega.md): no cambia.
- Hay que crear `vault/ingenieria/patrones-de-interfaz.md` con el patrón «fila de tabla navegable» (clic en toda la fila, un solo foco, modificadores de pestaña nueva y selección de texto), para reutilizarlo en las tablas de FE002, FE003 y FE006.

## Alcance

- Tabla del listado de conversaciones (`/conversaciones`).

## Fuera de alcance

- Tablas de los dashboards (KPIs por main topic, rendimiento por agente), cuyas filas llevan al listado y no al detalle.
- Navegación con teclado por filas (flechas arriba y abajo).

## Riesgos y asunciones

- **Asunción:** el clic en la fila abre el detalle en la misma pestaña, como el enlace de la fecha.
- **Riesgo:** los manejadores de clic en `<tr>` pueden romper la selección de texto o duplicar navegaciones. Los criterios 4 y 6 lo cubren con tests.

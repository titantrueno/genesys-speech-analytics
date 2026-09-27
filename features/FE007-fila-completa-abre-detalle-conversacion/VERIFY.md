# FE007 — Verificación

> Fase `/test`. Fecha: 2026-09-27. Artefactos: [spec](spec.md) · [plan](plan.md). La evidencia global (suites, auditorías, prueba de humo) está en [FE001/VERIFY](../FE001-base-dashboards-y-detalle-conversaciones/VERIFY.md#evidencia).

## Resultado

**Verde.** Los 7 criterios tienen evidencia automatizada y en navegador.

## Matriz de trazabilidad

| # | Criterio | Evidencia (`RowNavigation.test.tsx` salvo indicación) |
|---|---|---|
| 1 | Clic en cualquier celda abre el detalle | «un clic en la celda %s abre el detalle de esa fila» × 10 columnas; Chrome: clic en el summary |
| 2 | Volver conserva el listado | El mismo test comprueba `state.from.search`; Chrome: restaura `?resolution=escalada&page=2&sort=sentiment&order=asc` |
| 3 | Cursor y fondo al pasar el ratón | «la fila no es un enlace…» comprueba `cursor-pointer` |
| 4 | El enlace de la fecha navega una vez | «pulsar el enlace de la fecha navega una sola vez» |
| 5 | Ctrl/Cmd+clic y clic central abren pestaña nueva | «%s+clic abre el detalle en una pestaña nueva sin navegar» × 2, «el clic central…»; Chrome: pestaña nueva y la actual se queda |
| 6 | Seleccionar texto no navega | «si hay texto seleccionado en la fila no navega»; Chrome: arrastrar sobre el summary |
| 7 | Un único foco, sin `role` ni `tabindex` en la fila | «la fila no es un enlace ni una parada de tabulación extra» |

## Fundamentación

| Decisión | Fuente |
|---|---|
| `window.open(href, '_blank', 'noopener')` para no exponer `window.opener` | [MDN · Window.open](https://developer.mozilla.org/en-US/docs/Web/API/Window/open) |
| No convertir `<tr>` en enlace: mantener la semántica de tabla y un solo foco | [HTML-AAM](https://www.w3.org/TR/html-aam-1.0/) (mapeo de roles de tabla); patrón en el [vault](../../vault/ingenieria/patrones-de-interfaz.md) |

## Registro de duda

| Afirmación | Duda | Reconciliación | Conclusión |
|---|---|---|---|
| Un `onClick` en `<tr>` no rompe la selección de texto | ¿Un arrastre dispara `click`? | Sí lo dispara; por eso se comprueba `getSelection()`, y en Chrome el arrastre no navega | Se cumple |
| El clic en el enlace no navega dos veces | El evento burbujea hasta `<tr>` | Se ignoran los clics que salen de `a, button…`; el test cuenta las navegaciones | Se cumple |

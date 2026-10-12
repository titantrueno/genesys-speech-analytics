# FE012 — Verificación

> Verificación de la implementación (2026-10-12). Pendiente de `/test` independiente, `/review` y `/ship`.

## Resultado por criterio

| Criterios | Evidencia |
|---|---|
| 1 (origen, permisos, auditoría) | `tests/test_data_source.py`, `DataOrigin.test.tsx` (solo lectura para `supervisor`, conector real sustituye a los simulados). |
| 2, 3, 4 | `tests/test_real_origin.py`: total igual al de la base, `503` sin PostgreSQL con Configuración accesible, datos nuevos en la siguiente petición. Con `sintetico` la suite anterior no cambia (860 → 866 tests sin PostgreSQL, en las dos semillas). |
| 5, 6 | `test_real_conversations.py`, `ConversationDetailReal.test.tsx`, `ConversationsReal.test.tsx`. |
| 7, 8, 10 | `test_real_explorer.py`, `test_real_contract.py` (más de 150 llamadas sin `500` con datos degradados). |
| 9 | KPIs pendientes y drill-down que cuadra con el listado; `DashboardsReal.test.tsx`. |
| 11, 12 | `test_search_index.py`, `test_real_search.py` (índice en caliente, enmascarado de teléfono, email, DNI, IBAN y tarjeta; ANI, DNIS y `externalTag` sin enmascarar). |
| 14 | `test_real_contract.py`: 12 endpoints con 1.000 conversaciones, por debajo de 500 ms en régimen estable (con el índice ya construido). |

## Recorrido en Chrome (criterio 15)

Hecho contra la API real (`localhost:18000`), el servicio de ingesta (18001) y la web (18002), con las 13 conversaciones del 12 de octubre que descargó FE011 (en la base de desarrollo):

- Con `admin`: cambio a «Real» con confirmación y registro en el log de cambios; listado con 13 conversaciones y columnas de Genesys; búsqueda por teléfono (7 llamadas); detalle de una llamada bot → agente con la línea de transferencia y el panel completo (contacto, recorrido, cierre, tiempos, MOS, reparto del tiempo, confianza, temas) y el clic en un tema, que lleva a su turno; dashboards con «Sin datos · pendiente de análisis», volumen 13, AHT sobre 6 conversaciones y el drill-down al listado de 13; búsqueda de «Amazon Brasil» (9 resultados); explorador «derivada a agente» (5); flujo de insights completo sobre 5 conversaciones reales; vuelta a «Sintético» (326 conversaciones en el periodo por defecto, sin columnas de Genesys ni KPIs pendientes).
- Sin errores de consola en la parte final del recorrido; la lectura de consola empezó a mitad del recorrido.

**No comprobado en el navegador** (cubierto por tests): el rol `supervisor`, el chat con un mensaje no entregado y el chat con reconexión de la base de desarrollo.

## Gate

`./scripts/ci.sh` terminó con código 0 el 2026-10-12 (vault, backend con dos datasets, PostgreSQL, OpenAPI, front y auditoría de dependencias).

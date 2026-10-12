# FE012 — Verificación

> Fase `/test` (2026-10-12). Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde.** Los 15 criterios tienen evidencia automatizada, real (Chrome y la base de desarrollo con las 13 conversaciones del día) o ambas. La verificación escéptica encontró y corrigió tres cosas:

1. **Periodo por defecto vacío (bug real, encontrado por el usuario al probar):** con el origen `real`, el periodo por defecto acababa ayer y las conversaciones descargadas hoy quedaban fuera: 200 con 0 conversaciones. En el recorrido de Chrome no lo vi porque pasaba el rango en la URL. Causa raíz: `default_period_end` no existía; las dos fuentes del periodo por defecto restaban un día siempre. Regresión: `test_the_default_period_includes_today_with_real_data`, su contrapartida sintética y un test de los atajos de periodo del front.
2. **Tres mutaciones sobrevivían** a la primera pasada (cambio de `DATABASE_URL` dentro de una petición, clientes sin identificar en el FCR y conexión de solo lectura). Ahora hay un test para cada una; la del FCR destapó además una guarda redundante, que se simplificó.
3. **Informe de flujo con datos reales:** `build_report` asumía main topic y sentimiento (se vio en T8, ejecutando el flujo completo; queda cubierto por `test_an_insights_flow_runs_over_real_conversations`).

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `./scripts/ci.sh` | **Código 0** («CI local: OK») |
| `python3 scripts/audit_vault.py` | **Código 0**: 51 archivos, 0 errores |
| Backend sin PostgreSQL, dos datasets (FE009) | **868 passed** y 868 passed |
| Backend con PostgreSQL (`REQUIRE_PG=1`) | **123 passed** |
| Front (`npm test`, lint, build, `tsc -b`) | **383 passed** (35 ficheros); lint sin avisos |
| OpenAPI | Al día y válido (`PUT /api/config/sources` y los campos nuevos documentados) |
| `pip-audit` / `npm audit --audit-level=high` | Sin vulnerabilidades / 0 «high»; siguen las 4 «moderate» de `swagger-ui-react` (ADR-002) |
| Mutaciones | **31 de 31 detectadas** (34 con las 3 supervivientes ya cubiertas): 20 de backend y 11 de front sobre el repositorio y su testigo, el periodo por defecto, el teléfono, los KPIs pendientes, el motor de «vacío», el enmascarado, el índice, las variables de prompts, los permisos, la transferencia del chat, los mensajes no entregados, los tiles pendientes, el selector y los avisos de validación |
| Rendimiento | 12 endpoints con 1.000 conversaciones por debajo de 500 ms en régimen estable |
| Contrato | Más de 150 llamadas (todos los endpoints y cada operador de cada campo del explorador) sin `500` con datos degradados |

## Grounding (documentación oficial)

- Solo lectura de la conexión: [PostgreSQL · `default_transaction_read_only`](https://www.postgresql.org/docs/16/runtime-config-client.html). La página no confirma que se pueda fijar con `-c` en las opciones de conexión, así que se **comprobó en runtime**: `test_the_api_connection_to_postgres_is_read_only` falla al quitar la opción (mutación detectada).
- [React · `useSyncExternalStore`](https://react.dev/reference/react/useSyncExternalStore): `getSnapshot` debe devolver un valor estable mientras el almacén no cambia; el aviso de datos no disponibles devuelve el mismo objeto de error de la caché o `null`.
- [FastAPI · manejo de errores](https://fastapi.tiangolo.com/tutorial/handling-errors/): `@app.exception_handler` para la excepción propia que se traduce en `503`.

## Rutina de duda

- **CLAIM:** «los datos nuevos aparecen en la siguiente petición». **Asunción:** la comprobación del testigo se hace una vez por petición. **Duda:** ¿y fuera de una petición, o si cambia la URL? **Evidencia:** el límite de 1 s y la comparación de URL, con tests y mutaciones. **STOP.**
- **CLAIM:** «con `sintetico` todo es como antes». **Duda:** nuevos campos en JSON y en el esquema de OpenAPI. **Evidencia:** los tests anteriores no cambian (salvo uno de FE003 que miraba un detalle interno, `build_default_engine`); `severity` solo aparece en los avisos; el esquema del explorador no cambia (test explícito). **STOP.**
- **CLAIM:** «el rendimiento es < 500 ms». **Duda:** la reconstrucción del índice compite por el procesador. **Evidencia:** medido; el test mide con el índice ya construido y queda anotado como hecho en ADR-005. **STOP.**

## Recorrido en Chrome (criterio 15)

Hecho contra la API real (`localhost:18000`), el servicio de ingesta (18001) y la web (18002), con las 13 conversaciones del 12 de octubre que descargó FE011 (en la base de desarrollo):

- Con `admin`: cambio a «Real» con confirmación y registro en el log de cambios; listado con 13 conversaciones y columnas de Genesys; búsqueda por teléfono (7 llamadas); detalle de una llamada bot → agente con la línea de transferencia y el panel completo (contacto, recorrido, cierre, tiempos, MOS, reparto del tiempo, confianza, temas) y el clic en un tema, que lleva a su turno; dashboards con «Sin datos · pendiente de análisis», volumen 13, AHT sobre 6 conversaciones y el drill-down al listado de 13; búsqueda de «Amazon Brasil» (9 resultados); explorador «derivada a agente» (5); flujo de insights completo sobre 5 conversaciones reales; vuelta a «Sintético» (326 conversaciones en el periodo por defecto, sin columnas de Genesys ni KPIs pendientes).
- Sin errores de consola en la parte final del recorrido; la lectura de consola empezó a mitad del recorrido.

**No comprobado en el navegador** (cubierto por tests): el rol `supervisor`, el chat con un mensaje no entregado y el chat con reconexión de la base de desarrollo.

## Gate

`./scripts/ci.sh` terminó con código 0 el 2026-10-12.

# FE001 — Verificación

> Fase `/test`. Fecha: 2026-09-27. Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.
> Se verifica junto con [FE007](../FE007-fila-completa-abre-detalle-conversacion/VERIFY.md) y [FE008](../FE008-identificadores-con-prefijo-y-uuid/VERIFY.md), que modifican el mismo código y se entregan a la vez.

## Resultado

**Verde.** Toda la batería pasa, cada criterio de aceptación tiene evidencia y los dos bugs encontrados durante la verificación están corregidos con test de regresión (commit `a0d6512`).

## Evidencia

| Comando | Resultado |
|---|---|
| `cd backend && .venv/bin/pytest` | **102 passed** (1 aviso de deprecación de Starlette, ver [REVIEW](REVIEW.md)) |
| `cd frontend && npm test` | **72 passed** (6 ficheros) |
| `cd frontend && npm run lint` | 0 avisos |
| `cd frontend && npm run build` | OK: `index` 396,5 kB y `DashboardsPage` 369,0 kB, sin aviso de tamaño |
| `python3 scripts/audit_vault.py` | **código 0**, 34 archivos, 0 errores |
| `npm audit` | 0 vulnerabilidades |
| `pip-audit` (versiones instaladas y fijadas, `--no-deps --disable-pip`) | No known vulnerabilities found |
| Prueba de humo en Chrome contra el build de producción (`vite preview` + API real) | **11/11**, sin errores de consola |
| Drill-down en Chrome contra la API real | **7/7**: el valor pulsado coincide con el total del listado |

Los scripts de navegador (Playwright sobre el Chrome local) se ejecutaron desde un directorio temporal y no están versionados; ver el hallazgo en [REVIEW](REVIEW.md).

## Matriz de trazabilidad

| # | Criterio | Evidencia |
|---|---|---|
| 1 | API y front arrancan | `test_health`; tests de login de `App.test.tsx`; prueba de humo |
| 2 | Dataset determinista | `test_generation_is_deterministic` |
| 3 | Login y 401 | `test_login_with_valid_credentials_returns_token_and_user`, `test_login_with_invalid_credentials_returns_401`, `test_every_non_public_api_route_requires_auth`, `test_tampered_token_returns_401`, `test_expired_token_returns_401` |
| 4 | 403 por rol y menú sin la sección | `test_require_permission_enforces_matrix`, `test_every_data_route_requires_a_permission`; «viewer no ve Configuración ni Usuarios y roles», «una sección sin permiso… muestra "Sin acceso"» |
| 5 | Navegación de 7 secciones y «Próximamente» | «admin ve las siete secciones», «una sección aún no implementada muestra "Próximamente"» |
| 6 | Main topic y summary en todas | `test_every_conversation_has_valid_main_topic_and_summary` |
| 7 | Coherencia transcripción, summary y topic | `test_transcript_is_coherent_with_main_topic`, `test_summary_mentions_motive_and_result` |
| 8 | Distribución realista y colas habituales | `test_topic_distribution_is_realistic`, `test_topics_route_to_their_usual_queues` |
| 9 | Datos sensibles ficticios y tarjetas enmascaradas | `test_no_full_card_numbers`, `test_fake_identifiers_have_valid_format` |
| 10 | Tres dashboards | «abre Visión general por defecto…», «el dashboard %s muestra sus widgets» |
| 11 | Distribución por main topic y tabla | «muestra la distribución por main topic ordenada…», tabla «KPIs por main topic» |
| 12 | KPI con valor, anterior y variación | `test_summary_matches_independent_calculation` (4 combinaciones); «marca si la variación mejora o empeora…», «el índice de sentimiento muestra la variación absoluta…» |
| 13 | Filtros globales en la URL | «cambiar el canal…», «filtrar por main topic…», «al montar con filtros en la URL…», «las opciones rápidas… usan la fecha de referencia del backend», `test_filters_by_main_topic_affect_all_metrics` |
| 14 | Granularidad día o semana | «la granularidad día/semana…», `test_timeseries_by_day_covers_every_day_and_matches`, `test_timeseries_by_week_clips_partial_weeks` |
| 15 | Drill-down desde tarjeta, punto, barra o segmento | `drilldown.test.tsx` (9 casos) |
| 16 | Total del listado = valor pulsado | `test_list_total_equals_breakdown_volume`, `test_list_total_equals_timeseries_point`, `test_kpi_drilldown_filters_match_kpi_values`; Chrome 7/7 |
| 17 | Listado: chips, paginación, orden y columnas | `ConversationsPage.test.tsx` (9 casos); `test_pagination_covers_every_conversation_once`, `test_sorting` |
| 18 | Chat tipo WhatsApp | «pinta la transcripción como un chat…» |
| 19 | Sentimiento por burbuja y palabras clave | «cada burbuja muestra su marca de tiempo relativa y un indicador de sentimiento», «resalta las palabras clave» |
| 20 | Cabecera con main topic y summary | «muestra el main topic destacado y el summary completo…» |
| 21 | Panel de análisis | «el panel de análisis muestra resultado, cumplimiento, temas y entidades» |
| 22 | Punto del gráfico → turno | «pulsar un punto… desplaza solo el chat…», «los puntos del gráfico son accesibles con teclado»; Chrome (`scrollY` sigue en 0) |
| 23 | Volver conserva el listado | «volver al listado conserva filtros, página y orden», «sin listado previo…»; prueba de humo |
| 24 | Suites, build y lint en verde | Tabla de evidencia |
| 25 | < 500 ms | `test_metrics_respond_under_500ms`, `test_conversation_endpoints_respond_under_500ms` |

## Tests que prueban de verdad

- **Rojo antes que verde:** cada tarea partió de rojo por la razón correcta; el recuento de fallos previos está en el [plan](plan.md#progreso).
- **Pruebas de mutación realizadas:**
  - una ruta sin auth y otra solo con login rompen los tests de recorrido de OpenAPI (T2);
  - cambiar la ventana del FCR a 8 días provoca 5 fallos (T3);
  - cambiar el umbral de «negativo» de `<` a `<=` provoca 4 fallos (T3).
- **Cálculo independiente:** los valores esperados de métricas se calculan en el propio test, sin reutilizar `app/services`.

## Fundamentación

| Decisión | Fuente oficial o evidencia |
|---|---|
| `placeholderData: keepPreviousData` mantiene los datos mientras cambia la clave | [TanStack Query · Paginated queries](https://tanstack.com/query/latest/docs/framework/react/guides/paginated-queries) |
| Ruta diferida con `lazy` que devuelve `Component` | [React Router · Route object](https://reactrouter.com/start/data/route-object); `HydrateFallback` como propiedad estática comprobada en los tipos instalados (`react-router@8.4`, `index-react-server.d.ts`) |
| `CORSMiddleware` con orígenes explícitos | [FastAPI · CORS](https://fastapi.tiangolo.com/tutorial/cors/) |
| `useGrouping: 'always'` para mostrar «1.319» en `es-ES` | [MDN · Intl.NumberFormat](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat/NumberFormat) (por defecto `auto`) |
| `<header>` dentro de `<main>` no es `banner` | [HTML-AAM](https://www.w3.org/TR/html-aam-1.0/): se mapea a `sectionheader`; por eso la cabecera del detalle es una región con nombre |
| Rutas incluidas de FastAPI 0.141 envueltas en `_IncludedRouter` | Código instalado `fastapi/routing.py`; por eso los tests enumeran rutas con OpenAPI |
| Clic en Recharts (`activeIndex`) y `initialDimension` | Tipos instalados `recharts@3.10.1` (`synchronisation/types.d.ts`, `ResponsiveContainer.d.ts`) |
| Exportación `@testing-library/jest-dom/vitest` y `vitest/config` | `package.json#exports` de los paquetes instalados |

## Registro de duda

| Afirmación | Asunción | Duda | Reconciliación | Conclusión |
|---|---|---|---|---|
| El listado cuenta lo mismo que el elemento pulsado | Métricas y listado comparten filtros | ¿Redondeos de tasas o filtros por ID tras FE008? | Tests cruzados con enteros exactos; Chrome 7/7 antes y después de FE008 | Se cumple |
| Las opciones rápidas de periodo son coherentes con el periodo por defecto | El «hoy» del navegador es la fecha de referencia del backend | Con `DATA_REFERENCE_DATE` fijada, ¿qué pasa? | Runtime: «7 días» pedía septiembre con datos hasta junio (volumen 0) | **Bug 1**, corregido |
| Los widgets manejan todos los estados | Si no hay datos, están cargando | ¿Y si la API devuelve 4xx/5xx? | Runtime: esqueleto permanente con `?queue=Particulares` | **Bug 2**, corregido |
| `scrollIntoView` solo desplaza el chat | El navegador limita el scroll al contenedor | ¿Mueve la ventana? | La captura mostró la ventana desplazada | Cambiado a `scrollTo` del contenedor (T8); `scrollY` = 0 verificado |
| La variación en % sirve para todos los KPIs | Los valores anteriores están lejos de 0 | ¿Y el índice de sentimiento? | −0,00 → 0,03 daba un +10.606 % | Solo `delta` absoluto para `índice` (T3) |
| El FCR es comparable entre periodos | Hay 7 días de ventana tras cada conversación | ¿Y los últimos 7 días del dataset? | Esa ventana no está completa | Limitación documentada en la [arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md) |

## Bugs encontrados en la verificación

| Bug | Causa raíz | Corrección | Test de regresión |
|---|---|---|---|
| Con `DATA_REFERENCE_DATE` fijada, «Últimos 7/90 días» devolvía 0 conversaciones | Dos fuentes de verdad para «hoy»: el backend usa la fecha de referencia y el front la fecha del navegador. Los tests no lo veían porque fijan la referencia en la fecha actual | `GET /api/catalog` expone `reference_date` y el front calcula las opciones rápidas con ella | `test_catalog_exposes_reference_date_used_by_default_periods`; «las opciones rápidas de periodo usan la fecha de referencia del backend…» |
| Un error de la API dejaba los widgets cargando indefinidamente; por ejemplo, un enlace antiguo con nombre de cola tras FE008 | Los widgets solo comprobaban `data` y nunca `isError` | Aviso «No se han podido cargar los datos…» en tarjetas y gráficos | «si la API rechaza los filtros, los widgets muestran un aviso…» |

Ambos se reprodujeron en Chrome antes de corregirlos: volumen 0 y 1 esqueleto sin avisos. Después de corregirlos: 74 conversaciones en «7 días» y 6 avisos.

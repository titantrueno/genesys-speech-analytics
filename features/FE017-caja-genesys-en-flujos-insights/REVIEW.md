# FE017 — Review

> Fase `/review` (2026-10-13). Revisa los commits `5f23ca0`…`6bcc583` de la [spec](spec.md), con la evidencia de [VERIFY.md](VERIFY.md). Siguiente paso: `/ship`.

## Alcance y evidencia

- **Tamaño:** unas 1.500 líneas de código de producción (sin tests ni `openapi.yaml`), muy por encima de las ~100 líneas revisables por lote. Ya están partidas en 8 commits atómicos, uno por tarea del [plan](plan.md), cada uno con sus tests en verde. Se revisa commit a commit y no se propone partir más.
- **Evidencia:** [VERIFY.md](VERIFY.md) registra la auditoría del vault (`python scripts/audit_vault.py`, código 0), la cobertura de los 21 criterios, nueve mutaciones, fuentes oficiales, el recorrido en Chrome contra Genesys real y `./scripts/ci.sh` con código 0.

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| 1 | Corrección | minor | Si la descarga de la caja deja de existir a mitad (por ejemplo, al borrar el flujo de insights, que la borra en cascada), el nodo decía «The ingestion service is not available» aunque la ingesta respondía. | **Resuelto:** el nodo conserva el motivo real (`… is not available (404)`). Test `test_a_download_that_disappears_says_so`. |
| 2 | Adherencia a la spec | minor | Detrás de la caja, el resumen de filtros del Sampling decía «Todas las conversaciones del periodo», pero ahí no hay periodo (criterio 14). | **Resuelto:** «Todas las conversaciones de la descarga» cuando no hay condiciones. `DownloadBox.test.tsx` lo comprueba y falla sin la corrección. |
| 3 | Seguridad | minor | La ruta interna `POST /insight-downloads` no limitaba el intervalo. Solo la llama la API con su token interno y la API ya resuelve intervalos válidos. | **Resuelto** por defensa en profundidad: máximo de 90 días, como FE011 (test en `test_insight_downloads_pg.py`). |
| 4 | Simplicidad | nit | En `NodePanel.tsx`, el comentario del Prompt de entrada quedó separado de su código al insertar `afterDownload`. | **Resuelto.** |
| 5 | Corrección | minor | Un corte de red puntual al consultar el estado de la descarga termina la ejecución en `error`, en vez de reintentar. | **Aceptado:** coincide con el criterio 6 («la ingesta cae → error»). La descarga sigue en la ingesta y su log queda disponible. Un reintento con espera sería otra feature. |
| 6 | Corrección | minor | Con varios procesos de API (`uvicorn --workers N`), cada uno tendría su programador y lanzaría la misma ejecución. | **Aceptado:** la API se arranca en un solo proceso (`dev.sh`, README), igual que el programador de la ingesta (ADR-008). La asunción está en la spec y en el ADR-008. |
| 7 | Rendimiento | minor | Mientras dura la descarga, la ejecución ocupa un hilo de la API (tarea en segundo plano síncrona) y sondea cada 2 s. Muchas ejecuciones end-to-end a la vez podrían agotar el *pool* de hilos. | **Aceptado:** ya pasaba con los Prompt largos (FE013). Está en los riesgos del plan. Mover el ejecutor a una cola sería otra feature. |
| 8 | Rendimiento | minor | Para pintar el estado de cada flujo, el listado lo valida, y un Sampling con «All conversations» sin caja cuenta sus conversaciones en cada carga. | **Aceptado:** una consulta tarda menos de 500 ms con el dataset completo (tests de rendimiento) y solo afecta a esos Samplings. Si hiciera falta, se cachearía por versión del dataset. |
| 9 | Corrección | minor | Con origen «Sintético», un flujo programado deja cada hora una ejecución en `error` en el historial, que solo guarda 50 ejecuciones por flujo. | **Aceptado:** es lo que pide el criterio 9 (registrar el error con sus motivos) y lo documenta el runbook. Para pararlo basta con desactivar la caja o la programación. |
| 10 | Adherencia a la spec | minor | El panel de la caja no muestra junto a cada campo los errores `422` del guardado (criterio 12). Sí muestra el conflicto «programada con intervalo específico» y los rangos como pista; el resto llega en el aviso general del editor con la ruta del campo. | **Aceptado:** como un intervalo o una programación a medio escribir se guardan como «sin configurar», los valores fuera de rango son el único caso. El aviso general ya lo explica. Marcar el campo exigiría llevar las rutas `nodes[i].config.*` a cada panel; fuera de esta feature. |
| 11 | Seguridad | — | **OWASP:** las rutas de reenvío (`…/download`, `…/download/log`) toman el `1RN` de la descarga de la ejecución guardada en el servidor, no de la petición, así que no hay IDOR. Exigen `flows:view`; lanzar y programar exigen `flows:edit`. Los cuerpos internos se validan con modelos estrictos (`extra="forbid"`). Los identificadores van con `quote()`. Los secretos y tokens de Genesys no salen en la ejecución, la descarga ni el log (tests de ingesta y de punta a punta). | Sin hallazgos. |
| 12 | Seguridad | minor | «All conversations» no tiene tope: un flujo puede enviar miles de conversaciones a un LLM de pago. | **Aceptado** por decisión de la spec: aviso `large_sample` por encima de 1.000, que menciona el coste si hay un proveedor real. |
| 13 | Conocimiento | — | ADR-008, la arquitectura, el contrato de la API, el runbook de la ingesta, el glosario y las lecciones están actualizados y enlazan la spec. Los textos nuevos de los hallazgos 1–3 no cambian el contrato ni el vault. | Sin hallazgos. |
| 14 | Conocimiento | minor | Configuración → Fuentes de datos sigue diciendo que el origen «se pierde al reiniciar la API», cuando FE015 ya lo persiste. Anterior a FE017. | **Aceptado fuera de alcance;** se propone corregirlo en una feature pequeña. |
| 15 | Corrección | minor | `ConversationsPage.test.tsx › muestra los filtros activos como chips eliminables` falló una vez en el gate (carrera con la carga del catálogo). Anterior a FE017; pasó en las demás pasadas. | **Aceptado fuera de alcance;** se propone estabilizarlo esperando al catálogo. |

No hay hallazgos **critical** ni **major**.

## Ejes sin hallazgos adicionales

- **Corrección:** el ejecutor resuelve el intervalo al lanzar, ningún nodo empieza antes de que termine la descarga, el subconjunto es exactamente lo insertado o actualizado, y el programador lanza como mucho una vez por hora y no recupera las ejecuciones perdidas (mutaciones detectadas en [VERIFY.md](VERIFY.md)).
- **Simplicidad:** intervalo y programación tienen una sola implementación (`app/flows/download_config.py`), compartida por la ingesta y la API. Los campos del front se comparten entre el flujo de descarga y la caja, y el visor de log, entre las dos páginas. El descargador sigue el patrón de `AnalysisWriter`.

## Gate

- `./scripts/ci.sh` tras resolver los hallazgos 1–4: **código 0**. Vault con 0 errores; backend 1235 tests (dos semillas) y 203 con PostgreSQL; OpenAPI al día; front 47 ficheros y 597 tests, lint y build; auditoría de dependencias.
- **Veredicto:** aprobable. No quedan hallazgos critical ni major; los minor aceptados están justificados arriba.

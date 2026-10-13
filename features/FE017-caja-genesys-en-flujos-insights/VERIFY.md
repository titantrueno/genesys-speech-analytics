# FE017 — Verificación

> Evidencia de `/build` T8 (2026-10-13): recorrido en Chrome contra la API real y la cuenta de Genesys del laboratorio, y gate. La verificación escéptica completa es `/test`.

## Recorrido en Chrome (criterio 21)

Entorno: `./scripts/dev.sh` con puertos propios (API 18000, ingesta 18001, LLM 18002, web 15173), PostgreSQL de desarrollo, origen de datos «Real», interfaz en inglés (configuración guardada), usuario `admin`. Flujo creado para la prueba: «FE017 verificación end-to-end» (`1FL-F0DA2F92-D1C2-4D91-9422-761DBABB897F`).

| Paso | Resultado |
|---|---|
| Arrastrar «Genesys download» de la paleta al lienzo | La caja aparece con su tarjeta («Today · Voice + Chat · Manual only») y su panel. La paleta la deshabilita: «A flow can only have one Genesys download.» |
| Arrastrar Sampling, Prompt y Output y conectar caja → Sampling con el ratón | Conectado. El panel del Sampling oculta las fechas, explica que las conversaciones las da la descarga y la estimación dice «The number of conversations depends on the download.» |
| Marcar «All conversations» | Se ocultan método y tamaño; la tarjeta dice «All conversations». |
| Conectar la caja con el Prompt | Rechazado: «Cannot connect: A Genesys download can only be connected to a Sampling.» |
| Validar el flujo incompleto | Solo «Prompt 1: missing template» y «Output 1: missing destination name»; la caja y el Sampling son válidos. |
| Prompt de texto con Gemini 3.5 Flash-Lite y Output «Save to conversation fields» → Summary | «The flow is valid». |
| Guardar y recargar | El lienzo se reconstruye idéntico. |
| Ejecutar con «Today» (13/10, sin conversaciones en la cuenta) | La caja consulta Genesys (log: «Chunk 1/1 (13/10/2026 00:00 – 13/10/2026 20:59 (Europe/Madrid)): 0 conversations»), queda en OK con 0 encontradas, y Sampling, Prompt y Output quedan «Skipped» con «The download returned no conversations». Ejecución OK en 2,2 s, sin llamar al LLM. |
| Programar cada 1 hora y volver al listado | «Next run: Oct 13, 10:00 PM». |
| Historial | Columna «Origin» con «Manual». |
| Ejecutar con «Yesterday» y «Overwrite» (decisión de la persona usuaria, que aceptó borrar el análisis del LLM de las 13 conversaciones del 12/10) | La caja pasa por «Running» con los contadores creciendo (1 → 5 → 13 de 13) mientras el resto espera; descarga «With warnings» (13 encontradas, 13 guardadas). Sampling 13, Prompt 13/13, Output: 11 escritas y 2 rechazadas («The conversation has no transcript: it is not sent to the LLM», las dos llamadas sin transcripción). Ejecución OK en 29,4 s. |
| Abrir una conversación desde la tabla | El detalle muestra el summary nuevo de Gemini y «Back to the run»; el resto del análisis queda «Pending» porque «Overwrite» lo borró. |
| Ver el log de la descarga desde la ejecución | Se abre el visor de log con las entradas de búsqueda, descarga, normalización, análisis y carga. |
| Consola del navegador y logs de la API y la ingesta | Sin errores de consola desde que se empezó a capturar (a mitad del recorrido) y sin errores ni trazas en `.dev-logs/api.log` ni `.dev-logs/ingestion.log`. |

### No cubierto en el navegador

- **Solo lectura con `flows:view`:** ningún usuario demo tiene solo ese permiso; lo cubren `DownloadBox.test.tsx` (panel deshabilitado) y `test_flow_scheduler.py` (`403` al guardar y ejecutar).
- **Ejecución programada real:** antes de llegar a las 22:00 se volvió a «Manual only» para que el programador no repitiera la descarga con «Overwrite». La cubre `test_flow_scheduler.py` con reloj simulado.

### Observaciones

- **Cosmético, anterior a FE017:** el resumen de filtros de un Sampling detrás de la caja dice «All conversations in the period», aunque detrás de la caja no hay periodo.
- **Cosmético, anterior a FE017:** la tarjeta «Data origin» de Configuración sigue diciendo que el origen «se pierde al reiniciar la API», cuando FE015 ya lo persiste.
- **Incidencia de la prueba:** al parar el entorno de prueba, `dev.sh` paró el contenedor de PostgreSQL que compartía con el entorno de la persona usuaria (otro `dev.sh` en 8000/8001/5173). Se volvió a levantar en el momento con `docker compose up -d --wait postgres`; el volumen se conservó.

## Gate

- `python scripts/audit_vault.py`: 58 archivos, 0 errores.
- Backend: 1231 tests (dos semillas) y 203 tests con PostgreSQL, en verde.
- Front: en la primera pasada de `./scripts/ci.sh` falló `ConversationsPage.test.tsx › muestra los filtros activos como chips eliminables` (el chip mostraba el código `cajeros` en vez de «Incidencia en cajero»: carrera con la carga del catálogo). FE017 no toca esa página y el test pasó 3 de 3 por separado.
- **Segunda pasada de `./scripts/ci.sh`: código 0.** Vault, backend (1231 + 1231 con otra semilla + 203 con PostgreSQL), OpenAPI al día, front (597 tests, lint y build) y auditoría de dependencias.

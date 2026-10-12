# FE011 — Verificación

> Tarea T8 del [plan](plan.md): prueba con las conversaciones del día y recorrido en Chrome. Fecha: 2026-10-12. Artefactos: [spec](spec.md) · [plan](plan.md). La evidencia automatizada de cada criterio está en la sección «Progreso» del plan (T1–T7b). La fase `/test` completará este documento con la tabla por criterio.

## Resultado

**Verde para los criterios 26, 27 y 28.** El recorrido encontró un problema de presentación, ya corregido con su test: el log mostraba los instantes en ISO UTC con microsegundos. Ver «Hallazgos».

## Entorno

- **PostgreSQL** (Colima) con la base `speech_analytics`, que ya contenía las conversaciones de las pruebas de humo de la T4 y la T6.
- **Procesos en puertos propios:** servicio de ingesta en el 18001, API en el 18000 (`INGESTION_URL=http://localhost:18001`) y web en el 15173 (`API_PROXY_TARGET=http://localhost:18000`). Se arrancaron y pararon por PID, sin tocar los procesos de la persona usuaria.
- **Genesys:** la cuenta real del laboratorio (organización «SGTO», `eu-west-1`), en solo lectura.
- **Navegador:** Chrome real con la extensión Claude in Chrome, en una pestaña nueva que se cerró al terminar.

## Criterios 26 y 27: conversaciones del día

| Comprobación | Resultado |
|---|---|
| Conversaciones terminadas de hoy en Genesys (voz y chat), consulta de analítica | **13**, ninguna omitida |
| Conversaciones de hoy guardadas en PostgreSQL | **13**, el mismo conjunto de identificadores |
| Tipos presentes | Los 7 de la tabla de la spec |
| Repetir la descarga (manual a las 15:51 y programada a las 16:00, sobre las de la T4 y la T6) | 0 insertadas y 13 actualizadas en cada una. Las filas se mantienen: 13 conversaciones, 131 turnos, 48 tramos y 32 temas |

Valores del criterio 27, leídos con `GET /conversations/{id}` del servicio de ingesta en marcha:

| Referencia | Comprobado | Resultado |
|---|---|---|
| `37dcbccf` voz contenida en el bot | 12 turnos (9 del bot y 3 del cliente); ANI, DNIS y `externalTag`; flujo «Sierra VoiceAgent»; contenida; colgó el cliente (`endpoint`); 4 temas con su frase; completa | OK |
| `7b94988a` voz bot → agente | Turnos del bot antes de la transferencia y del agente después; derivada, con 218,1 s en el bot; cola `AIT_Transcription`; agente «Javier Del Olmo»; wrap-up; 8 temas; confianza del agente menor que la del bot | OK |
| `8d29170a` chat con agente | 16 turnos (uno por mensaje); métricas de chat; 2 temas; sin ANI ni acústica | OK |
| `f7e79502` chat bot → agente | 3 turnos del bot antes del agente; derivada; 3 mensajes del bot | OK |
| `9e3ec75a` mensaje no entregado | Un único turno no entregado: agente, «lo estoy revisando, un segundo» | OK |
| `c870bc58` chat con reconexión | Dos tramos de agente con su wrap-up; reconexión; 5 turnos del cliente y 4 del agente; sin errores por el `404` | OK |
| `687f2225` voz con agente sin frases | Parcial; agente y wrap-up resueltos; tiempo de conversación | OK |

## Criterio 28: recorrido en Chrome

**Con `admin`:**

1. **Configuración → Fuentes de datos:** la tarjeta «Genesys Cloud · datos reales» muestra el servicio disponible, `eu-west-1`, credenciales configuradas, la última descarga («Con avisos»), 13 conversaciones (voz 7 · chat 6) y su calidad (completa 9 · parcial 2 · sin transcripción 2). Los conectores mock de FE005 siguen encima, sin cambios.
2. **«Probar conexión»:** devuelve «Conexión correcta con Genesys Cloud: SGTO (eu-west-1)», y «Última prueba» pasa a «Correcta · 12 oct, 15:50 · SGTO».
3. **Flujos de insights:** el listado muestra las columnas «Tipo» y «Próxima ejecución». «Nuevo flujo» con el tipo «Descarga de transcripciones» crea «Descarga de hoy» y abre su formulario («Hoy», voz y chat, «Solo manual»).
4. **«Ejecutar ahora»:** abre la ejecución «En curso», con el progreso (1 de 13…) y el log en vivo. Termina en «Con avisos»: 13 de 13 descargadas, 0 insertadas y 13 actualizadas, voz 7 · chat 6, completa 9 · parcial 2 · sin transcripción 2, 2 mensajes no entregados, 14,4 s. El log tiene los 6 avisos esperados, cada uno con su conversación: 2 sin transcripción, 2 parciales y 2 con mensajes no entregados.
5. **Log:**
   - el filtro «Aviso» deja solo esos 6;
   - el log en texto (`format=text`) responde `200` con 14 líneas.

   No se pulsó «Descargar log», para no guardar un fichero en el equipo sin preguntar. La descarga del fichero está cubierta por los tests del front, y sus cabeceras se comprobaron con curl en la T5 y la T6.
6. **Historial:** muestra la ejecución, y su fila la vuelve a abrir.
7. **Programación:** se cambia a «Cada N horas» con 1. La cabecera pasa a «Cada hora · próxima ejecución: 12 oct, 16:00».
   - **El programador lanzó la ejecución a las 16:00:04** (origen «Programada»), que terminó en «Con avisos» con 13 encontradas y 13 actualizadas.
   - La siguiente quedó a las 17:00.
   - Después se devolvió el flujo a «Solo manual», para que no siga descargando.
8. **Servicio de ingesta parado** (se paró solo el proceso del 18001):
   - el listado muestra el aviso «Las descargas de Genesys no están disponibles: el servicio de ingesta no responde», con los flujos de insights a la vista;
   - un flujo de insights se crea y su editor abre con normalidad;
   - la tarjeta de Genesys dice «El servicio de ingesta no responde».

**Con un rol que solo tiene `flows:view`** (rol `lector_flujos` y usuaria creados por la API, en memoria): el listado no tiene «Nuevo flujo» ni columna «Acciones»; el formulario está deshabilitado y sin «Guardar»; no hay «Ejecutar ahora»; el historial se ve.

**Consola:** sin errores en ninguna pantalla.

## Hallazgos

| Hallazgo | Arreglo |
|---|---|
| El log mostraba los instantes en ISO UTC con microsegundos: «Ejecución manual de 2026-10-11T22:00:00+00:00 a 2026-10-12T13:51:16.515358+00:00» | Los instantes del inicio y de los tramos se escriben en la zona horaria del flujo y al minuto: «12/10/2026 00:00 – 12/10/2026 15:51 (Europe/Madrid)». El test `test_the_log_shows_instants_in_the_flow_timezone_without_microseconds` falló antes del cambio y pasa después. |

## Estado que queda

- **PostgreSQL** contiene las 13 conversaciones de hoy y dos flujos de descarga: «Prueba de humo T4» (T4) y «Descarga de hoy» (T8), los dos «Solo manual», con sus ejecuciones.
- **Todo lo que viva en la memoria de la API se perdió al pararla:** el flujo de insights de prueba, el rol `lector_flujos` y su usuaria.
- **Procesos:** ninguno de la prueba sigue en marcha. PostgreSQL sigue arrancado.

# FE011 — Ingesta de conversaciones de Genesys

> Estado: **aprobada** el 2026-10-12. Revisada el mismo día con los sondeos de las 13 conversaciones de hoy en la cuenta del laboratorio: voz con bot, voz con bot y agente, y chats con y sin bot. Depende de FE004 (flujos y ejecuciones), FE005 (configuración, conectores y auditoría) y FE006 (permisos). Aplica FE008 y FE009.
>
> **Dividida el 2026-10-12** a petición del usuario: esta feature descarga, normaliza y guarda las conversaciones reales. Usarlas en la plataforma (cambiar entre datos sintéticos y reales, ver su analítica en el detalle, el listado, el explorador y los dashboards) es [FE012](../FE012-switch-entre-datos-sinteticos-reales/spec.md).

## Objetivo

Un servicio de ingesta nuevo descarga de Genesys Cloud las transcripciones y la analítica de las conversaciones de voz y chat, las normaliza y las guarda en PostgreSQL. Se lanza desde un tipo de flujo nuevo, «Descarga de transcripciones», a mano o con una programación, y cada ejecución deja un log.

## Decisiones de la entrevista (2026-10-12)

- **Base de datos:** PostgreSQL en Docker (`docker compose`). Es la primera persistencia del proyecto: [ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md) la había pospuesto.
- **Nuevo backend:** un servicio aparte (un proceso FastAPI propio) que es el **único** que lee las credenciales de Genesys y llama a su API. El front solo habla con la API actual, que comprueba la sesión y los permisos y delega en el servicio de ingesta con un token interno.
- **Qué se descarga:** la transcripción **y la analítica** de cada conversación. La analítica incluye:
  - los teléfonos (ANI y DNIS), las colas, el agente y el `externalTag`;
  - el flujo de IVR o bot, el wrap-up y quién colgó;
  - los tiempos (IVR, espera, conversación, retención, ACW), la calidad de la llamada y las métricas del chat;
  - los datos de Speech & Text Analytics: temas, reparto del tiempo por hablante y silencio, sentimiento y empatía.

  En los chats se descargan también **los mensajes**, incluidos los no entregados, con su texto, mediante la API de mensajes.
- **Datos sensibles:** en este desarrollo, el **teléfono** y el **`externalTag`** no son datos sensibles: se guardan sin enmascarar. El enmascarado del texto de las transcripciones lo trata FE012.
- **Análisis:** solo se guarda lo que da Genesys. Summary, main topic de la taxonomía del banco, CSAT, resolución y cumplimiento quedan **pendientes de análisis**. El modelo y el pipeline se diseñan para que la siguiente fase los rellene con un LLM, sin migrar datos.
- **Ejecución:** el tipo de flujo **«Descarga de transcripciones»** tiene un intervalo relativo o específico y se lanza a mano («Ejecutar ahora») o con una programación periódica. Cada ejecución tiene log.
- **Pruebas con datos reales:** se hacen con las **conversaciones del día** de la cuenta del laboratorio, porque en las últimas semanas hubo incidencias con las grabaciones y, por tanto, con las transcripciones. El sondeo confirma que el cliente OAuth tiene todos los permisos necesarios (ver «Riesgos y asunciones»).

## Conceptos

- **Servicio de ingesta:** proceso nuevo (carpeta y puerto a decidir en `/plan`, por ejemplo `ingestion/` en el 8001) con el pipeline `extraer → normalizar → cargar → analizar`. En esta fase, la etapa `analizar` deja el análisis en `pendiente`.
- **Analítica de Genesys:** lo que Genesys da de una conversación además de sus turnos (criterio 8). Se guarda **separada del análisis** de la plataforma (summary, main topic, CSAT…), que es lo que rellenará el LLM.
- **Tramo:** cada paso de una conversación por un participante: flujo de entrada, IVR o bot, cola o agente. Una conversación puede tener varios tramos del mismo tipo, por ejemplo cuando el cliente vuelve a escribir al mismo chat.
- **Flujo de descarga** (`1FL`, tipo `descarga`): un flujo con nombre, intervalo, canales y programación, sin lienzo. Convive con los flujos de insights de FE004 (tipo `insights`) en la misma sección.
- **Ejecución de descarga** (`1RN`): una ejecución de un flujo de descarga, con su origen (`manual` o `programada`), sus contadores y su log.
- **Entrada de log:** una línea de una ejecución con fecha, nivel (`info`, `aviso` o `error`), etapa y mensaje. No es una entidad.
- **Conversación real** (`1CO`): una conversación normalizada, con su identificador de Genesys, sus turnos, la analítica de Genesys, el análisis (vacío y `pendiente` en esta fase) y las respuestas originales de Genesys, para poder reanalizarla.
- **Calidad de la transcripción:** `completa`, `parcial` o `sin_transcripcion` (criterio 7).

## Tipos de conversación observados (2026-10-12)

Según los sondeos de solo lectura de las 13 conversaciones de hoy, la ingesta tiene que manejar estos tipos. Cada uno tiene una conversación de referencia para los tests y para la prueba real (criterios 26 y 27).

| Tipo | Referencia | Lo que la caracteriza |
|---|---|---|
| **Voz contenida en el bot** | `37dcbccf-2d89-424e-bc9e-9e53d8494a9a` | El cliente habla con el agente de voz con IA (flujo `Sierra VoiceAgent`) y nunca entra en una cola. Las frases del bot llegan como `internal`, sin `userIds`. El cliente cuelga dentro del flujo (`exitReason: DISCONNECT`). |
| **Voz bot → agente** | `7b94988a-807b-4a59-8767-ed445ba9f12b` | 218 s con el bot, transferencia a la cola `AIT_Transcription` (`exitReason: TRANSFER`) y 51 s con un agente, con wrap-up. La comunicación del cliente devuelve **tres** transcripciones: una vacía, la del tramo del bot (34 frases) y la del tramo del agente (6 frases). Las frases `internal` del agente traen `userIds` y las del bot no. El tramo del agente tiene sentimiento y empatía, pero está mal transcrito («see can second»). El participante agente no trae nombre. |
| **Voz con transcripción parcial o vacía** | `687f2225…`, `762c914d…` y dos llamadas del bot | El agente o el bot hablaron, según las métricas, pero no tienen frases, por las incidencias de grabación. |
| **Chat solo con agente** | `8d29170a-20f1-4421-8150-0075a8dd27d5` | Mensajería web (`webmessaging`): el flujo de entrada `AIT_ChatSim_Inbound` (`workflow`) no escribe y transfiere a la cola y al agente. La transcripción parte cada mensaje en frases, que comparten `messageID` e instante. Tiene temas y sentimiento. No trae ANI, `externalTag` ni acústica, pero sí métricas propias del chat (primera respuesta, tiempos medios de respuesta, nº de mensajes). |
| **Chat bot → agente** | `f7e79502-c16d-4b7a-9fd6-a9b2ae145bd6`, `90116482-f12f-466f-a7ba-2c7c96a975c3` | El flujo de entrada actúa de bot: envía 3 mensajes (saludo, clasificación «Tarjetas y cargos / Reclamaciones / Otras consultas» y «Le paso con un agente») y transfiere a la cola. Sus mensajes no tienen `createdBy` en la API de mensajes, y sus frases no tienen `userIds`. En `90116482`, el agente solo llega a escribir «hola». |
| **Chat con mensaje no entregado** | `9e3ec75a-11c8-4df7-9002-339916be2827`, `d74fc0d8-4ac1-47da-9a8c-d91ce49dfda2` | El agente responde cuando el cliente ya se ha ido. En la transcripción, el mensaje llega como una frase `internal` **vacía**. La API de mensajes lo da como `delivery-failed` y **con su texto** («lo estoy revisando, un segundo»). |
| **Chat con reconexión** | `c870bc58-1f9d-4c89-a7d7-a86b2b32625a` | El cliente vuelve a escribir al mismo chat después de cerrarse. La conversación tiene dos tramos de cliente, flujo, cola y agente, y dos wrap-ups. La transcripción del primer tramo incluye las frases de los dos, y la URL de transcripción del segundo devuelve `404`. Hay temas de queja («Insatisfacción», «Queja», «Remitir a un supervisor») y sentimiento negativo. |

En los 6 chats, los `messageID` de las frases coinciden al 100 % con los identificadores de la API de mensajes.

## Criterios de aceptación

### Base de datos y servicio de ingesta

1. **Arranque:** `docker compose up -d` levanta PostgreSQL con un volumen persistente. El servicio de ingesta crea o actualiza el esquema al arrancar sin perder datos (test: arrancar dos veces conserva las filas). El `README.md` explica cómo arrancar Postgres, el servicio de ingesta, la API y la web.
2. **Esquema normalizado:** tiene tablas de:
   - conversaciones, tramos, turnos y participantes;
   - catálogos de colas, agentes, flujos, códigos de wrap-up y divisiones, con su identificador de Genesys y su nombre;
   - analítica (criterio 8) y temas detectados;
   - análisis, con `estado` (`pendiente`, `completo` o `error`) y `fuente` (`genesys` o `llm`);
   - flujos de descarga, ejecuciones y entradas de log.

   Cada conversación guarda las respuestas originales de Genesys: detalle de analítica, Speech & Text Analytics, transcripciones y, en chat, mensajes. El servicio expone una lectura interna `GET /conversations/{id}` (por `1CO` o por identificador de Genesys) que devuelve la conversación normalizada. La usan los tests y la prueba real, y la usará FE012.
3. **Credenciales:** solo el servicio de ingesta lee `GENESYS_CLIENT_ID`, `GENESYS_CLIENT_SECRET` y `GENESYS_REGION` del `.env` de la raíz, que sigue ignorado por git. Ningún log, respuesta de la API, entrada de auditoría, fila de la base de datos ni mensaje de error contiene el secreto, el token de acceso ni las URL firmadas de descarga de las transcripciones. Un test fuerza errores de autenticación y de API y busca esos valores en todas las salidas. La API arranca y sus tests pasan sin esas variables.
4. **Autenticación con Genesys:** usa *client credentials* contra la región configurada (`eu-west-1` → `mypurecloud.ie`, con una tabla de regiones en el código).
   - El token se reutiliza hasta poco antes de caducar y se renueva solo (test con un reloj simulado).
   - Con credenciales incorrectas, la ejecución acaba en `error` con «Credenciales de Genesys no válidas», sin reintentos.
   - Un `403` en una llamada a Genesys se registra con la ruta y el permiso que falta, y no se reintenta.
5. **API del servicio de ingesta:** solo acepta peticiones con el token interno compartido con la API (test: sin token, `401`). No se expone al navegador: CORS cerrado y documentado. Tiene su propio OpenAPI.

### Extracción y normalización

6. **Extracción:**
   - Busca las conversaciones del intervalo con la consulta de detalles de analítica. Parte el intervalo en tramos de **7 días como máximo** (límite de la cuenta del laboratorio) y pagina hasta el final (test con un intervalo de 20 días y varias páginas).
   - Solo procesa conversaciones **terminadas** de los canales pedidos: voz (`voice`) → `voz`, y mensajería o chat (`message`, `chat`) → `chat`. Una conversación en curso se omite y se recogerá en una descarga posterior. El resto de medios también se omite. Ambos casos se cuentan.
   - Para cada conversación descarga el resumen de Speech & Text Analytics y **todas** las transcripciones de cada comunicación del cliente, en voz y en mensajería (la misma API sirve para las dos).
     - Una transcripción repetida se identifica por su `transcriptId`.
     - Si una comunicación responde `404` y sus frases ya llegaron en la transcripción de otra (la reconexión), no es un error.
   - En chat, descarga además **todos los mensajes** con la API de mensajes (lectura en bloque): texto, dirección, instante, estado de entrega y autor.
   - Ante un `429` respeta `Retry-After`. Ante un `5xx` o un fallo de red reintenta hasta 3 veces con espera creciente. Si una conversación sigue fallando, se registra el error y la ejecución continúa (test con un Genesys falso que devuelve cada caso).
7. **Turnos y calidad de la transcripción:**
   - **Voz:** cada frase de la transcripción es un turno. Las frases de todas las transcripciones de la conversación se unen sin duplicados y se ordenan por instante (tests con `7b94988a` y con una transcripción vacía).
   - **Chat:** cada **mensaje** de la API de mensajes es un turno, con su texto completo, en orden de instante.
     - Un mensaje no entregado (`delivery-failed`) es un turno con su texto, marcado como **no entregado** (test con `9e3ec75a`: el turno del agente «lo estoy revisando, un segundo» aparece como no entregado).
     - El sentimiento y los temas de la transcripción se enlazan al turno por `messageID`.
     - Si la API de mensajes falla, los turnos se construyen con la transcripción, agrupando las frases por `messageID`. Un mensaje sin texto cuenta entonces como no entregado sin texto, y se anota un aviso en el log.
   - **Offsets:** los instantes de Genesys son absolutos (milisegundos desde 1970). El offset de un turno es su instante menos el inicio de la conversación, en segundos, y nunca es negativo: en chat, los primeros mensajes llegan unas décimas antes del inicio y se fijan en 0.
   - **Hablantes:**
     - Voz: `external` → `cliente`. Una frase `internal` es del `agente` (el de su `userIds`) si los trae, y del `bot` si no. Si no hay `userIds`, decide el tramo en el que cae la frase.
     - Chat: un mensaje entrante es del `cliente`, uno saliente con autor (`createdBy`) es del `agente` que lo escribió, y uno saliente sin autor enviado por el flujo de entrada es del `bot`.
     - Los eventos del sistema → `sistema`.
     - Tests: en `37dcbccf`, todas las frases `internal` son del bot. En `7b94988a`, son del bot hasta la transferencia y del agente después. En `f7e79502`, los 3 primeros mensajes salientes son del bot y el resto, del agente.
   - **Sentimiento:** Genesys lo da por frase, solo para las frases que lo tienen (hoy, siempre `-1` o `1`).
     - El turno que contiene una de esas frases toma su valor; si son varias (un mensaje de chat), su media.
     - El resto de turnos de una transcripción con análisis de sentimiento son neutros (`0`).
     - Si la transcripción no tiene sentimiento, el turno tampoco.
   - **Calidad de la transcripción:**
     - `sin_transcripcion`: no hay turnos con texto.
     - `parcial`: un participante intervino según las métricas (un agente de voz con tiempo de conversación o un bot con su tramo), pero no tiene turnos.
     - `completa`: el resto. Los chats son `completa` cuando la API de mensajes responde.

     Las dos primeras dejan un aviso en el log, y la conversación se guarda igualmente, con su analítica.
8. **Analítica de Genesys:** por conversación se guarda lo siguiente, con un test por grupo de campos.
   - **Conversación:** identificador de Genesys, `externalTag`, dirección de origen, inicio, fin, duración, divisiones, MOS mínimo y R-factor.
   - **Teléfonos:** ANI (teléfono del cliente) y DNIS (número marcado), sin el prefijo `tel:` y sin enmascarar. Solo en voz.
   - **Recorrido:** la secuencia de tramos con su tipo (`cliente`, `flujo_entrada`, `ivr`, `cola`, `agente` o `externo`), su nombre, inicio y fin, incluidos los tramos repetidos de una reconexión. De ella salen:
     - las colas por las que pasa la conversación;
     - el agente o los agentes;
     - cada flujo de IVR, bot o mensajería, con su nombre, tipo, versión, motivo de entrada y de salida, destino de la transferencia e idioma final.
   - **Cierre:**
     - los códigos de wrap-up de cada tramo de agente (identificador y nombre);
     - quién terminó la conversación (tipo de desconexión del cliente);
     - si hubo transferencia;
     - si hubo **reconexión** (más de un tramo de cliente).
   - **Contención:**
     - `contenida_en_bot`: la conversación terminó en el IVR o el bot sin entrar en una cola;
     - `derivada_a_agente`: el bot la transfirió a una cola; se guarda el tiempo y el nº de mensajes o turnos del bot;
     - `abandonada_en_cola`: entró en una cola y terminó sin que la atendiera un agente.
   - **Tiempos y contadores**, en segundos y en unidades, a partir de las métricas de las sesiones y sumados por tramo:
     - comunes: IVR, flujo, espera en cola, alerta, conversación, retención, ACW y gestión total; ofrecidas, conectadas y transferencias;
     - de chat: primera respuesta del agente, primer contacto, tiempos medios de respuesta del agente y del cliente, y mensajes del cliente, del bot y del agente, entregados y no entregados.

     Una métrica que Genesys no da queda vacía, no a 0.
   - **Speech & Text Analytics:**
     - en voz, el porcentaje del tiempo de agente, cliente, silencio, IVR, ACD y otros;
     - los temas detectados: nombre, frase que lo activó, hablante, turno, offset y confianza;
     - el sentimiento por turno, el sentimiento medio del cliente y la empatía, cuando los haya;
     - en voz, el recuento de los eventos acústicos (voz y silencio por lado) y la confianza media del reconocimiento por hablante, para detectar tramos mal transcritos como el del agente en `7b94988a`.

   Cada nombre (cola, agente, wrap-up, flujo y división) se resuelve con la API de Genesys, con una caché por ejecución. El nombre del agente sale de su `userId`, porque en voz el participante agente no lo trae. Si un nombre no se puede resolver, se guarda el identificador de Genesys en su lugar y se avisa en el log.
9. **Identificadores:** se generan con `backend/app/ids.py`: conversación `1CO`, cola `1QU`, agente `1AG` y cliente `1CU`. Todos son **v5 derivados del identificador de Genesys**, para que repetir una descarga no duplique nada.
   - El `1CU` se deriva del contacto externo, que traen tanto la voz como el chat. Si no lo hay, del ANI; y si tampoco, la conversación queda sin cliente identificado.
   - Un test comprueba que no colisionan con los del dataset sintético.
10. **Carga idempotente:** una conversación ya guardada se actualiza (`upsert` por su identificador de Genesys) con sus turnos, analítica y temas, sin duplicar filas.
    - Ejecutar dos veces el mismo intervalo deja el mismo número de filas en cada tabla, y la segunda ejecución las cuenta como «actualizadas» (test).
    - Cada conversación se guarda en su propia transacción: un fallo en una no deshace las anteriores.
    - Una conversación que antes era `parcial` y ahora llega `completa` se actualiza.
11. **Preparado para el análisis con LLM:** la etapa `analizar` está detrás de una interfaz (`Analyzer`) que recibe los turnos y la analítica de Genesys. La implementación de esta fase deja el análisis en `pendiente`.
    - Un test la sustituye por otra que rellena summary y main topic, y comprueba que la lectura del criterio 2 los devuelve con `fuente: llm` y `estado: completo` sin cambiar el esquema.
    - Es el punto de extensión de la fase siguiente, como `PromptRunner` en [ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md).

### Flujos de descarga

12. **Tipos de flujo:** al crear un flujo en **Flujos de insights** se elige su tipo: «Insights» (el lienzo de FE004, sin cambios) o «Descarga de transcripciones». El listado muestra una columna «Tipo» y, para los flujos de descarga, la próxima ejecución programada.
13. **Configuración de un flujo de descarga:** es un formulario, sin lienzo. El backend lo valida y responde `422` con un mensaje por campo.
    - **Intervalo relativo:** «hoy» (desde las 00:00 en la zona horaria de la plataforma), «ayer», o las últimas N horas (1–720) o días (1–90) hasta el momento de la ejecución.
    - **Intervalo específico:** desde–hasta en la zona horaria de la plataforma, con `desde` anterior a `hasta`, como máximo 90 días y sin fechas futuras.
    - **Canales:** voz, chat o ambos (al menos uno).
    - **Programación:** desactivada, cada N horas (1–24) o diaria a una hora. Solo admite intervalo relativo; con uno específico, responde `422` con «Una descarga programada necesita un intervalo relativo».
    - **Activo:** un flujo desactivado no se ejecuta por programación, pero sí a mano.
14. **Persistencia:** los flujos de descarga, sus ejecuciones y sus logs viven en PostgreSQL y sobreviven a reiniciar la API y el servicio de ingesta (test). Los flujos de insights siguen en memoria, como hoy.
15. **Ejecución manual:** «Ejecutar ahora» crea una ejecución `manual` (`202`) que pasa por `pendiente → en_curso` y termina en `completada`, `completada_con_avisos` o `error`.
    - Si el flujo ya tiene una ejecución en curso, responde `409`.
    - El intervalo relativo se resuelve en el momento de lanzarla y se guarda en la ejecución.
16. **Ejecución programada:** el servicio de ingesta lanza las ejecuciones programadas de los flujos activos a su hora, con origen `programada`.
    - Un test con un reloj simulado comprueba que un flujo «cada 1 hora» se lanza una vez por hora y no dos.
    - Si a esa hora ya hay una ejecución en curso del mismo flujo, se omite y se anota en el log de la siguiente.
    - Las ejecuciones perdidas mientras el servicio estaba parado no se recuperan: la siguiente se lanza a su hora.
17. **Contadores:** cada ejecución informa en todo momento de:
    - el intervalo y la duración;
    - las conversaciones encontradas, descargadas, insertadas, actualizadas, con error y omitidas (en curso o de otro canal);
    - de las guardadas, cuántas hay por canal y por calidad de la transcripción, y cuántos mensajes no entregados.

    Al terminar, `encontradas = insertadas + actualizadas + omitidas + con error` (test).
18. **Log:**
    - Cada etapa (autenticación, búsqueda, descarga, normalización, carga y análisis) escribe entradas con fecha, nivel y mensaje.
    - Cada conversación omitida, con error, con transcripción parcial o ausente, o con mensajes no entregados deja una entrada con su identificador de Genesys y el motivo.
    - La vista de la ejecución muestra el log, se actualiza por polling mientras la ejecución está en curso, filtra por nivel y permite descargar el log en texto.
    - El log no contiene el texto de los turnos ni los secretos del criterio 3: solo identificadores, recuentos y motivos (test).
19. **Historial:** cada flujo de descarga lista sus ejecuciones, de la más reciente a la más antigua, con fecha, origen, intervalo, contadores, duración y estado. Cada una se puede reabrir. Se conservan las 200 más recientes por flujo.
20. **Permisos:**
    - Ver flujos de descarga, ejecuciones y logs exige `flows:view`. Crear, editar, borrar, programar y ejecutar exige `flows:edit`.
    - Un test con un rol que solo tiene `flows:view` recibe `403` en cada escritura.
    - El recorrido de rutas del OpenAPI cubre las rutas nuevas.
21. **Servicio caído:** si la API no alcanza el servicio de ingesta, las rutas de flujos de descarga responden `503` con «El servicio de ingesta no está disponible». El editor de flujos de insights sigue funcionando (test).

### Estado del conector

22. **Fuentes de datos:** la pestaña de Configuración añade, para Genesys Cloud y con `config:view`:
    - si el servicio de ingesta responde;
    - si las credenciales son válidas, con el botón «Probar conexión»;
    - el nombre de la organización y la región;
    - la última descarga;
    - el nº de conversaciones guardadas por canal y por calidad de la transcripción.

    Los conectores mock de FE005 siguen como hoy. El cambio de origen de datos es FE012.

### Calidad

23. `./scripts/ci.sh` termina con código 0.
    - Los tests del servicio de ingesta usan un **Genesys falso** (nunca la cuenta real) y un PostgreSQL efímero. El gate y `.github/workflows/ci.yml` los arrancan.
    - `backend/openapi.yaml` incluye las rutas nuevas.
24. **Fixtures:** las respuestas del Genesys falso salen de las conversaciones reales del 2026-10-12, una por cada tipo de la tabla «Tipos de conversación observados».
    - Conservan ANI y `externalTag`, por decisión de este desarrollo.
    - No contienen tokens, URL firmadas ni identificadores de la organización.
    - Hay un test de normalización por tipo, con los valores de la prueba real (criterio 27).
25. **Rendimiento:** con un Genesys falso sin latencia, una descarga de 1.000 conversaciones se completa en menos de 60 s y su carga no bloquea las lecturas de la API (test).
26. **Prueba con las conversaciones del día:** contra la cuenta real del laboratorio, el mismo día de la prueba, con un flujo de descarga «hoy» de voz y chat. Se comprueba:
    - que todas las conversaciones terminadas del día quedan guardadas y que el recuento coincide con la consulta de analítica de Genesys para ese intervalo;
    - que hay al menos una de cada tipo de la tabla y que la lectura del criterio 2 devuelve cada una como describe el criterio 27;
    - que repetir la descarga no duplica nada.

    Si ese día falta algún tipo, se generan conversaciones de prueba de ese tipo antes de empezar.
27. **Valores esperados** en las conversaciones de referencia (en la prueba del 2026-10-12, o en las fixtures):
    - `37dcbccf`: 12 turnos (9 del bot y 3 del cliente), ANI, DNIS, `externalTag`, flujo «Sierra VoiceAgent», `contenida_en_bot`, colgó el cliente, 4 temas con su frase y calidad `completa`.
    - `7b94988a`:
      - turnos del bot hasta la transferencia y del agente después, en una única secuencia ordenada;
      - `derivada_a_agente`, con unos 218 s en el bot;
      - la cola `AIT_Transcription`, el agente con su nombre y el wrap-up;
      - los temas de los dos tramos y el sentimiento del tramo del agente;
      - la confianza media del agente, menor que la del bot.
    - `8d29170a`: 16 turnos (uno por mensaje, no 30 por frase), métricas de chat, temas y sentimiento del cliente; sin ANI ni acústica.
    - `f7e79502`: 3 turnos del bot, después los del agente; `derivada_a_agente`, con 3 mensajes del bot.
    - `9e3ec75a`: el turno del agente «lo estoy revisando, un segundo» marcado como no entregado.
    - `c870bc58`: dos tramos de agente, dos wrap-ups y reconexión; los mensajes de los dos tramos; ningún error por el `404` del segundo.
    - Una llamada con agente sin frases del agente (`687f2225` o `762c914d`): calidad `parcial`, con aviso en el log y su analítica completa (cola, agente, wrap-up y tiempos).
28. **Recorrido en Chrome** contra la API real.
    - Con `admin`:
      - pulsar «Probar conexión» en Fuentes de datos;
      - crear un flujo de descarga «hoy» de voz y chat, ejecutarlo a mano y seguir el log hasta el final, con avisos de transcripciones parciales y mensajes no entregados;
      - reabrir la ejecución desde el historial y descargar su log;
      - programar el flujo cada hora y ver la próxima ejecución;
      - parar el servicio de ingesta y ver el `503` sin romper el editor de flujos de insights.
    - Con un rol que solo tiene `flows:view`: ver flujos, ejecuciones y logs, sin acciones de edición.
    - Sin errores de consola.

## Conocimiento afectado

- [ADR-002 — Stack Vite, FastAPI y mock](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md): su alternativa «Base de datos (pospuesta)» queda resuelta. Hay que ampliarla y enlazar el ADR nuevo.
- **ADR nuevo (ADR-008):** recoge:
  - PostgreSQL y el servicio de ingesta aparte, con token interno;
  - la analítica de Genesys separada del análisis;
  - la API de mensajes como fuente de los turnos de chat;
  - el análisis pendiente, con `Analyzer` como punto de extensión del LLM.
- [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): componentes nuevos (PostgreSQL y servicio de ingesta), flujos de descarga y el límite «Sin persistencia», que deja de ser cierto para los datos reales.
- [Contrato de la API entre front y back](../../vault/arquitectura/contrato-api-front-back.md): rutas nuevas de flujos de descarga y del estado del conector, el `503` y la API interna del servicio de ingesta.
- [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md): consultado.
  - No hacen falta prefijos nuevos: `1FL` y `1RN` cubren los flujos y las ejecuciones de descarga. Las entradas de log, los tramos, los temas y los flujos de Genesys no son entidades de la plataforma, y se guardan con su identificador de Genesys.
  - Hay que añadir una excepción: los `1CO`, `1CU`, `1AG` y `1QU` de datos reales son **v5 derivados del identificador de Genesys**.
- **Entrada nueva en Producto, «Datos de Genesys para STA»:**
  - qué da Genesys y qué no;
  - los tipos de conversación observados;
  - que los temas de STA de la organización son en su mayoría genéricos («Conexión», «Saludos»);
  - que el sentimiento es por frase y binario.
- [Estado operativo](../../vault/operaciones/estado-operativo.md): los conectores dejan de ser solo mock. Hay que añadir un runbook nuevo para arrancar Postgres y la ingesta, probar la conexión y diagnosticar una descarga con el log (transcripciones parciales por incidencias de grabación y mensajes no entregados).
- [Glosario](../../vault/glosario/terminos-del-harness.md): añadir «servicio de ingesta», «flujo de descarga», «analítica de Genesys», «tramo», «contención en el bot», «transcripción parcial», «mensaje no entregado» y «análisis pendiente».
- [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md): revisarlas al planificar, en especial la 19 (ejecuciones en segundo plano).
- `README.md`: cómo arrancar Postgres y el servicio de ingesta.

## Alcance

- PostgreSQL en Docker, esquema normalizado y servicio de ingesta.
- Extracción de transcripciones, mensajes de chat y analítica; normalización; carga idempotente; programación y log.
- Tipo de flujo «Descarga de transcripciones», con intervalo relativo o específico, ejecución manual y programada, historial y log.
- Estado del conector de Genesys en Configuración.
- Tests con un Genesys falso (fixtures de las conversaciones de hoy), prueba con las conversaciones del día, recorrido en Chrome y actualización del vault.

## Fuera de alcance

- **Todo lo de [FE012](../FE012-switch-entre-datos-sinteticos-reales/spec.md):**
  - cambiar entre datos sintéticos y reales;
  - mostrar las conversaciones reales y su analítica en dashboards, listado, detalle, explorador, búsqueda y flujos de insights;
  - el enmascarado del texto real.
- **Análisis con LLM** (summary, main topic de la taxonomía, CSAT, resolución, cumplimiento…): es la siguiente fase. Tampoco se mapean los temas de STA a main topics.
- Audio o grabaciones: solo transcripciones, mensajes y analítica.
- Email, callbacks u otros medios distintos de voz y mensajería o chat.
- Recibir conversaciones en tiempo real (notificaciones o webhooks de Genesys).
- Varias organizaciones de Genesys.
- Gestionar las credenciales de Genesys desde la UI: se editan en el `.env`.
- Persistir en PostgreSQL la configuración, los usuarios, los flujos de insights o sus ejecuciones, que siguen en memoria.
- Borrar conversaciones reales, y políticas de retención o de cifrado.
- Recuperar las ejecuciones programadas perdidas mientras el servicio estaba parado.
- Reparar en Genesys las grabaciones o transcripciones incompletas: la ingesta solo las detecta y las marca.

## Riesgos y asunciones

- **Hecho (sondeos de solo lectura del 2026-10-12, hasta las 12:30 de Madrid; 13 conversaciones):**
  - **Acceso:** las credenciales obtienen token por *client credentials* en `mypurecloud.ie`. Responden `200`:
    - la consulta de analítica, el resumen de Speech & Text Analytics y las URL de transcripción de voz y de mensajería;
    - los metadatos de grabación y la API de mensajes, también en bloque;
    - los temas y programas de STA, las colas, los usuarios, los wrap-up, los contactos externos y las divisiones.

    **No falta ningún permiso de los necesarios.**
  - **Límite:** la consulta de detalles de analítica rechaza intervalos de más de 7 días.
  - **Qué hubo:**
    - 7 llamadas de voz entrantes, todas grabadas y con `externalTag` y ANI: 4 terminaron en el bot «Sierra VoiceAgent», 2 pasaron a cola y agente, y 1 fue del bot al agente;
    - 6 chats de mensajería web, todos con flujo de entrada, cola y agente; 2 de ellos con mensajes del bot antes del agente. Los chats no tienen ANI ni `externalTag`.
  - **Transcripciones:**
    - cada comunicación de voz devuelve de 1 a 3 transcripciones, algunas vacías y otras una por tramo;
    - en las 2 llamadas atendidas solo por un agente, solo hay frases del cliente (1 y 3); 2 llamadas del bot no tienen ninguna frase. Es coherente con las incidencias de grabación;
    - los chats tienen todos sus mensajes, salvo el texto de los no entregados, que solo da la API de mensajes.
  - **Bot o agente:** en voz y en chat, las frases `internal` del agente traen `userIds` y las del bot no. En la API de mensajes, los del agente tienen `createdBy` y los del bot no.
  - **STA:**
    - hay temas en voz y en chat (41 definidos, programa «General»), casi todos genéricos;
    - el sentimiento llega solo en algunas transcripciones, por frase y con valores `-1` o `1`;
    - la empatía, en una;
    - el reparto del tiempo por hablante y silencio solo existe en voz.
- **Riesgo:** las transcripciones de voz incompletas pueden ser lo habitual mientras duren las incidencias de grabación. Se mitiga marcando la calidad y guardando siempre la analítica. Una descarga posterior actualiza la conversación (criterio 10), así que si Genesys completa la transcripción, se recogerá.
- **Hipótesis:** en una transcripción con análisis de sentimiento, las frases que no aparecen en él son neutras. Si `/plan` encuentra documentación de Genesys que lo contradiga, esos turnos quedan vacíos en lugar de a `0`.
- **Hipótesis:** «sin `userIds` = bot» se cumple en todas las conversaciones de hoy. Si una frase de agente llegara sin `userIds`, se clasificaría por el tramo; las fixtures cubren los dos casos.
- **Riesgo:** el *rate limit* de Genesys puede alargar una descarga de 90 días, porque cada conversación necesita de 3 a 5 llamadas más la resolución de nombres. Se mitiga con los reintentos del criterio 6, la caché de nombres y el log. El límite de 90 días puede ajustarse en `/plan`.
- **Riesgo:** PostgreSQL añade Docker al arranque y al CI, y el gate local falla si Docker no está en marcha. El `README` y `ci.sh` lo indican con un mensaje claro.
- **Riesgo:** los turnos reales y los teléfonos se guardan en claro en PostgreSQL, y las fixtures llevan ANI, `externalTag` y textos reales de la cuenta del laboratorio, por decisión del usuario. El texto contiene nombres de personas, porque el bot lee el `externalTag` al saludar. Para producción habría que revisar esta decisión, la retención y el cifrado (fuera de alcance).
- **Asunción:** basta con `flows:view` y `flows:edit` para los flujos de descarga, aunque modifiquen el dataset real compartido. Si hace falta separar quién descarga de quién diseña insights, el permiso nuevo iría en otra feature.
- **Asunción:** el planificador vive en el servicio de ingesta, en un solo proceso, sin réplicas.
- **Riesgo:** aun dividida, FE011 es grande: servicio, esquema, extracción, normalización, flujos y UI. Si el plan supera 9 tareas, se propone dividirla otra vez, por ejemplo dejando la programación y el estado del conector para otra feature.

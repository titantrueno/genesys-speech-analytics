---
title: "Datos de Genesys para STA"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [producto, genesys, sta, transcripciones, analitica, fe011]
created: 2026-10-12
updated: 2026-10-12
---

# Datos de Genesys para STA

## Resumen

Qué da Genesys Cloud de cada conversación y qué no, según la cuenta del laboratorio. La ingesta de FE011 lo guarda todo ([ADR-008](../decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)). Lo que no da es lo que tendrá que calcular el análisis con LLM de la fase siguiente.

## Contexto

Hechos observados el 2026-10-12, con sondeos de solo lectura y la descarga real de las 13 conversaciones del día (7 de voz y 6 de chat) en la organización del laboratorio (`eu-west-1`). Las respuestas de referencia, saneadas, están en `backend/tests/fixtures/genesys/`.

## Conocimiento confirmado

### Lo que da Genesys

- **Analítica** (consulta de detalles):
  - recorrido por participantes y sesiones (cliente, flujo de IVR o bot, flujo de entrada de mensajería, cola, agente);
  - ANI y DNIS en voz, y `externalTag`;
  - código de wrap-up y tipo de desconexión;
  - motivo de salida y destino de la transferencia de un flujo;
  - MOS y R-factor;
  - métricas por sesión: tiempos de IVR, espera, alerta, conversación, ACW y gestión; y en chat, primera respuesta, tiempos medios de respuesta y nº de mensajes.
- **Speech & Text Analytics:**
  - temas detectados con su frase y su confianza, en voz y en chat;
  - sentimiento por frase, solo en algunas frases y con valores `-1` o `1`;
  - sentimiento de la conversación (`sentimentScore`, `sentimentTrend`, `sentimentTrendClass`);
  - empatía del agente;
  - en voz, reparto del tiempo entre agente, cliente, silencio, IVR y ACD, y eventos acústicos.
- **Transcripciones:** un documento por comunicación del cliente, con una o varias transcripciones dentro (una por tramo, algunas vacías). Las URL de descarga son firmadas y caducan.
- **API de mensajes:** el texto completo de cada mensaje de chat, su estado de entrega (`delivery-failed` incluido) y su autor.

### Lo que no da

Summary, main topic de la [taxonomía del banco](catalogo-de-main-topics.md), temas secundarios, resolución, CSAT, esfuerzo, cumplimiento de los checks y riesgo de abandono. Los temas de STA de la organización (41, programa «General») son en su mayoría **genéricos** («Conexión», «Saludos», «Satisfacción») y no sustituyen a la taxonomía. Algunos sí aportan en conversaciones de queja («Insatisfacción», «Queja», «Remitir a un supervisor»).

### Tipos de conversación

| Tipo | Lo que hay que tener en cuenta |
|---|---|
| Voz contenida en el bot | Agente de voz con IA (flujo de IVR); sus frases llegan como `internal` y sin `userIds`. |
| Voz bot → agente | Una transcripción por tramo; las frases del agente traen `userIds`. El participante agente no trae nombre: se resuelve por su `userId`. |
| Voz parcial o sin transcripción | El agente o el bot hablaron (según las métricas) sin frases, por incidencias de grabación. |
| Chat con agente | El flujo de entrada (`workflow`) no escribe. La transcripción parte cada mensaje en frases con el mismo `messageID`. |
| Chat bot → agente | El flujo de entrada escribe mensajes con `originatingEntity: Bot` y sin `createdBy`. |
| Chat con mensaje no entregado | En la transcripción, una frase `internal` vacía; en la API de mensajes, `delivery-failed` con su texto. |
| Chat con reconexión | Dos tramos de cliente, cola y agente; la transcripción del primer tramo incluye las del segundo, y la del segundo da `404`. |

### Trampas de la API

- La consulta de detalles de analítica rechaza intervalos de más de 7 días.
- El `phraseIndex` de una entrada de sentimiento **no** es el de su frase (en una llamada, el 3 apuntaba a la frase 5). Se enlaza por lado, instante y texto.
- Los `messageID` de las frases de chat coinciden con los identificadores de la API de mensajes, y así se enlazan sentimiento y temas a cada mensaje.
- Los instantes de las frases son absolutos (milisegundos), y en chat los primeros mensajes llegan unas décimas antes del inicio de la conversación.

## Límites y excepciones

- **Hipótesis:** las frases sin entrada de sentimiento, en una transcripción que sí tiene análisis, son neutras (`0`). Genesys no lo documenta.
- **Hipótesis:** «sin `userIds` = bot» se cumple en todas las conversaciones observadas. Si no, decide el tramo.
- **Hecho del 2026-10-12:** las transcripciones de voz atendidas por agentes salen incompletas por incidencias de grabación de la cuenta. Puede no ser lo habitual en otra organización.
- El FCR necesita un cliente estable: en los chats de prueba, cada conversación tiene un contacto externo distinto aunque sea la misma persona. Lo trata [FE012](../../features/FE012-switch-entre-datos-sinteticos-reales/spec.md).

## Fuentes

- [Spec FE011, tipos de conversación observados](../../features/FE011-ingesta-de-conversaciones-genesys/spec.md)
- [Verificación de FE011](../../features/FE011-ingesta-de-conversaciones-genesys/VERIFY.md)
- [Normalización](../../backend/ingestion/pipeline/normalize.py)
- [Script de captura de fixtures](../../scripts/capture_genesys_fixtures.py)
- [Genesys Cloud Developer Center](https://developer.genesys.cloud/)

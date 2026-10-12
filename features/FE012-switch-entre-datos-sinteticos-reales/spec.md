# FE012 — Switch entre datos sintéticos y reales

> Estado: **entregada** en `v0.9.0` el 2026-10-12 (aprobada al pedir su implementación). Nace de dividir la petición original de FE011. **Depende de [FE011](../FE011-ingesta-de-conversaciones-genesys/spec.md)**, que descarga y guarda las conversaciones reales, y también de FE001–FE006. Aplica FE007, FE008 y FE009.

## Objetivo

Cambiar desde Configuración entre los datos sintéticos y las conversaciones reales de Genesys guardadas por FE011, de modo que toda la plataforma trabaje con el origen elegido y muestre la analítica de Genesys de las conversaciones reales.

## Decisiones de la entrevista (2026-10-12)

- **Switch:** global a la plataforma, en Configuración, como el resto de la configuración ([ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md)).
- **Análisis:** las conversaciones reales no tienen summary, main topic de la taxonomía, CSAT, resolución ni cumplimiento hasta la fase con LLM. Se muestran como **pendientes de análisis**; lo que da Genesys sí se usa.
- **Datos sensibles:** en este desarrollo, el teléfono y el `externalTag` no son sensibles. Se muestran sin enmascarar y se pueden buscar y filtrar. El texto de los turnos sí se enmascara (FE005).

## Conceptos

- **Origen de datos:** `sintetico` (el dataset generado de hoy, en memoria) o `real` (las conversaciones de PostgreSQL de FE011). Por defecto, `sintetico`.
- **Repositorio de conversaciones:** la interfaz por la que todos los servicios (KPIs, listado, detalle, explorador, búsqueda y sampling) obtienen las conversaciones. Tiene dos implementaciones, una por origen. [ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md) ya lo anticipaba: «sustituir los mocks exigirá una capa de repositorio».
- **Análisis pendiente:** un campo del análisis de la plataforma que una conversación real aún no tiene.

## Criterios de aceptación

### Origen de datos

1. **Configuración:** la pestaña **Fuentes de datos** muestra el origen activo y permite cambiarlo entre «Sintético» y «Real (Genesys Cloud)», con confirmación.
   - El cambio exige `config:edit` y se audita (`1AU`, sección `fuentes`).
   - Se ve en el resto de secciones sin recargar, porque se invalida la caché del front.
   - Con `supervisor`, la pestaña está en solo lectura (test por rol).
   - Con el origen `real`, el estado del conector de FE011 sustituye a los conectores mock de FE005.
2. **Propagación:** con el origen `real`, dashboards, listado, detalle, explorador, búsqueda semántica y sampling de los flujos de insights trabajan **solo** con las conversaciones de PostgreSQL. Con `sintetico`, todo funciona exactamente como hoy: los tests existentes no cambian y no necesitan PostgreSQL. Un test por sección cambia el origen y comprueba que el total de conversaciones es el de la base de datos.
3. **Sin conexión:** si el origen es `real` y PostgreSQL no responde, las secciones de datos devuelven `503` con un mensaje, y el front lo muestra sin romper la navegación. Configuración sigue accesible para volver a `sintetico` (test).
4. **Datos nuevos:** las conversaciones que guarda una ejecución de descarga de FE011 aparecen en la siguiente petición, sin reiniciar la API.

### Conversaciones reales en la UI

5. **Detalle:** el chat muestra los turnos de cliente, bot y agente con estilos distintos, y una línea marca la transferencia del bot al agente. Los mensajes no entregados se muestran con su texto y la marca «No entregado». Además, hay un panel «Analítica de Genesys» con:
   - teléfonos y `externalTag`, cuando los haya;
   - el recorrido por tramos (bot → cola → agente; en una reconexión, los tramos repetidos);
   - wrap-ups, quién terminó, contención y reconexión;
   - los tiempos (los de chat, si es un chat) y la calidad de la llamada en voz;
   - el reparto del tiempo por hablante y silencio;
   - la calidad de la transcripción y la confianza media por hablante;
   - los temas detectados: al pulsar uno, el chat se desplaza a su turno, como en FE003.

   El panel muestra también la etiqueta «Análisis pendiente». Los campos que no existen en el canal (el ANI en un chat, por ejemplo) no se muestran. Hay tests con una llamada bot → agente, un chat bot → agente y un chat con un mensaje no entregado.
6. **Listado:** añade columnas de teléfono (ANI), `externalTag`, contención y calidad de la transcripción. Permite buscar de forma exacta por teléfono, con o sin `+34`, y por `externalTag` (test). El summary vacío se muestra como «Análisis pendiente».
7. **Explorador (FE002) y sampling (FE004):** con el origen `real` se ofrecen campos nuevos para:
   - ANI, DNIS y `externalTag`;
   - flujo de IVR o de entrada y wrap-up;
   - quién terminó, contención en el bot, derivación a agente, abandono y reconexión;
   - mensajes no entregados y calidad de la transcripción;
   - tema de Genesys, sentimiento de Genesys y % de silencio;
   - los tiempos de FE011.

   Con `sintetico` no aparecen (test).
8. **Variables de los prompts (FE004):**
   - `{{transcripcion}}` incluye los turnos del bot y marca los mensajes no entregados.
   - `{{metadatos}}` incluye la analítica de Genesys.
   - `{{summary}}` y `{{main_topic}}` quedan vacíos mientras el análisis está pendiente, y la validación del flujo avisa de ello sin bloquear la ejecución.

### Campos sin analizar y KPIs

9. **KPIs:** en modo real, los KPIs y desgloses que dependen del análisis de la plataforma (resolución, FCR, CSAT, esfuerzo, cumplimiento, riesgo de abandono y main topic) muestran «Sin datos · pendiente de análisis», en lugar de 0 o de un error. Se calculan con la analítica de Genesys:
   - el **volumen**;
   - el **AHT**: la gestión total de las conversaciones atendidas por un agente;
   - el **sentimiento**: el sentimiento medio del cliente según Genesys, solo con las conversaciones que lo tienen, indicando sobre cuántas se calcula.

   El drill-down de los KPIs calculados sigue cuadrando con el listado (test de contrato de FE001).
10. **Campos vacíos:** el explorador y el sampling tratan un campo sin analizar como vacío: no cumple ninguna condición salvo «está vacío». Un test de contrato comprueba que ningún endpoint devuelve `500` con conversaciones sin analizar, sin transcripción, con analítica incompleta o sin cliente identificado.

### Búsqueda y privacidad

11. **Búsqueda semántica:** el índice se reconstruye al cambiar de origen y cuando FE011 avisa de que una ejecución ha insertado o actualizado conversaciones. La búsqueda no deja de dar servicio: sigue usando el índice anterior hasta que el nuevo está listo (test). Indexa los turnos de cliente, bot y agente, incluidos los mensajes no entregados.
12. **Privacidad:** el enmascarado de PII de FE005 se aplica igual al **texto** de las conversaciones reales.
    - Con el interruptor activado, la API no devuelve el dato original del texto.
    - El índice y la variable `{{transcripcion}}` usan siempre el texto enmascarado.
    - Hay tests con turnos de ejemplo que contienen teléfono, email, DNI, IBAN y tarjeta ficticios. Por ejemplo, en los chats de prueba, «Visa terminada en 4821» conserva los últimos 4 dígitos.
    - Los campos ANI, DNIS y `externalTag` **no** se enmascaran (decisión de este desarrollo; test).

### Calidad

13. `./scripts/ci.sh` termina con código 0. Los tests del modo real usan el PostgreSQL efímero de FE011, sembrado con sus fixtures.
14. Los endpoints de datos siguen respondiendo en menos de 500 ms en modo real (test con 1.000 conversaciones sembradas en PostgreSQL).
15. **Recorrido en Chrome** contra la API real, con conversaciones del día descargadas por FE011.
    - Con `admin`:
      - cambiar el origen a «Real»;
      - en el listado, buscar por teléfono y por `externalTag`;
      - en el detalle, abrir la llamada bot → agente con su línea de transferencia, un chat bot → agente, un chat con un mensaje no entregado y el chat con reconexión. Comprobar el panel de analítica, que los temas llevan a su turno y la etiqueta «Análisis pendiente»;
      - en los dashboards, ver «Sin datos» en los KPIs de análisis, y volumen, AHT y sentimiento calculados, con un drill-down;
      - en la búsqueda, encontrar «Amazon Brasil»;
      - en el explorador, filtrar por «derivada a agente»;
      - ejecutar un flujo de insights sobre conversaciones reales;
      - volver a «Sintético» y comprobar que todo es como antes.
    - Con `supervisor`, el origen se ve en solo lectura.
    - Sin errores de consola.

## Conocimiento afectado

- [ADR-002 — Stack Vite, FastAPI y mock](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md): se cumple la consecuencia de la capa de repositorio.
- [ADR-006 — Ejecución de prompts simulada](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md): con datos reales, las variables de análisis pueden estar vacías y `{{metadatos}}` incluye la analítica de Genesys.
- [ADR-007 — Configuración global y enmascarado](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md):
  - el origen de datos es una sección más;
  - ANI, DNIS y `externalTag` no se enmascaran;
  - la hipótesis sobre formatos de PII que se escapan pasa a ser comprobable con datos reales.
- [ADR-005 — Búsqueda vectorial ligera](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md): el índice se reconstruye en caliente al cambiar de origen o al recibir datos.
- [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): repositorio con dos orígenes, propagación y KPIs con análisis pendiente.
- [Contrato de la API entre front y back](../../vault/arquitectura/contrato-api-front-back.md): campos de analítica en detalle y listado, campos nuevos del explorador, `503` de datos y KPIs sin datos.
- [Patrones de interfaz](../../vault/ingenieria/patrones-de-interfaz.md): estado «Análisis pendiente», mensajes no entregados y línea de transferencia en el chat.
- [Propósito del proyecto](../../vault/producto/proposito-del-proyecto.md): la hipótesis de validar el catálogo de main topics con datos reales queda para la fase con LLM.
- [Glosario](../../vault/glosario/terminos-del-harness.md): añadir «origen de datos» y «repositorio de conversaciones».
- [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md): revisarlas al planificar, en especial la 28 (tests que dependen del dataset) y la 31 (tests que dependen de la estructura interna).
- `README.md`: la nota «Todos los datos son mock» deja de ser cierta.

## Alcance

- Repositorio de conversaciones con dos orígenes y switch global en Configuración.
- Propagación a dashboards, listado, detalle, explorador, búsqueda y flujos de insights.
- Analítica de Genesys y turnos de bot, agente y mensajes no entregados en la UI.
- KPIs y campos con análisis pendiente.
- Enmascarado del texto real e índice de búsqueda en caliente.

## Fuera de alcance

- La descarga y la normalización (FE011).
- **Análisis con LLM** y el mapeo de los temas de STA a main topics: es la siguiente fase.
- **Dashboards o KPIs nuevos** basados en la analítica (contención, abandono, espera, silencio, mensajes no entregados): los datos son filtrables en el explorador, pero los dashboards solo cambian según el criterio 9.
- Mezclar sintéticos y reales en la misma vista.
- Persistir la configuración: el origen elegido se pierde al reiniciar la API y vuelve a `sintetico`, como el resto de la configuración ([ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md)).

## Riesgos y asunciones

- **Riesgo:** pasar de un dataset en memoria a un repositorio toca casi todos los servicios (KPIs, listado, explorador, búsqueda y flujos), muchos con cachés `@cache` sobre el dataset. Se mitiga con una interfaz única, con cachés invalidadas al cambiar de origen o al llegar datos, y con la suite actual intacta en modo sintético.
- **Riesgo:** varios KPIs, gráficos y el intérprete de FE002 asumen que todos los campos del análisis existen. Se mitiga con el test de contrato del criterio 10.
- **Riesgo:** el FCR usa el cliente para detectar recontactos. En los chats de prueba, cada conversación tiene un contacto externo distinto aunque sea la misma persona. El FCR queda «pendiente de análisis» en esta fase, y el problema se anota para la siguiente.
- **Riesgo:** reconstruir el índice cuesta unos 2,5 s con 1.000 conversaciones ([ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md)). Con muchas descargas programadas, la reconstrucción se agrupa para que no se repita en bucle.
- **Asunción:** la API lee PostgreSQL directamente (solo lectura) o a través de la lectura del servicio de ingesta de FE011. Se decide en `/plan` según el rendimiento (criterio 14).
- **Asunción:** el origen vuelve a `sintetico` al reiniciar la API, como el resto de la configuración en memoria. Si resulta incómodo, persistir la configuración sería otra feature.

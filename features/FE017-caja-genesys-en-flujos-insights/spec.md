# FE017 — Caja de descarga de Genesys en los flujos de insights

> Estado: **entregada** en `v0.13.0` el 2026-10-13 ([ship](SHIP.md)). Aprobada el 2026-10-13. Amplía FE004 (lienzo, reglas, ejecución), FE011 (descarga, programación y log) y FE015 (persistencia de flujos de insights). Aplica FE008, FE012 y ADR-010.

## Objetivo

Que un único flujo de insights haga las cuatro fases —descarga de transcripciones de Genesys, sampling, prompt y output— con una caja nueva «Genesys download» al principio del lienzo, que se pueda programar y que, al terminar la descarga, pase sus conversaciones al Sampling; y que el Sampling pueda tomar todas las conversaciones («All conversations») en lugar de una muestra.

## Decisiones de la entrevista (2026-10-13)

| Pregunta | Decisión |
|---|---|
| ¿Qué es «end-to-end»? | Un solo flujo de insights con las 4 fases: **descarga** (caja nueva) → sampling → prompt → output. No hace falta un flujo de descarga y otro de insights. |
| ¿Y el tipo «Descarga de transcripciones» de FE011? | **Conviven.** Se mantiene sin cambios; la caja nueva usa el mismo servicio de ingesta, el mismo pipeline y el mismo log. |
| ¿Sobre qué trabaja el Sampling detrás de la caja? | **Solo las conversaciones de esa descarga** (el subconjunto de la ejecución), y sobre ellas aplica sus filtros. |
| ¿Qué hace «All conversations»? | **Toma todas** las que cumplen los filtros, sin método ni tamaño. Detrás de una caja de descarga, todas las del subconjunto. |

## Conceptos

- **Caja «Genesys download»** (nodo `1ND` de tipo `descarga`): primera caja de un flujo de insights. Su configuración es la de un flujo de descarga de FE011 (intervalo, canales y «Sobrescribir») más la programación del flujo.
- **Subconjunto de la descarga:** las conversaciones que la ejecución de la caja dejó guardadas, insertadas o actualizadas. No incluye las omitidas ni las que terminaron con error.
- **Ejecución end-to-end** (`1RN` de insights): una ejecución de un flujo con caja de descarga. Contiene la ejecución de descarga del servicio de ingesta (otro `1RN`, con su log) y después el resto de nodos, como en FE004.

## Criterios de aceptación

### Caja de descarga: modelo, reglas y validación

1. **Tipo de nodo nuevo:** el catálogo (`GET /api/flows/catalog`) y la paleta del editor ofrecen la caja `descarga` («Genesys download»). Su configuración tiene:
   - **intervalo** relativo o específico, con las mismas reglas y mensajes que FE011 criterio 13 (`hoy`, `ayer`, últimas N horas 1–720 o días 1–90; específico de hasta 90 días, sin fechas futuras y con «desde» anterior a «hasta»);
   - **canales:** voz, chat o ambos (al menos uno);
   - **Sobrescribir** (como el flujo de descarga de FE011/FE013);
   - **programación:** desactivada, cada N horas (1–24) o diaria a una hora `HH:MM`, en la zona horaria de la plataforma; con intervalo específico, se rechaza con el mismo mensaje que FE011 («A scheduled download needs a relative interval»);
   - **activo:** si no lo está, el flujo no se lanza por programación, pero sí a mano.

   Un valor fuera de rango al guardar el grafo responde `422` con la ruta del campo (`nodes[0].config.interval…`), como en FE004 criterio 2. Guardar y leer el grafo devuelve el mismo JSON (test de ida y vuelta).
2. **Reglas de conexión** (en el fichero de casos compartido `rules.cases.json`, que ejecutan los tests del backend y del front):
   - se admite `descarga → sampling` y ninguna otra conexión con la caja de descarga como origen o destino;
   - la caja de descarga no tiene entradas y tiene como máximo **una** salida;
   - un `sampling` tiene como máximo una entrada, y solo puede venir de una caja de descarga;
   - un flujo tiene **como máximo una** caja de descarga: añadir una segunda se rechaza al guardar (`422`) y en el editor (aviso).
3. **Validación** (`POST /api/flows/validate`), con un código por caso:
   - caja de descarga sin salida o con configuración incompleta → error;
   - caja de descarga y origen de datos «Sintético» en Configuración → error que bloquea la ejecución («A Genesys download needs the real data origin»), porque el subconjunto son conversaciones reales;
   - servicio de ingesta no disponible al validar → error con el `503` de FE011 criterio 21;
   - un flujo sin caja de descarga valida exactamente como hoy (los tests de FE004, FE012, FE013 y FE014 siguen pasando sin cambios).

### Ejecución end-to-end

4. **Orden:** `POST /api/flows/{id}/runs` en un flujo con caja de descarga crea la ejecución de insights (`202`), y la caja pasa a `en_curso` y lanza una ejecución de descarga en el servicio de ingesta con el intervalo resuelto en ese instante. Ningún otro nodo empieza hasta que la descarga termina (test con un Genesys falso lento que observa estados intermedios).
5. **Progreso de la caja:** mientras dura la descarga, la caja informa de los contadores de FE011 criterio 17 (encontradas, descargadas, insertadas, actualizadas, con error, omitidas) y el detalle de la ejecución enlaza a la ejecución de descarga y a su log (vista de FE011, criterio 18). Los procesados no decrecen (test).
6. **Al terminar la descarga:**
   - `completada` o `completada_con_avisos` → la caja queda en `ok` y el Sampling recibe el subconjunto de la descarga;
   - `error` → la caja y la ejecución acaban en `error` con el mensaje de la descarga, y el resto de nodos queda en `pendiente` (como FE004 criterio 6);
   - subconjunto vacío (la descarga no trajo conversaciones) → la caja queda en `ok`, los nodos siguientes en un estado nuevo `omitido` con el motivo «The download returned no conversations» y la ejecución termina en `ok`, sin llamar al LLM (test). Así una programación horaria sin conversaciones nuevas no genera errores.
7. **Sampling detrás de la caja:** trabaja **solo** sobre el subconjunto de la descarga:
   - se ignora el intervalo de fechas de sus filtros (el panel lo oculta y explica que lo da la descarga) y se aplica el resto de condiciones;
   - aplica su método y tamaño (o «All conversations», criterio 10) sobre lo que queda;
   - test: con un subconjunto de 5 conversaciones y otras 20 reales del mismo intervalo descargadas antes, la muestra solo contiene conversaciones del subconjunto.
8. **Concurrencia:** si el flujo ya tiene una ejecución en curso, `POST …/runs` responde `409` (como FE004). Un flujo de descarga de FE011 y una caja de descarga pueden coincidir en el tiempo; la carga sigue siendo idempotente (FE011 criterio 10) y cada una cuenta sus conversaciones.

### Programación

9. **Ejecución programada:** un flujo de insights con caja de descarga activa y programación se lanza solo a su hora, con origen `programada` (las manuales, `manual`).
   - Test con un reloj simulado: «cada 1 hora» se lanza una vez por hora y no dos.
   - Si a esa hora hay una ejecución en curso del mismo flujo, se omite y se anota en la siguiente (como FE011 criterio 16).
   - Las ejecuciones perdidas mientras la API o el servicio estaban parados no se recuperan.
   - La programación sobrevive a reiniciar la API y el servicio de ingesta (persistencia de FE015; test).
   - Una ejecución programada que no valida (por ejemplo, origen «Sintético» o un check desactivado, FE014 criterio 7) queda registrada en el historial como `error` con los errores de validación, sin lanzar la descarga.
   - El listado de flujos muestra la próxima ejecución programada también para los flujos de insights con caja de descarga.

### Sampling «All conversations»

10. **Opción nueva:** el Sampling admite, en lugar de método y tamaño, la opción **«All conversations»** (`size: "all"` o equivalente decidido en `/plan`, con su test de ida y vuelta):
    - sin caja de descarga: pasan todas las conversaciones que cumplen sus filtros (intervalo y condiciones), en orden cronológico;
    - detrás de una caja de descarga: pasan todas las del subconjunto que cumplen sus condiciones;
    - no hay tope de tamaño; si la estimación (`POST /api/flows/sampling/estimate`) supera **1.000** conversaciones, la validación da un **aviso** (no bloqueante) `large_sample` con el número, y si algún Prompt usa un proveedor real, el aviso lo dice (coste);
    - la estimación devuelve el tamaño efectivo igual al nº de conversaciones disponibles; detrás de una caja de descarga devuelve «depends on the download» en lugar de un número.
11. **Compatibilidad:** los flujos guardados con método y tamaño se leen y ejecutan igual que antes (test con un grafo de FE004 guardado).

### Front

12. La paleta tiene la caja «Genesys download» con su icono; su panel de configuración reutiliza los controles del formulario de flujo de descarga de FE011 (intervalo, canales, Sobrescribir, programación y activo) con los mismos mensajes de validación por campo. Si ya hay una caja de descarga, la paleta la deshabilita con una explicación.
13. Conectar la caja de descarga con algo distinto de un Sampling, o un Sampling que ya tiene entrada, se rechaza con el aviso del motivo (reglas del criterio 2).
14. El panel del Sampling tiene la opción «All conversations», que oculta método y tamaño; detrás de una caja de descarga oculta el intervalo de fechas con el texto explicativo del criterio 7.
15. La vista de la ejecución muestra la caja de descarga con su estado y contadores, el enlace a su log, y el estado `omitido` en los nodos con su motivo; se actualiza por polling hasta terminar. El historial muestra el origen (`manual` o `programada`).
16. Todos los textos nuevos existen en `es` y `en` (test de paridad de ADR-010); las respuestas y errores de la API están solo en inglés.
17. Sin `flows:edit`: la caja de descarga y su programación se ven en solo lectura (test de permisos, como FE004 criterio 19).

### Permisos, contrato y calidad

18. Ejecutar y programar exige `flows:edit`; ver la ejecución y su log de descarga, `flows:view`. Un test con un rol que solo tiene `flows:view` recibe `403` en cada escritura. El recorrido de rutas del OpenAPI cubre las rutas nuevas o cambiadas y `backend/openapi.yaml` documenta el nodo `descarga`, el estado `omitido`, «All conversations» y el aviso `large_sample`.
19. Las credenciales de Genesys siguen solo en el servicio de ingesta: la API no las lee y ninguna salida nueva (ejecución de insights, errores, logs) contiene secretos, tokens ni URL firmadas (se amplía el test de FE011 criterio 3).
20. `./scripts/ci.sh` termina con código 0, con los tests de ejecución end-to-end contra el Genesys falso y PostgreSQL efímero de FE011.
21. **Recorrido en Chrome** contra la API real y con datos reales:
    - crear un flujo de insights con Genesys download («hoy», voz y chat) → Sampling «All conversations» → Prompt → Output «Guardar en campos»;
    - intentar conectar la caja de descarga con un Prompt y añadir una segunda caja de descarga (rechazos);
    - ejecutarlo a mano, ver la caja en curso con sus contadores, abrir su log, ver que el Sampling solo toma conversaciones de esa descarga y ver el resultado del Output;
    - programarlo cada hora, recargar y ver la próxima ejecución en el listado;
    - sin errores de consola. La evidencia queda en `VERIFY.md`.

## Conocimiento afectado

- **Consultado:**
  - [FE004](../FE004-disenador-de-flujos-de-insights/spec.md): tipos de nodo, reglas de conexión, estados de nodo y ejecución en memoria.
  - [FE011](../FE011-ingesta-de-conversaciones-genesys/spec.md): configuración, ejecución, programación, contadores y log de los flujos de descarga.
  - [FE015](../FE015-persistencia-flujos-y-preferencias/spec.md): flujos de insights persistidos en PostgreSQL a través del servicio de ingesta; ejecuciones de insights en memoria.
  - [ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md): solo el servicio de ingesta habla con Genesys y escribe en PostgreSQL.
  - [ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md) y [ADR-009](../../vault/decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md): ejecución de prompts.
  - [ADR-010](../../vault/decisiones/adr-010-idioma-de-la-interfaz-y-api-en-ingles.md): textos de interfaz en `es`/`en` y API solo en inglés.
  - [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md): no hacen falta prefijos nuevos (`1ND`, `1RN` y `1FL` ya cubren la caja, las ejecuciones y el flujo).
- **A actualizar:**
  - [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): ejecución end-to-end, quién programa los flujos de insights y el subconjunto de la descarga.
  - [Contrato de la API](../../vault/arquitectura/contrato-api-front-back.md): nodo `descarga`, estado `omitido`, «All conversations» y aviso `large_sample`.
  - [Runbook de la ingesta](../../vault/operaciones/runbook-ingesta-de-genesys.md): diagnosticar una ejecución end-to-end (de la caja a su log de descarga).
  - [Glosario](../../vault/glosario/terminos-del-harness.md): «caja de descarga», «subconjunto de la descarga», «ejecución end-to-end», «All conversations».
  - ADR nuevo o ampliación de ADR-008 si `/plan` decide que el programador de los flujos de insights vive en el servicio de ingesta (ver Riesgos).

## Alcance

- Nodo `descarga` en el modelo del grafo, catálogo, reglas compartidas, validación y paleta.
- Ejecución end-to-end: lanzar la descarga en el servicio de ingesta, esperar su fin y pasar el subconjunto al Sampling; estado `omitido`.
- Programación de flujos de insights con caja de descarga, con persistencia y próxima ejecución en el listado.
- Opción «All conversations» del Sampling, con y sin caja de descarga, y aviso `large_sample`.
- Front (paleta, paneles, vista de ejecución, historial), textos `es`/`en`, OpenAPI y vault.

## Fuera de alcance

- Cambiar, migrar o retirar el tipo de flujo «Descarga de transcripciones» de FE011: convive sin cambios.
- Programar flujos de insights **sin** caja de descarga.
- Varias cajas de descarga en un flujo, o una caja de descarga conectada a algo que no sea un Sampling.
- Conectar varias salidas de la caja de descarga (un Sampling por flujo detrás de ella); si hace falta repartir, se encadenan Prompts como hoy.
- Recuperar las ejecuciones programadas perdidas, cancelar una ejecución en curso o reintentar una fallida automáticamente.
- Persistir las ejecuciones de insights entre reinicios (siguen en memoria, FE015): el historial de ejecuciones programadas se pierde al reiniciar la API; el log de la descarga sí se conserva en PostgreSQL.
- Usar la caja de descarga con datos sintéticos.
- Control de coste del LLM más allá del aviso `large_sample`.

## Riesgos / asunciones

- **Riesgo (arquitectura):** hoy el programador vive en el servicio de ingesta (FE011) y las ejecuciones de insights en la memoria de la API (FE004, FE015). `/plan` debe decidir quién dispara las ejecuciones programadas de insights (un programador en la API que lee los flujos persistidos, o el de ingesta llamando a la API con el token interno) y documentarlo; las dos opciones deben cumplir el criterio 9.
- **Riesgo:** «All conversations» sin tope puede generar ejecuciones largas, caras con un LLM real y resultados de más de ~1 MB en memoria. Se mitiga con el aviso `large_sample`; si en la verificación aparece un problema de memoria, se propondrá un tope en otra feature.
- **Asunción:** el subconjunto se identifica por las conversaciones que la ejecución de descarga insertó o actualizó; esto requiere que el servicio de ingesta guarde o devuelva los identificadores `1CO` de cada ejecución. Si no lo hace hoy, `/plan` añade esa lectura (sin cambiar los contadores de FE011).
- **Asunción:** el estado `omitido` es nuevo en las ejecuciones de insights; el front lo muestra y los tests de FE004 que esperan `error` con muestra vacía **sin** caja de descarga siguen igual.
- **Asunción:** basta con `flows:view` y `flows:edit`, como en FE011 (no se separa quién descarga de quién diseña insights).
- **Riesgo:** con el origen «Sintético» un flujo programado fallará a su hora (criterio 9). Es deliberado para no mezclar datos; el historial lo explica.
- **Riesgo de tamaño:** toca modelo, reglas, ejecución, programador, servicio de ingesta y front. Si el plan supera 9 tareas, se propone dividir «All conversations» o la programación en otra feature.

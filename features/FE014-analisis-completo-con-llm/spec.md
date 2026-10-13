# FE014 — Análisis completo con LLM

> Estado: **aprobada** (2026-10-13). Depende de FE013 (servicio de LLM y «Guardar en campos»), FE012 (origen real y análisis pendiente) y FE005 (taxonomía y checks). Aplica FE008 y FE009.

## Objetivo

Que un flujo de insights genere con el LLM, a partir de la transcripción, el resto del análisis de una conversación real (resolución, CSAT predicho, esfuerzo, riesgo de abandono, sentimiento si Genesys no lo da, cumplimiento de cada check, temas secundarios, entidades y palabras clave) y lo guarde para que se vea en el detalle y cuente en los KPIs, como ya ocurre con el summary y el main topic.

## Decisiones de la entrevista

| Pregunta | Decisión |
|---|---|
| ¿Cómo se generan y guardan? | **Ampliando «Guardar en campos»** de FE013: nuevos campos destino, un tipo de campo JSON «lista» y una plantilla «Generar análisis completo» con **una sola llamada** por conversación. |
| ¿Cuándo deja de estar pendiente? | **Campo a campo:** cada dato se muestra y cuenta en los KPIs en cuanto existe; lo que falta sigue como pendiente. |
| ¿Qué checks evalúa el LLM? | **Todos los activos.** Un resultado del LLM para un check manda sobre su evaluación por frases. |
| ¿Sentimiento global? | **Del LLM solo si Genesys no lo da.** Si Genesys lo da, se conserva el de Genesys. |

## Criterios de aceptación

### Campos destino y tipos

1. El catálogo de campos destino (`TARGET_FIELDS`, `/api/flows/catalog`) añade, con su etiqueta en español: `resolution` («Resolución»), `csat` («CSAT predicho»), `effort` («Esfuerzo del cliente»), `churn_risk` («Riesgo de abandono»), `sentiment` («Sentimiento global»), `secondary_topics` («Temas secundarios»), `keywords` («Palabras clave»), una entrada `entity:<tipo>` por tipo de entidad (`importe`, `producto`, `fecha`, `comercio`) y una entrada `compliance:<código>` por **check activo** de Configuración (con su nombre). Un check desactivado o borrado deja de ofrecerse; un flujo que ya lo use no valida (criterio 7).
2. El esquema JSON de un Prompt admite el tipo **«lista»** (lista de textos), con valores permitidos opcionales. El LLM la recibe como `{"type": "array", "items": {"type": "string", "enum"?: […]}}`; la API rechaza una respuesta cuyo campo lista no sea una lista de textos o contenga un valor no permitido. Guardar y leer el flujo devuelve el mismo JSON (test de ida y vuelta).
3. El límite de campos de un esquema JSON sube de 20 a 40, para que quepa la plantilla del criterio 13 con los checks base y algunos personalizados.

### Validación de cada campo destino (al ejecutar)

4. Cada asignación valida su valor antes de escribirlo; un valor no válido deja **ese campo** de esa conversación en `rechazado` con el motivo, sin afectar a los demás campos de la misma respuesta (test por regla):
   - `resolution`: `resuelta`, `no_resuelta` o `escalada`, o su etiqueta del catálogo; se guarda el código;
   - `churn_risk`: `bajo`, `medio` o `alto`;
   - `csat` y `effort`: número entre 1 y 5;
   - `sentiment`: número entre −1 y 1;
   - `secondary_topics`: cada valor, un tema secundario **activo** (por código o nombre), guardado por código; los duplicados se quitan;
   - `keywords`: textos no vacíos; se guardan como mucho 10, en el orden recibido;
   - `entity:<tipo>`: texto; un texto vacío significa «no hay» y deja el campo en `sin valor`, sin escribir;
   - `compliance:<código>`: `cumple`, `no_cumple` o `no_aplica` (sin distinguir mayúsculas ni tildes), guardados como `true`, `false` y `null`.
5. Los rangos y el máximo de palabras clave los aplica la API, no el proveedor: Anthropic no admite `minimum`, `maximum` ni restricciones de listas en su salida estructurada (ver Riesgos). Tests con valores fuera de rango.

### Reglas de completitud del editor

6. Cada asignación exige un campo JSON del tipo adecuado (test por regla en `POST /api/flows/validate`): `resolution`, `churn_risk` y `compliance:*` → texto con valores permitidos que sean valores válidos del criterio 4; `csat`, `effort` y `sentiment` → número; `secondary_topics` → lista con valores permitidos que sean temas secundarios activos; `keywords` → lista; `entity:*` → texto. Con un Prompt de texto o etiqueta siguen valiendo solo `summary` y `main_topic` (FE013).
7. Un `compliance:<código>` de un check inexistente o desactivado es un error que bloquea la ejecución.
8. Un destino repetido sigue siendo un error (FE013); el aviso `simulated_values_to_real_data` también aplica a los campos nuevos.

### Escritura

9. El servicio de ingesta escribe los campos nuevos con las mismas reglas de FE013 (solo vacíos salvo «Sobrescribir», `FOR UPDATE`, lotes de 100, trazabilidad en `llm_meta` por campo, `status` sin cambiar). «Vacío» es: `NULL` en los escalares, lista vacía o `NULL` en las listas, y **ausencia de la clave** del check o del tipo de entidad en `compliance` y `entities`, que se combinan clave a clave sin borrar las demás. Tests con PostgreSQL por tipo de campo, con y sin «Sobrescribir».
10. `sentiment` se guarda en una columna nueva de `analysis` (migración numerada) y **solo si la conversación no tiene sentimiento de Genesys**; si lo tiene, el campo queda `omitido` con el motivo «Genesys ya da el sentimiento». Test con y sin sentimiento de Genesys.
11. Una redescarga con «Sobrescribir» (FE013) vacía también los campos nuevos y su trazabilidad (test).

### Lectura campo a campo

12. Una conversación real muestra y usa cada campo del análisis **en cuanto existe**, aunque el resto siga pendiente:
    - **detalle:** el panel «Resultado» muestra resolución, CSAT, esfuerzo, riesgo de abandono y sentimiento disponibles, y «Pendiente» en los que faltan; el panel de cumplimiento muestra cada check con resultado («Cumple», «No cumple», «No aplica») y «Pendiente» en los que no lo tienen; temas secundarios, entidades y palabras clave aparecen si existen (tests de componente con un análisis parcial);
    - **cumplimiento:** un check con resultado del LLM usa ese resultado; sin él, se mantiene la evaluación actual (los personalizados, por frases; los base, pendientes) (test);
    - **KPIs:** cada KPI que depende del análisis se calcula sobre las conversaciones que tienen ese dato, informa de cuántas son (`based_on`) y sale «pendiente» solo si ninguna lo tiene (test con un periodo en que solo una parte tiene resolución);
    - **sentimiento:** el de Genesys si existe; si no, el del LLM;
    - **filtros y explorador:** los campos con valor dejan de cumplir «está vacío» y se filtran con sus operadores habituales (test).

### Plantilla, resultado y comprobación

13. «Nuevo flujo» ofrece la plantilla **«Generar análisis completo»**: un Prompt JSON con summary, main topic, resolución, CSAT, esfuerzo, riesgo de abandono, sentimiento, un campo por check activo, temas secundarios (valores permitidos: los activos), palabras clave y las cuatro entidades, con las instrucciones de cada campo en la plantilla, y un Output «Guardar en campos» con todas las asignaciones y sin «Sobrescribir». El Sampling toma las conversaciones con alguno de esos campos vacío. Un flujo recién creado valida con datos reales y un proveedor con clave (test con PostgreSQL).
14. La ejecución muestra el estado de cada campo por conversación (también `sin valor`) y los recuentos por campo, sin desbordar la página: tabla con desplazamiento horizontal y los campos agrupados (análisis, cumplimiento, temas y entidades) (test de componente).
15. El panel del Output ofrece en el desplegable de campo destino los grupos «Análisis», «Cumplimiento» y «Entidades», y el editor de esquema permite el tipo «Lista» con sus valores permitidos (tests de componente).
16. Comprobación en navegador con datos reales y Gemini: crear un flujo desde «Generar análisis completo» con 3 conversaciones con transcripción, ejecutarlo y ver en el detalle de una de ellas el panel «Resultado», el cumplimiento, los temas secundarios, las entidades y las palabras clave rellenos. La evidencia queda en `VERIFY.md`.

### Gate

17. `./scripts/ci.sh` termina con código 0 y el OpenAPI documenta los tipos y estados nuevos.

## Conocimiento afectado

- **Consultado:**
  - [ADR-009](../../vault/decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md): «Guardar en campos», valores permitidos, una llamada por conversación y escritura por el servicio de ingesta.
  - [ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md): tabla `analysis` con todas las columnas del análisis (`resolution`, `csat`, `effort`, `churn_risk`, `compliance`, `entities`, `keywords`, `secondary_topics`) ya creadas y vacías.
  - [ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md): taxonomía de temas secundarios y checks de cumplimiento editables; evaluación por frases de los personalizados.
  - [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md) (FE012): análisis pendiente y KPIs «pendiente».
  - [Catálogo de main topics](../../vault/producto/catalogo-de-main-topics.md).
- **A actualizar:** ADR-009 (campos nuevos, tipo lista, lectura campo a campo), ADR-007 (cumplimiento del LLM sobre frases), arquitectura, [contrato de la API](../../vault/arquitectura/contrato-api-front-back.md), [runbook del servicio de LLM](../../vault/operaciones/runbook-servicio-llm.md) y `backend/openapi.yaml`.
- **Identificadores:** no se prevén prefijos nuevos ([registro](../../vault/ingenieria/registro-de-identificadores.md)).

## Alcance

- Campos destino nuevos, tipo «lista», validación por campo, reglas del editor y plantilla «Generar análisis completo».
- Escritura de los campos nuevos en el servicio de ingesta, columna `sentiment` y combinación por clave de `compliance` y `entities`.
- Lectura campo a campo en detalle, cumplimiento, KPIs, filtros y explorador.
- Front: panel del Output, editor de esquema, resultado de la ejecución y detalle con análisis parcial.

## Fuera de alcance

- Analizar con el LLM durante la ingesta (sigue siendo desde flujos).
- Escribir en datos sintéticos.
- Sentimiento por turno (`sentiment_timeline`) generado por el LLM.
- Tipos de entidad nuevos o temas secundarios nuevos creados por el LLM: solo los de la taxonomía activa.
- Editar el análisis a mano desde la interfaz.
- Marcar el análisis como `completo`: la lectura pasa a ser campo a campo y `status` no cambia.
- Coste, cancelación y colas externas (como en FE013).

## Riesgos / asunciones

- **Hecho (documentación):** la salida estructurada de Anthropic no admite `minimum`, `maximum` ni restricciones de listas; por eso los rangos y el máximo de palabras clave se validan en la API ([Anthropic · Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), sección de limitaciones del esquema).
- **Hipótesis:** Gemini y OpenAI aceptan `array` de `string` con `enum` en su modo estricto; Gemini se comprobará contra la API real en `/build`, OpenAI y Anthropic solo contra su documentación (sin claves).
- **Riesgo:** un esquema de unos 25 campos en una llamada puede bajar la calidad o subir los rechazos. Se medirá en la comprobación del criterio 16 (recuentos de rechazados por campo) y, si hace falta, se partirá la plantilla.
- **Riesgo:** la lectura campo a campo cambia los KPIs con datos reales (antes «pendiente» en bloque). Los tests de FE012 que esperan KPIs pendientes con análisis vacío deben seguir pasando: sin datos escritos, el comportamiento no cambia.
- **Riesgo:** «todos los checks activos» hace que un check personalizado pueda tener dos fuentes; la del LLM manda cuando existe. Un check creado después de ejecutar el flujo queda «pendiente» hasta otra ejecución (criterio 12).
- **Asunción:** el sentimiento de Genesys es el `customer_sentiment` que ya guarda la ingesta (FE011); una conversación sin él es la que no tiene análisis de Speech & Text Analytics.

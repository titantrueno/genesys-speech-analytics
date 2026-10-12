# FE013 — Servicio de LLM para summary y main topic

> Estado: **entregada** en `v0.10.0` el 2026-10-13 ([ship](SHIP.md)). Aprobada el 2026-10-12, ampliada en `/plan` con la casilla «Sobrescribir» de la ingesta (criterios 26–30) y la protección de la taxonomía (criterio 31), y en `/build` de T6 con summary y main topic en una sola llamada (criterio 16). Depende de FE004 (flujos de insights), FE005 (configuración), FE011 (ingesta y PostgreSQL) y FE012 (origen de datos real). Aplica FE008 y FE009.

## Objetivo

Conectar la plataforma con un LLM real (Gemini por defecto, intercambiable por OpenAI o Anthropic) mediante un servicio aparte, y permitir que los flujos de insights generen el **summary** o el **main topic** de conversaciones reales y los guarden en el campo que se elija en un desplegable del nodo Output.

## Decisiones de la entrevista

| Pregunta | Decisión |
|---|---|
| ¿Qué es el «nuevo backend»? | Un **servicio aparte** (`backend/llm/`, `uvicorn llm.main:app`), único proceso que lee las claves de los proveedores. La API delega en él con token interno, igual que con la ingesta ([ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)). |
| ¿Dónde se escribe el output? | **Solo con datos reales**, en la tabla `analysis` de PostgreSQL. Con datos sintéticos el destino aparece deshabilitado con un aviso. |
| ¿Y si ya hay valor? | Casilla **«Sobrescribir valores existentes»** en el nodo, desmarcada por defecto: sin marcarla solo rellena campos vacíos. |
| ¿La ingesta analiza con el LLM? | **No.** El LLM solo se usa desde flujos de insights; `PendingAnalyzer` no cambia. |
| ¿Qué pasa al volver a descargar una conversación? (añadida en `/plan`) | El flujo de descarga tiene la casilla **«Sobrescribir»**, desmarcada por defecto. Marcada: la conversación se sustituye entera y su análisis vuelve a `pendiente`, **borrando** summary y main topic del LLM (para redescargar tras cambios o reprocesos). Sin marcar: si la conversación ya está en la base, no se descarga ni se toca y se pasa a la siguiente. |
| ¿Summary y main topic en una sola llamada? (añadida en `/build` de T6) | **Sí.** Un Prompt JSON con los dos campos y un Output `campo` con dos asignaciones; el main topic se acota con los valores permitidos del campo. |
| ¿Se puede borrar un main topic en uso? (añadida en `/plan`) | No, tampoco si solo lo usan conversaciones reales y el origen activo es `sintetico`. |

## Criterios de aceptación

### Servicio de LLM y proveedores

1. Existe el proceso `backend/llm/` (`uvicorn llm.main:app`, puerto por defecto `8002`) con `GET /health` (estado del servicio y, por proveedor, si su clave está configurada como booleano) y `POST /complete` (proveedor, modelo, temperatura, prompt y formato de salida → texto de respuesta, proveedor, modelo y tokens consumidos si el proveedor los da).
2. El servicio es el **único** proceso que lee `GEMINI_API_KEY`, `OPENAI_API_KEY` y `ANTHROPIC_API_KEY`, desde su lista blanca de `app/envfile.py`. Un test estructural comprueba que ni la API ni la ingesta leen esas claves, y que `backend/llm/` solo importa de `app` los módulos `ids`, `clock` y `envfile`.
3. Toda petición a `/complete` sin el token interno `LLM_TOKEN` correcto recibe `401`, y ninguna respuesta, log ni mensaje de error del servicio contiene una clave de proveedor (test con una clave ficticia buscada en respuestas y logs capturados).
4. Los proveedores están detrás de una interfaz `LlmProvider` con cuatro implementaciones: `gemini`, `openai`, `anthropic` y `simulado` (determinista, sin red, para tests y para trabajar sin clave). Añadir un proveedor consiste en una clase nueva y una entrada en el registro de proveedores; un test recorre el registro y verifica que cada proveedor cumple el contrato de `LlmProvider` con su transporte simulado.
5. Cada proveedor real traduce la misma petición a la API oficial de su proveedor. Los tests, sin red (`httpx.MockTransport`), comprueban por proveedor la URL, las cabeceras de autenticación, el modelo, la temperatura y el prompt enviados, y la extracción del texto de una respuesta de ejemplo tomada de la documentación oficial.
6. Errores del proveedor: `429` y `5xx` se reintentan hasta 2 veces con espera creciente; clave ausente devuelve `503` «El proveedor X no tiene clave configurada»; clave rechazada (`401`/`403` del proveedor) devuelve `502` «El proveedor rechazó la clave»; el resto de fallos, `502` con un mensaje sin datos sensibles. Cada caso tiene un test.
7. El servicio limita las llamadas simultáneas al proveedor (`LLM_MAX_CONCURRENCY`, 4 por defecto); un test con un proveedor lento comprueba que nunca hay más de N llamadas en curso.

### Configuración → Modelos de IA

8. El catálogo de proveedores (`PROVIDERS` en `backend/app/flows/catalog.py`) incluye `gemini` (por defecto en una configuración nueva), `openai`, `anthropic` y `simulado`, cada uno con su lista de modelos. Cambiar de proveedor en Configuración → Modelos de IA cambia, sin reiniciar nada, el proveedor y modelo por defecto de los nodos Prompt nuevos y los modelos ofrecidos en su desplegable.
9. La pestaña muestra, para cada proveedor, si su clave está configurada (sí/no, nunca la clave) y si el servicio de LLM responde, y un botón «Probar» que lanza una petición mínima y muestra éxito o el mensaje de error del criterio 6. Si el servicio no responde, la pestaña lo indica y la API devuelve `503` en esas rutas.
10. Un nodo Prompt guarda proveedor y modelo. La validación de completitud avisa (`error`, bloquea la ejecución) si el proveedor del nodo no tiene clave configurada o el modelo no pertenece al proveedor.

### Ejecución de prompts con el LLM

11. La API tiene un `LlmPromptRunner` (implementa `PromptRunner` de [ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md)) que renderiza la plantilla con `render_template` y llama al servicio de LLM con `app/llm_client.py`. `get_prompt_runner()` lo usa para cualquier proveedor distinto de `simulado`; con `simulado` se mantiene `MockPromptRunner`. Un test con `dependency_overrides` y un doble del servicio lo comprueba.
12. El prompt enviado al LLM usa siempre la transcripción **enmascarada** (test: una conversación con un DNI y un teléfono en un turno; el prompt que recibe el doble del servicio no los contiene).
13. La respuesta se valida contra el formato del nodo: **texto** se recorta de espacios y no puede quedar vacío; **etiqueta** debe coincidir con una de la lista sin distinguir mayúsculas, tildes ni espacios en los extremos; **JSON** debe cumplir el esquema. Una respuesta no válida marca esa conversación como `rechazada` con el motivo, sin detener el nodo. Hay un test por formato.
14. Si el servicio de LLM no responde o devuelve `503` (sin clave) o `502` de clave rechazada, el nodo pasa a `error` con el mensaje del criterio 6 y los nodos dependientes quedan `pendiente`. Otros fallos por conversación cuentan como `error` de esa conversación y el nodo continúa.

### Output «Guardar en campo»

15. El nodo Output tiene un nuevo tipo `campo` («Guardar en campos de la conversación») con una o varias **asignaciones** y la casilla «Sobrescribir valores existentes» (`overwrite`, `false` por defecto). Cada asignación tiene un **desplegable de campo destino** con `summary` («Summary») y `main_topic` («Main topic»), que sale de un catálogo de campos destino (`TARGET_FIELDS`; `ANALYSIS_FIELDS` ya existe en `app/query/fields.py`) servido por `/api/flows/catalog`, y, si el Prompt de entrada es JSON, el **campo del JSON** del que sale el valor. Guardar y leer el flujo devuelve el mismo JSON (test de ida y vuelta).
16. **Una sola llamada para los dos campos** (añadido en `/build` de T6): un campo de texto del esquema JSON de un Prompt puede llevar una lista de **valores permitidos** (`options`). Se envía al proveedor como `enum` y una respuesta con otro valor se rechaza. Así, un Prompt JSON con `summary` (texto) y `main_topic` (texto con los main topics activos como valores permitidos) devuelve los dos en una llamada por conversación, y un Output `campo` con dos asignaciones los guarda. Test: el flujo hace exactamente una llamada al servicio de LLM por conversación y escribe los dos campos.
17. Reglas de completitud del Output `campo` (cada una con su test en `POST /api/flows/validate`):
    - con un Prompt de texto o etiqueta, exactamente una asignación y sin campo de origen; con un Prompt JSON, cada asignación nombra un campo de texto del esquema;
    - `summary` exige texto (el Prompt de texto o un campo de texto sin valores permitidos);
    - `main_topic` exige un Prompt de etiqueta o un campo JSON con valores permitidos, y que todas las etiquetas o valores sean main topics **activos** de la taxonomía (por código o por nombre);
    - un destino repetido, en el mismo Output o en dos Outputs `campo` del flujo, es un error;
    - con el origen de datos `sintetico` (FE012) es un error que bloquea la ejecución: «Guardar en campos solo funciona con datos reales».
18. En el editor, con origen `sintetico`, la opción `campo` del Output aparece deshabilitada con ese aviso; con origen `real`, los desplegables muestran los campos destino del catálogo con su etiqueta en español y, con un Prompt JSON, sus campos de texto.
19. Al ejecutar, por cada conversación con resultado válido y cada asignación: si el campo está vacío o `overwrite` es `true`, se guarda; si no, se omite. `main_topic` se guarda siempre como **código** de la taxonomía aunque el LLM responda el nombre. Tests con PostgreSQL (`pg`) para: campo vacío → escrito; con valor y `overwrite=false` → intacto; con valor y `overwrite=true` → sustituido; respuesta rechazada → intacto.
20. Las escrituras las hace el **servicio de ingesta** (único que escribe en PostgreSQL, [ADR-008](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)) con un endpoint interno nuevo que la API llama con el token de ingesta. Cada escritura guarda, por campo, proveedor, modelo, el `1RN` de la ejecución y el instante en una columna nueva (`analysis.llm_meta`) de una migración numerada, y actualiza `updated_at`. No cambia `status` de la fila.
21. Un summary o main topic escrito por un flujo se ve en el detalle, el listado, los filtros por main topic y los dashboards tras la siguiente petición (el testigo de FE012 detecta el cambio en `analysis`), **aunque el resto del análisis siga `pendiente`**. Test de integración: escribir el main topic de una conversación pendiente y comprobar que `GET /api/conversations?main_topic=<código>` la devuelve.
22. La ejecución muestra para el Output `campo` una tabla por conversación (valor y estado `escrito`, `omitido`, `rechazado` o `error` de cada campo destino) y los recuentos de cada estado por campo. Para cada campo, la suma de los recuentos es igual al número de conversaciones que llegaron al Prompt.

### Plantillas de flujo

23. En el listado de flujos de insights, «Nuevo flujo» ofrece tres plantillas además del flujo vacío: **«Generar summary»**, **«Generar main topic»** y **«Generar summary y main topic»** (una llamada por conversación, criterio 16). Cada una crea un flujo `Sampling → Prompt → Output (campo)` ya configurado: Sampling de conversaciones con el campo (o alguno de los dos campos) vacío, sin fechas para que siempre sea relativo al periodo por defecto (cambio de `/build` de T8: el Sampling no admite fechas relativas y unas fechas fijas de «últimos 7 días» se quedarían desfasadas); Prompt con una plantilla en español, el proveedor y modelo por defecto y el formato adecuado (texto, etiqueta o JSON con los main topics activos como valores permitidos); Output con las asignaciones correspondientes y `overwrite=false`. Un flujo recién creado desde una plantilla pasa la validación de completitud con origen `real` y un proveedor con clave (test).

### Operación y gate

24. `./scripts/dev.sh` arranca y para también el servicio de LLM, `.env.example` documenta `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LLM_TOKEN`, `LLM_URL` y `LLM_MAX_CONCURRENCY` sin valores, y `./scripts/ci.sh` ejecuta los tests del servicio sin red ni claves reales y termina con código `0`.
25. Comprobación en navegador (con proveedor `simulado` y, si hay clave disponible, una ejecución manual con Gemini sobre 3 conversaciones reales): crear un flujo desde «Generar main topic», ejecutarlo y ver el main topic en el detalle de esas conversaciones. La evidencia queda en `VERIFY.md`.

### Ingesta: casilla «Sobrescribir»

26. El flujo de descarga tiene el campo booleano `overwrite` («Sobrescribir»), `false` por defecto, guardado en `download_flow` por una migración numerada; los flujos existentes quedan con `false`. Crear, leer y guardar un flujo devuelve el valor (tests del servicio de ingesta y del relevo de la API).
27. Con `overwrite=false`, por cada conversación encontrada en la búsqueda se comprueba **antes de descargar su transcripción** si su identificador de Genesys ya está en `conversation`. Si está, no se llama a Genesys para esa conversación, no se modifica ninguna fila suya (tampoco `analysis`) y se cuenta en el contador nuevo `skipped_existing` con una línea de log «Ya existe: no se descarga». Test `pg` con el Genesys falso: segunda ejecución sobre el mismo periodo → cero llamadas de descarga, `skipped_existing` igual a las conversaciones ya cargadas y `analysis.summary` escrito antes intacto.
28. Con `overwrite=true`, una conversación existente se descarga y se sustituye: columnas de `conversation`, tramos, turnos, temas y respuestas originales, y la fila de `analysis` vuelve al resultado de `PendingAnalyzer` (`pendiente`, `summary` y `main_topic` vacíos y sin trazabilidad del LLM), **también si estaba `completo`**. Se cuenta en `updated`. Test `pg`: escribir summary y main topic con la escritura del criterio 20, redescargar con `overwrite=true` y comprobar que están vacíos y el `1CO` no cambia.
29. Las conversaciones nuevas se insertan igual con los dos valores (`inserted`). La suma `inserted + updated + skipped_existing + errors` es igual al número de conversaciones por descargar de la búsqueda (test).
30. El formulario del flujo de descarga muestra la casilla «Sobrescribir» con la ayuda «Vuelve a descargar las conversaciones que ya existen y borra su summary y main topic generados por el LLM», y la página de la ejecución muestra el recuento «Ya existentes (no descargadas)». Comprobado en navegador y con tests de componente.

### Taxonomía: main topics en uso en datos reales

31. Borrar un main topic (`DELETE /api/config/taxonomy/main-topics/{id}`) devuelve `409` si lo usa alguna conversación del dataset sintético **o** de PostgreSQL, sea cual sea el origen activo; el mensaje dice cuántas conversaciones de cada origen lo usan. Si hay `DATABASE_URL` pero PostgreSQL no responde, el borrado devuelve `503` «No se puede comprobar el uso en los datos reales» y no borra. Sin `DATABASE_URL`, solo cuenta el sintético. Tests `pg` para los tres casos con origen activo `sintetico`.

## Conocimiento afectado

- **Consultado:**
  - [ADR-006 — Ejecución de prompts simulada](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md): `PromptRunner`, `get_prompt_runner()` y los pasos de migración a un LLM real que esta feature sigue.
  - [ADR-008 — PostgreSQL y servicio de ingesta](../../vault/decisiones/adr-008-postgresql-y-servicio-de-ingesta.md): patrón de servicio aparte, lista blanca de claves, token interno, escritor único de PostgreSQL y tabla `analysis` con `source` `llm`.
  - [ADR-007 — Configuración global y enmascarado](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md): sección «Modelos de IA» y prompts siempre enmascarados.
  - [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): flujos de insights (FE004), configuración (FE005) y repositorio real (FE012).
  - [Catálogo de main topics](../../vault/producto/catalogo-de-main-topics.md): un main topic por conversación, por código, y summary de 2 a 4 frases.
  - [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md): la feature reutiliza `1FL`, `1ND` y `1RN`; no prevé prefijos nuevos.
- **A crear:** ADR-009 — Servicio de LLM con proveedores intercambiables; runbook del servicio de LLM en `vault/operaciones/`.
- **A actualizar:** ADR-006 (ampliación: runner real), arquitectura de la plataforma (componente nuevo y Output `campo`), [contrato de la API](../../vault/arquitectura/contrato-api-front-back.md), `backend/openapi.yaml`, [estado operativo](../../vault/operaciones/estado-operativo.md) y [primeros pasos](../../vault/onboarding/primeros-pasos.md) (tercer servicio y claves).

## Alcance

- Servicio `backend/llm/` con `LlmProvider` y proveedores Gemini, OpenAI, Anthropic y simulado; salud, prueba de proveedor, reintentos y límite de concurrencia.
- `LlmPromptRunner` y cliente de la API; selección de proveedor y modelo en Configuración y en el nodo Prompt.
- Output `campo` con desplegable de destino (`summary`, `main_topic`) y `overwrite`; validaciones; escritura en PostgreSQL vía servicio de ingesta y migración con trazabilidad.
- Plantillas «Generar summary» y «Generar main topic».
- Casilla «Sobrescribir» de los flujos de descarga y comprobación de existencia antes de descargar.
- Protección del borrado de main topics usados en datos reales.
- `dev.sh`, `.env.example`, `ci.sh`, OpenAPI y vault.

## Fuera de alcance

- Analizar con el LLM durante la ingesta (`PendingAnalyzer` sigue igual).
- Otros campos de análisis (temas secundarios, resolución, CSAT, esfuerzo, riesgo de abandono, cumplimiento): el catálogo `TARGET_FIELDS` queda preparado, pero solo se ofrecen `summary` y `main_topic`.
- Escribir en datos sintéticos.
- Gestionar las claves desde la interfaz: se configuran en `.env` del servicio.
- Control de coste o presupuestos, streaming, caché de respuestas, cancelación de ejecuciones y colas externas (Celery, RQ): las ejecuciones siguen en segundo plano dentro de la API.
- Usar el LLM en el intérprete del explorador (FE002) o en la búsqueda semántica (FE003).
- Persistir flujos de insights, configuración o ejecuciones (siguen en memoria).
- Evaluar la calidad de los summaries o main topics generados.

## Riesgos / asunciones

- **Hipótesis:** los identificadores de modelo de cada proveedor y la forma de sus APIs REST cambian a menudo. `/test` debe contrastar URL, cabeceras, cuerpo y modelos de cada proveedor con su documentación oficial en la fecha de la verificación y citarla.
- **Hipótesis:** se usará `httpx` contra las APIs REST, sin SDK de cada proveedor, para no añadir dependencias pesadas ([ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md)) y probar con `MockTransport` como la ingesta. Se decide en `/plan`.
- **Riesgo:** la lectura actual del repositorio real solo usa `analysis` cuando `status='completo'` (`backend/app/data/real.py`). El criterio 21 obliga a cambiarla para leer `summary` y `main_topic` aunque la fila esté `pendiente`, sin que el resto de pantallas traten la conversación como analizada.
- **Riesgo:** una muestra de 1.000 conversaciones con 4 llamadas simultáneas puede tardar minutos y consumir cuota; sin cancelación, la única forma de pararla es reiniciar la API. Se asume aceptable para el laboratorio.
- **Riesgo:** enviar transcripciones enmascaradas a un proveedor externo. El enmascarado por patrones ([ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md)) puede no cubrir toda la PII; se asume aceptable para la cuenta de laboratorio y se anotará para producción.
- **Cambio de comportamiento:** hoy volver a descargar una conversación la actualiza. Con `overwrite=false` por defecto, los flujos existentes y programados dejan de actualizar las conversaciones ya cargadas: un cambio posterior en Genesys (transcripción tardía, wrap-up nuevo) no llega hasta que se ejecute un flujo con «Sobrescribir». Decidido por la persona usuaria.
- **Riesgo:** una conversación descargada mientras aún estaba incompleta en Genesys (las `en curso` ya se omiten) queda fija si no se redescarga con «Sobrescribir».
- **Asunción:** la persona usuaria dispone de una clave de Gemini para la comprobación manual del criterio 25; si no, esa parte se marca como no verificada y se usa el proveedor `simulado`.
- **Asunción:** el filtro de Sampling «campo vacío» de las plantillas existe o se puede expresar con el motor de consultas de FE002; si no, `/plan` añade el campo al registro del explorador.

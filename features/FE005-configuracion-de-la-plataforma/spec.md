# FE005 — Configuración de la plataforma

> Estado: **aprobada** el 2026-09-28 (revisada tras la entrega de `v0.4.0`). Depende de FE001 y propaga sus cambios a FE002, FE003 y FE004. Aplica FE007 y FE008.

## Objetivo

Centralizar la configuración funcional de la plataforma, de modo que sus cambios se reflejen en el resto de secciones.

## Conceptos

- **Configuración:** global a la plataforma (no por usuario), en memoria y servida completa por `GET /api/config`. El front la cachea y la invalida tras cada cambio.
- **Main topic** (`1TP`) y **tema secundario:** entradas editables de la taxonomía. Cada main topic tiene un identificador `1TP` estable (v5 derivado del código) para la API de configuración, pero su **código** legible (`cargo_no_reconocido`) sigue siendo la clave en filtros, URLs, consultas guardadas, flujos y drill-down. El código se fija al crear y no se puede cambiar.
- **Check de cumplimiento** (`1CK`): igual que un main topic, identificador `1CK` más código inmutable, que sigue siendo la clave del campo de FE002.
- **Conector de datos** (`1CN`): fuente de conversaciones mock.
- **Entrada de auditoría** (`1AU`): registro de un cambio de configuración.

## Criterios de aceptación

### Backend

1. **API:** `GET /api/config` devuelve la configuración completa. Cada pestaña tiene sus escrituras (`PUT` de la sección o CRUD de sus elementos). Un identificador inexistente, mal formado o de otro tipo devuelve `404`.
2. **Validación:** cada cambio se valida con Pydantic y devuelve `422` con un mensaje por campo (ruta del campo y motivo). Un test por pestaña cubre al menos un valor inválido.
3. **Permisos:** las lecturas exigen `config:view` y las escrituras, `config:edit`. Con los roles por defecto, `admin` modifica, `supervisor` ve en solo lectura y `analista` y `viewer` reciben `403` y no ven la sección. Un test por rol lo comprueba, y el recorrido de rutas del OpenAPI cubre las rutas nuevas.
4. **Auditoría:** cada cambio aceptado crea una entrada `1AU` con usuario, fecha, sección, elemento afectado, valor anterior y valor nuevo. `GET /api/config/audit` la lista (más reciente primero, filtrable por sección) con `config:view`. Un cambio rechazado (`403` o `422`) no crea entrada (test).

### Pestañas

5. **General:** nombre de la plataforma (1–60 caracteres), zona horaria (lista IANA) e idioma por defecto (solo `es-ES` disponible). El nombre aparece en la cabecera y en el login. Cambiar la zona horaria cambia las fechas mostradas en el listado, el detalle, los resultados de búsqueda y el listado e historial de flujos (test de front). Los filtros de fecha y los días de las series temporales se interpretan en esa zona horaria (test de backend con una conversación cercana a medianoche).
6. **Fuentes de datos:** muestra los conectores mock (`Genesys Cloud · voz transcrita` y `Genesys Cloud · chat`) con estado, última sincronización y nº de conversaciones de su canal (el mismo que el KPI de volumen del periodo completo). «Sincronizar» simula una sincronización: actualiza la fecha y no cambia el dataset.
7. **Taxonomía:** CRUD de main topics y de temas secundarios con código (`snake_case`, único), nombre, descripción y palabras clave, inicializado con el catálogo de FE001.
   - Un main topic nuevo y activo aparece en los filtros de dashboards, listado y búsqueda semántica, en los valores del campo `main_topic` de FE002 y en los estratos del Sampling de FE004 (tests).
   - Un main topic en uso (asignado a alguna conversación) no se puede borrar (`409`), solo desactivar. Uno desactivado deja de ofrecerse en filtros y selectores, pero sus conversaciones lo siguen mostrando, contando en los KPIs y siendo accesibles por drill-down.
   - Renombrar un main topic cambia su nombre en todas las secciones sin cambiar su código.
8. **KPIs y objetivos:** para cada KPI de FE001, objetivo, umbrales y en qué dashboards se muestra.
   - El sentido de cada KPI es fijo (por ejemplo, más resolución es mejor; más AHT o más escalado es peor), y los umbrales verde/ámbar/rojo deben ser coherentes con él (`422` si no lo son).
   - Las tarjetas de KPI de FE001 se colorean según esos umbrales, y cambiarlos cambia el color (test).
   - Un KPI que no se muestra en un dashboard no aparece en sus tarjetas.
9. **Cumplimiento:** CRUD de checks con código, nombre, descripción, frases esperadas (1–20), canal al que aplica (`voz`, `chat` o `ambos`) y si está activo.
   - Los seis checks de FE001 conservan el resultado del análisis mock. Un check nuevo se evalúa buscando sus frases esperadas en los turnos del agente, sin distinguir mayúsculas ni tildes: `cumple` si aparece alguna, `no_cumple` si no aparece ninguna y `no_aplica` si el canal no aplica (test con conversaciones de ejemplo).
   - Solo los checks activos aparecen en el detalle, en el KPI de cumplimiento (global y por check) y como campos de FE002.
   - El drill-down del KPI de cumplimiento sigue cuadrando con su valor tras crear, desactivar o cambiar un check (test de contrato de FE001).
10. **Privacidad:** interruptor de enmascarado de PII, **activado por defecto**. Detecta por patrones teléfonos, emails, DNI/NIE, IBAN y tarjetas (últimos 4 dígitos).
    - Activado, el detalle, el summary del listado, los fragmentos de la búsqueda semántica y los resultados de los flujos muestran `[TELÉFONO]`, `[EMAIL]`, `[DNI]`, `[IBAN]` y `[TARJETA]`. Hay un test con ejemplos de cada tipo, incluidos falsos positivos habituales (importes, fechas, números de expediente).
    - **Siempre**, con independencia del interruptor, el índice de la búsqueda semántica y la variable `{{transcripcion}}` de los prompts de FE004 usan el texto enmascarado. Buscar un DNI del dataset no devuelve resultados (test).
    - El enmascarado se aplica en el backend: el JSON de la API no contiene el dato original cuando el interruptor está activado (test).
11. **Modelos de IA:** proveedor y modelo por defecto, de las listas mock del catálogo de FE004, sin claves ni secretos. Un nodo Prompt nuevo toma ese modelo; los existentes conservan el suyo. La UI indica que la ejecución es simulada ([ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md)).

### Front

12. La sección **Configuración** (`/configuracion`) sustituye el «Próximamente» y tiene las siete pestañas; la pestaña activa vive en la URL. Estados: cargando, error y solo lectura (sin controles de edición).
13. Cada formulario muestra el error de cada campo junto al campo, a partir de la respuesta `422`, y conserva lo escrito.
14. Borrar o desactivar pide confirmación. Un main topic en uso no ofrece «Borrar».
15. Cada pestaña muestra su registro de auditoría (quién, cuándo, elemento, valor anterior y nuevo).
16. Tras guardar un cambio, las demás secciones lo reflejan sin recargar la página (se invalida la caché de `GET /api/config` y de los catálogos dependientes).

### Calidad

17. `./scripts/ci.sh` termina con código 0. Los endpoints nuevos y los afectados por la configuración siguen respondiendo en menos de 500 ms con el dataset completo (tests con ese umbral).
18. Recorrido en Chrome contra la API real: con `admin`, crear un main topic, cambiar un umbral, crear un check, cambiar la zona horaria y desactivar el enmascarado, comprobando el efecto en dashboards, listado, detalle, explorador, búsqueda y flujos; con `supervisor`, la sección en solo lectura. Sin errores de consola.

## Conocimiento afectado

- [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): añadir el modelo de configuración y su propagación, y actualizar el límite que dice que los DNI e IBAN se muestran sin enmascarar hasta FE005.
- [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md): pasar `1TP`, `1CK`, `1CN` y `1AU` a activos, y sustituir la excepción «Main topics y checks conservan su código legible hasta FE005» por la regla de código más identificador.
- [Catálogo de main topics](../../vault/producto/catalogo-de-main-topics.md): indicar que es el catálogo inicial y que después se edita en Configuración.
- [ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md): marcar como resuelto el enmascarado antes de enviar transcripciones.
- [ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md): el índice se construye sobre texto enmascarado.
- [Gobierno del vault](../../vault/Governance.md): su regla de no almacenar datos personales justifica el enmascarado por defecto; enlazarla desde la arquitectura.
- [Estado operativo](../../vault/operaciones/estado-operativo.md): anotar que los conectores son mock.
- Nuevo ADR: modelo de configuración global y enmascarado de PII.

## Alcance

- API y UI de las siete pestañas, validación, permisos y registro de auditoría.
- Propagación a FE001–FE004: catálogos, filtros, campos de FE002, estratos de FE004, colores de KPI, checks activos, zona horaria, enmascarado y modelo por defecto.
- Enmascarado de PII en la API, en el índice de búsqueda y en la entrada de los prompts.

## Fuera de alcance

- Conexión real con Genesys Cloud (OAuth, APIs de grabación o transcripción).
- Persistencia entre reinicios del backend.
- Gestión de secretos o claves de proveedores de IA.
- Configuración por tenant, por usuario o multi-organización.
- Reclasificar las conversaciones existentes con un main topic nuevo: el dataset no cambia, así que un main topic nuevo empieza sin conversaciones.
- Traducción de la UI a otros idiomas.
- Edición de roles y permisos (FE006).

## Riesgos y asunciones

- **Asunción:** la configuración es global a la plataforma, no por usuario.
- **Riesgo:** propagar cambios a otras secciones crea dependencias. Se mitiga con un único `GET /api/config` cacheado en el front e invalidado tras cada cambio, y con servicios del backend que leen la configuración vigente en cada petición.
  - **Desviación aceptada en `/build` (T8):** `GET /api/config` exige `config:view`, pero la zona horaria y el nombre de la plataforma los necesitan todos los roles y el login. Se exponen en `GET /api/config/public` (sin sesión, solo nombre, zona horaria e idioma), y el modelo por defecto en `GET /api/flows/catalog`. Ver [ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md).
- **Riesgo:** evaluar los checks nuevos por frases en cada petición puede superar los 500 ms. Se mitiga con una caché por check invalidada al editarlo; se verifica con los tests de rendimiento.
- **Riesgo:** los patrones de PII pueden enmascarar de más (importes, referencias) o de menos. El test de ejemplos incluye falsos positivos conocidos.
- **Riesgo:** construir el índice sobre texto enmascarado reduce ligeramente la recuperación de términos numéricos. Se acepta por privacidad.
- **Hipótesis:** las pantallas de FE001–FE004 formatean las fechas en un único punto que puede recibir la zona horaria. Hay que comprobarlo en `/plan`.

# FE005 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-09-28. Siguiente paso: `/build`, en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md) | `1TP`, `1CK`, `1CN` y `1AU` reservados | Pasan a activos (T1, T9). `1TP` y `1CK` son v5 derivados del código (estables); `1AU` es v4. Hay que comprobar si ya están en `PREFIXES` de `app/ids.py`; si no, se añaden en T1 junto con la tabla. |
| [ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md) y `app/auth.py` | `config:view` y `config:edit` ya existen; `admin` tiene los dos y `supervisor` solo `config:view`; `analista` y `viewer`, ninguno | Sin cambios en la matriz. |
| `app/data/catalog.py` | `MAIN_TOPICS`, `SECONDARY_TOPICS` y `COMPLIANCE_CHECKS` son constantes de módulo | Pasan a ser el **estado inicial** del store de configuración. El generador los sigue usando tal cual, así que el dataset no cambia. Los demás módulos dejan de importarlos y leen la configuración vigente (T3, T4). |
| `app/routers/conversations.py` (`/api/catalog`, detalle) | Catálogo y etiqueta del main topic desde constantes | Lee la configuración: solo main topics y checks activos en los selectores; la etiqueta de un topic desactivado se sigue resolviendo (T3, T4). |
| `app/services/filters.py` (`is_compliant`, fechas con `started_at.date()`) | Cumplimiento desde `analysis.compliance`; día sin zona horaria | `is_compliant` pasa a usar el cumplimiento efectivo (T4); el día se calcula en la zona horaria configurada (T5). **Hipótesis:** `started_at` lleva zona (UTC); se comprueba en T5 antes de convertir. |
| `app/services/kpis.py` | `KPI_DEFS` con `higher_is_better`; `compliance_by_check` recorre `COMPLIANCE_CHECKS` | El sentido de cada KPI ya existe y valida los umbrales (T5). `compliance_by_check` recorre los checks activos (T4). |
| `app/query/fields.py` | `FIELDS` construido una vez al importar | Pasa a construirse desde la configuración vigente (`get_fields()`, cacheado por versión de configuración), para que un main topic o un check nuevo aparezcan como valores o campos de FE002 (T3, T4). |
| `app/search/` ([ADR-005](../../vault/decisiones/adr-005-busqueda-vectorial-ligera.md)) | Índice de fragmentos sobre el texto de los turnos | El índice se construye sobre texto **siempre** enmascarado (T2). Los turnos devueltos se enmascaran o no según el interruptor. |
| `app/flows/prompting.py` y catálogo de flujos ([ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md)) | `{{transcripcion}}` con el texto original; modelos mock en `catalog.py` | `{{transcripcion}}` siempre enmascarada (T2). Proveedores y modelo por defecto salen del mismo catálogo; los estratos por `main_topic` usan la configuración (T1, T3). |
| `frontend/src/lib/format.ts` | `formatDateTime` es el único punto que formatea fecha y hora, en la zona del navegador | Confirma la hipótesis de la spec: recibe la zona configurada (T8). Hay que buscar otros usos directos de `Date`/`Intl` en listado, detalle y búsqueda. |
| `frontend/src/router.tsx` y `layout/navigation` | `/configuracion` muestra `ComingSoonPage` | Se sustituye por la sección (T6). El test de «Próximamente» pasa a `/usuarios`. |
| [Lecciones de la construcción](../../vault/aprendizaje/lecciones-construccion-plataforma.md) | 22 lecciones | Se aplican: rutas vía OpenAPI, tres estados de datos remotos, fecha de referencia distinta de hoy, test de propiedad para lo que convierte texto libre (patrones de PII), rojo demostrado con mutaciones, build comprobado por código de salida y verificación en navegador. |

## Decisiones de diseño

- **Store de configuración** (`app/config/store.py`): un único objeto en memoria con cerrojo, una **versión** que aumenta con cada cambio y `reset_config_store()` para los tests. Los servicios leen `get_config()` en cada petición; las cachés derivadas (campos de FE002, cumplimiento efectivo) se indexan por la versión, así que se invalidan solas.
- **Una ruta de escritura por sección**, todas a través de `apply_change(section, element, before, after, user)`, que valida, guarda y crea la entrada `1AU` en la misma operación bajo el cerrojo. Así ningún cambio aceptado queda sin auditar y ninguno rechazado deja entrada.
- **Errores `422` por campo:** se reutiliza el formato de validación de FastAPI (`loc` y `msg`) también para las reglas de negocio (umbrales incoherentes, código duplicado), para que el front tenga un solo formato.
- **Cumplimiento efectivo** (`app/config/compliance.py`): `effective_compliance(conv) -> dict[code, bool | None]` con los checks activos. Los seis originales toman el valor de `analysis.compliance`; los nuevos se evalúan por frases en los turnos del agente con `normalize_text` de FE002. Caché por (versión, conversación). Todo lo que hoy lee `analysis.compliance` pasa por aquí.
- **Enmascarado** (`app/privacy/masking.py`): `mask(text) -> str` con patrones ordenados (IBAN antes que DNI y teléfono, para no cortar un IBAN). Se aplica al serializar la respuesta, no al dataset, para que el interruptor sea reversible. El índice y los prompts llaman a `mask` siempre.
- **Zona horaria:** el backend interpreta `from`/`to` y los días de las series en la zona configurada; las fechas viajan en ISO con zona y el front las formatea con la zona de `GET /api/config`.
- **Propagación en el front:** `useConfig()` sobre `GET /api/config`; cada mutación de configuración invalida `config`, `catalog`, `query-schema` y `flows-catalog`.

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Núcleo: store, API, permisos, auditoría y pestañas General, Fuentes y Modelos (backend) | — | 1, 2, 3, 4, 5 (nombre), 6, 11 |
| T2 | Privacidad: enmascarado en la API, en el índice y en los prompts | T1 | 10 |
| T3 | Taxonomía editable y su propagación | T1 | 7 |
| T4 | Checks de cumplimiento editables y cumplimiento efectivo | T1, T3 | 9 |
| T5 | KPIs y objetivos, y zona horaria en el backend | T1 | 5 (backend), 8 |
| T6 | Front: sección, pestañas General, Fuentes, Privacidad y Modelos, errores, auditoría y solo lectura | T1, T2 | 12, 13, 15 |
| T7 | Front: pestañas Taxonomía, KPIs y Cumplimiento | T3, T4, T5, T6 | 7, 8, 9, 14 |
| T8 | Front: propagación a dashboards, listado, detalle, búsqueda y flujos | T6, T7 | 5, 8, 11, 16 |
| T9 | Conocimiento, CI y verificación en Chrome | T1–T8 | 17, 18 y conocimiento afectado |

### T1 — Núcleo de configuración

- **Qué:**
  - `app/ids.py`: `TOPIC`, `CHECK`, `CONNECTOR` y `AUDIT` (y la tabla del registro en el mismo cambio);
  - `app/config/model.py`: modelos Pydantic de cada sección con `extra="forbid"` (General, Fuentes, Privacidad, Modelos; los de Taxonomía, KPIs y Cumplimiento se añaden en T3–T5);
  - `app/config/store.py`: estado inicial, versión, cerrojo, `apply_change` y auditoría `1AU`;
  - `app/routers/config.py`: `GET /api/config`, `PUT /api/config/general`, `GET /api/config/connectors` y `POST …/{id}/sync`, `PUT /api/config/privacy`, `PUT /api/config/ai`, `GET /api/config/audit?section=`;
  - el nombre de la plataforma en `GET /api/config` y en una ruta pública mínima para el login (`GET /api/config/public`, solo nombre).
- **Hecho cuando:** hay tests para:
  - lectura con `admin` y `supervisor`, `403` con `analista` y `viewer`, y `403` en cada escritura para `supervisor` (el recorrido de rutas del OpenAPI cubre las nuevas);
  - `422` con `loc` y mensaje por campo (nombre vacío o de 61 caracteres, zona horaria desconocida, idioma no disponible, modelo fuera del catálogo o de otro proveedor);
  - la auditoría: una entrada por cambio aceptado con usuario, fecha, sección, elemento, antes y después; ninguna por un `403` o un `422`; orden y filtro por sección;
  - conectores: nº de conversaciones igual al volumen por canal del periodo completo; «Sincronizar» actualiza la fecha y no cambia el dataset; `404` de un `1CN` inexistente o de otro tipo;
  - `reset_config_store()` en el fixture `api`, para que los tests no se contaminen.

### T2 — Privacidad

- **Qué:**
  - `app/privacy/masking.py` con los cinco tipos;
  - enmascarado al serializar el detalle, el summary del listado y del explorador, los turnos de la búsqueda y los resultados de los flujos cuando el interruptor está activado;
  - el índice de búsqueda y `{{transcripcion}}` de los prompts siempre sobre texto enmascarado;
  - las condiciones de texto de FE002 (`summary`, `transcript`) buscan en el texto tal como se muestra.
- **Hecho cuando:** hay tests para:
  - ejemplos de cada tipo (con y sin separadores) y falsos positivos conocidos: importes, fechas, horas, números de expediente, últimos 4 dígitos ya ocultos y códigos de 1TP/1CO;
  - un test de propiedad con semilla fija sobre todas las transcripciones del dataset: tras enmascarar no queda ningún DNI, IBAN ni teléfono que case con los patrones, y enmascarar dos veces da lo mismo;
  - con el interruptor activado, el JSON de detalle, listado, búsqueda y ejecución de un flujo no contiene ningún DNI ni IBAN del dataset; desactivado, el detalle los muestra;
  - buscar un DNI del dataset no devuelve resultados con el interruptor en cualquiera de sus dos estados;
  - el prompt simulado recibe la transcripción enmascarada (con un `PromptRunner` espía);
  - rendimiento: detalle y búsqueda siguen por debajo de 500 ms con el enmascarado activo.

### T3 — Taxonomía

- **Qué:**
  - modelos y CRUD de main topics (`1TP`) y temas secundarios, con código `snake_case` único e inmutable, nombre, descripción, palabras clave y activo;
  - `409` al borrar uno en uso; desactivar;
  - `/api/catalog`, `get_fields()` de FE002, los filtros de la búsqueda y los estratos del Sampling de FE004 leen la configuración.
- **Hecho cuando:** hay tests para:
  - estado inicial igual al catálogo de FE001 (15 main topics, mismos códigos y nombres);
  - crear un main topic y verlo en `/api/catalog`, en los valores de `main_topic` de `/api/query/schema` y en el catálogo de flujos; una consulta de FE002 que lo usa devuelve 0 conversaciones sin error;
  - `422` por código duplicado, mal formado o cambiado en una edición; `409` al borrar uno en uso; borrar uno sin uso;
  - desactivar: desaparece de los selectores, las conversaciones siguen mostrando su nombre, los KPIs no cambian y el drill-down por ese código sigue cuadrando;
  - renombrar cambia la etiqueta en el detalle, el listado y el desglose por main topic;
  - la caché de campos de FE002 se invalida con la versión (mutación: caché sin versión).

### T4 — Cumplimiento

- **Qué:**
  - modelos y CRUD de checks (`1CK`) con código, nombre, descripción, frases, canal y activo;
  - `app/config/compliance.py` con `effective_compliance` y su caché;
  - `is_compliant`, `compliance_by_check`, los campos `check:*` de FE002, el detalle y el filtro `compliant` del listado pasan a usarlo.
- **Hecho cuando:** hay tests para:
  - estado inicial con los seis checks de FE001 y resultados idénticos a los de `analysis.compliance` (el KPI de cumplimiento no cambia sin tocar la configuración);
  - un check nuevo sobre conversaciones de ejemplo: `cumple` con una frase en un turno del agente (sin mayúsculas ni tildes), `no_cumple` si la frase solo la dice el cliente, `no_aplica` si el canal no aplica;
  - desactivar un check lo quita del detalle, del KPI (global y por check) y del esquema de FE002;
  - **contrato de drill-down:** tras crear, desactivar y editar un check, el total de `/api/conversations?compliant=false` coincide con el numerador del KPI de cumplimiento;
  - rendimiento: `/api/metrics/summary` con dos checks nuevos sobre 90 días por debajo de 500 ms (y la segunda llamada usa la caché).

### T5 — KPIs y zona horaria

- **Qué:**
  - configuración por KPI: objetivo, umbrales y dashboards donde se muestra; validación de coherencia con `higher_is_better`;
  - `GET /api/metrics/summary` devuelve, por KPI, el estado (`verde`, `ambar`, `rojo` o `null`) y si se muestra en el dashboard pedido;
  - días de filtros y series en la zona horaria configurada.
- **Hecho cuando:** hay tests para:
  - umbrales incoherentes (`422` por campo) en un KPI donde más es mejor y en otro donde más es peor;
  - el estado de una tarjeta cambia al mover un umbral por encima y por debajo del valor;
  - un KPI oculto en un dashboard no se devuelve para ese dashboard y sí para otro;
  - zona horaria: una conversación a las 23:30 UTC cuenta en un día con `UTC` y en el siguiente con `Europe/Madrid`, en el listado, en la serie diaria y en los KPIs; el drill-down desde la serie sigue cuadrando.

### T6 — Front: sección y pestañas simples

- **Qué:**
  - `config/api.ts` (`useConfig`, mutaciones que invalidan las claves dependientes) y `config/ConfigPage.tsx` en `/configuracion` con pestañas en la URL (`?tab=`);
  - pestañas General, Fuentes de datos, Privacidad y Modelos de IA;
  - `config/FieldError` a partir del `422`, conservando lo escrito;
  - `config/AuditLog.tsx` por pestaña;
  - solo lectura sin `config:edit`.
- **Hecho cuando:** hay tests para cambiar de pestaña (y recargar en la misma), guardar cada pestaña, el error de un campo junto a él sin perder lo escrito, sincronizar un conector, la auditoría, los estados cargando y error, la solo lectura de `supervisor` (sin controles de edición) y el aviso de ejecución simulada en Modelos de IA.

### T7 — Front: Taxonomía, KPIs y Cumplimiento

- **Qué:** las tres pestañas con sus tablas y formularios: crear, editar, desactivar y borrar con confirmación; umbrales con el sentido del KPI visible; frases del check como lista editable.
- **Hecho cuando:** hay tests para cada CRUD, la confirmación al borrar y desactivar, un main topic en uso sin «Borrar», el código no editable al editar, los umbrales incoherentes con su error y los dashboards de cada KPI.

### T8 — Front: propagación

- **Qué:**
  - `formatDateTime` y los demás formateos de fecha reciben la zona de la configuración;
  - el nombre de la plataforma en la cabecera y en el login;
  - tarjetas de KPI coloreadas según su estado y ocultas si no se muestran en el dashboard;
  - un nodo Prompt nuevo toma el modelo por defecto;
  - las invalidaciones de caché de T6 comprobadas en las otras secciones.
- **Hecho cuando:** hay tests para:
  - las fechas del listado, del detalle, de la búsqueda y del listado e historial de flujos con dos zonas horarias;
  - el color de una tarjeta al cambiar un umbral y una tarjeta oculta;
  - el nombre en la cabecera y en el login;
  - un Prompt nuevo con el modelo por defecto y uno existente sin cambios;
  - un main topic creado en Configuración que aparece en el filtro del dashboard sin recargar.

### T9 — Conocimiento, CI y navegador

- **Qué:**
  - vault:
    - nuevo ADR-007 (configuración global en memoria, propagación y enmascarado de PII por defecto);
    - ADR-005 (índice enmascarado) y ADR-006 (enmascarado resuelto);
    - arquitectura (sección de configuración y límite de PII actualizado, con enlace a [Gobierno del vault](../../vault/Governance.md));
    - registro de identificadores (`1TP`, `1CK`, `1CN`, `1AU` activos; regla de código más identificador);
    - catálogo de main topics (catálogo inicial), estado operativo (conectores mock), glosario, patrones de interfaz y lecciones;
  - READMEs con los endpoints, la sección y el estado.
- **Hecho cuando:**
  - `python scripts/audit_vault.py` y `./scripts/ci.sh` terminan con código 0;
  - el recorrido del criterio 18 funciona en Chrome contra la API real, sin errores de consola.

## Riesgos del plan

- **Configuración leída en caliente (T3–T5):** módulos que hoy importan constantes pueden seguir haciéndolo sin que ningún test falle. Se mitiga con un test que busca importaciones de `MAIN_TOPICS` y `COMPLIANCE_CHECKS` fuera de `app/data/` y `app/config/`.
- **Falsos positivos del enmascarado (T2):** los importes y referencias del generador pueden parecer teléfonos. El test de propiedad recorre todo el dataset y los falsos positivos conocidos quedan como casos fijos.
- **Rendimiento (T2, T4):** enmascarar y evaluar frases en cada petición. Cachés por versión y tests con el umbral de 500 ms.
- **Zona horaria (T5):** si `started_at` no lleva zona, primero hay que fijarla a UTC en el generador sin cambiar el dataset (test de determinismo de FE001).

## Progreso

| Id | Estado | Evidencia |
|---|---|---|
| T1 | Hecha | `tests/test_config_api.py`: 31 tests en verde (rojo previo: 28 fallos; pasaban solo los 3 de `404` de conector, porque la ruta aún no existía); suite de 539. `app/ids.py`: constantes `TOPIC`, `CHECK`, `CONNECTOR` y `AUDIT`. `app/config/model.py`: secciones Pydantic con `extra="forbid"` (General con nombre recortado de 1–60, zona IANA e idioma `es-ES`; Privacidad; Modelos, con el modelo validado contra su proveedor) y `field_errors`, que devuelve el formato de FastAPI (`loc`, `msg`) con mensajes en español. `app/config/store.py`: `Config` inmutable con versión, `apply_change` que lee el valor anterior, guarda y audita (`1AU`) bajo el mismo cerrojo y no audita si nada cambia, y `reset_config_store` en el fixture `api`. `app/routers/config.py`: `GET /api/config` (secciones, versión y opciones), `PUT general`, `privacy` y `ai`, conectores (`1CN` v5) con nº de conversaciones por canal y `sync`, `audit?section=` y `GET /api/config/public` (solo el nombre, para el login; añadido a las rutas públicas del recorrido del OpenAPI). `flows/catalog.py`: `PROVIDERS` (proveedor simulado con los modelos de FE004). **Hallazgo para T5:** `started_at` no lleva zona y es la hora local del banco (8–22 h), así que la zona por defecto es `Europe/Madrid` para no cambiar el comportamiento actual. Mutaciones detectadas (10 de 10): auditar sin cambios, auditoría sin orden inverso, nombre sin recortar, modelo de otro proveedor, escritura con `config:view`, estado sin reiniciar entre tests, conector inexistente sin `404`, datos de más en la ruta pública, zona horaria sin validar y valor anterior mal auditado. La última pareció sobrevivir por el `.pyc` en caché (lección 23). |
| T2 | Pendiente | |
| T3 | Pendiente | |
| T4 | Pendiente | |
| T5 | Pendiente | |
| T6 | Pendiente | |
| T7 | Pendiente | |
| T8 | Pendiente | |
| T9 | Pendiente | |

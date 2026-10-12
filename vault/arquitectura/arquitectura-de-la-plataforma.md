---
title: "Arquitectura de la plataforma"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [arquitectura, frontend, backend, api, mock, busqueda, flujos, configuracion, privacidad, usuarios, roles, genesys, ingesta, postgresql]
created: 2026-09-27
updated: 2026-10-12
---

# Arquitectura de la plataforma

## Resumen

La plataforma es una SPA (Vite, React, TypeScript, Tailwind) que consume una API REST de FastAPI. La API genera en memoria un dataset mock determinista de conversaciones bancarias transcritas y calcula métricas bajo demanda. La arquitectura del entorno de trabajo de agentes se describe aparte en [arquitectura del harness](arquitectura-del-harness.md).

## Conocimiento confirmado

### Componentes

| Componente | Ubicación | Responsabilidad |
|---|---|---|
| Generador de datos | `backend/app/data/` | 1.000 conversaciones de 90 días a partir de semilla y fecha de referencia; catálogo bancario, guiones por main topic, análisis correlacionado. |
| Store | `backend/app/data/store.py` | Dataset cacheado, índice por identificador e índice de recontacto a 7 días (FCR). |
| Servicios | `backend/app/services/` | Filtros comunes y de drill-down; cálculo de los 13 KPIs. |
| Auth | `backend/app/auth.py` | Usuarios y roles (`1RO`) en memoria con escritura única y protecciones, token HMAC y `require_permission` (ver [ADR-003](../decisiones/adr-003-auth-mock-por-roles.md)). |
| Auditoría | `backend/app/audit.py` | Registro `1AU` compartido por la configuración (FE005) y por usuarios y roles (FE006). |
| Identificadores | `backend/app/ids.py` | `PREFIJO-UUID` (ver el [registro](../ingenieria/registro-de-identificadores.md)). |
| Búsqueda semántica | `backend/app/search/` | Índice por fragmentos construido al arrancar, interfaz `SearchEngine`, TF-IDF y diccionario de sinónimos (ver [ADR-005](../decisiones/adr-005-busqueda-vectorial-ligera.md)). |
| Flujos de insights | `backend/app/flows/` | Formato JSON del flujo, integridad y reglas de conexión, validación, sampling, prompt simulado detrás de `PromptRunner`, outputs y ejecuciones en segundo plano (ver [ADR-006](../decisiones/adr-006-ejecucion-de-prompts-simulada.md)). |
| Configuración | `backend/app/config/` | Instantánea global versionada (`store.py`, audita en `app/audit.py`), secciones Pydantic (`model.py`), taxonomía, checks y cumplimiento efectivo, y KPIs (ver [ADR-007](../decisiones/adr-007-configuracion-global-y-enmascarado.md)). |
| Privacidad | `backend/app/privacy/masking.py` | Enmascarado de PII por patrones sobre una copia de cada conversación. |
| Servicio de ingesta (FE011) | `backend/ingestion/` | Proceso aparte (`uvicorn ingestion.main:app`) y único que lee `GENESYS_*`. Descarga, normaliza y guarda conversaciones de Genesys en PostgreSQL, y ejecuta los flujos de descarga y su programador (ver [ADR-008](../decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)). |
| PostgreSQL (FE011) | `docker-compose.yml`, `backend/ingestion/migrations/` | Conversaciones reales, tramos, turnos, temas, análisis pendiente, respuestas originales, flujos de descarga, ejecuciones y logs. |
| Front | `frontend/src/` | Sesión, navegación por permisos, dashboards, listado, detalle, explorador, búsqueda semántica, diseñador de flujos, configuración y usuarios y roles. |

### Flujo de datos

1. El front autentica con `POST /api/auth/login` y envía `Authorization: Bearer` en cada petición. El contrato completo de cada endpoint está en [Contrato de la API entre front y back](contrato-api-front-back.md). En desarrollo, el proxy de Vite reenvía `/api` al puerto 8000.
2. Los filtros de los dashboards viven en la URL (`from`, `to`, `channel`, `queue`, `agent`, `main_topic`) y se pasan tal cual a métricas y listado.
3. **Contrato de drill-down:** cada elemento de un dashboard navega a `/conversaciones` con los filtros del dashboard más un filtro que selecciona el **numerador** de su KPI (`frontend/src/dashboards/drilldown.ts`). Los tests del backend garantizan que el total del listado coincide con el valor mostrado.
4. El detalle carga `GET /api/conversations/{id}` y el catálogo para las etiquetas de los checks.

### Motor de consultas (FE002)

- **Modelo:** un intervalo más un árbol de grupos `and`/`or` (máximo 2 niveles) con condiciones `{field, operator, value, speaker?}`. `backend/app/query/model.py` valida y devuelve **todos** los errores con la ruta de cada condición (`root.conditions[1].conditions[0]`).
- **Campos:** registro tipado en `backend/app/query/fields.py`:
  - categóricos, numéricos, texto y booleanos;
  - un campo por cada check de cumplimiento, con «cumple / no cumple / no aplica»;
  - cola y agente con identificadores `1QU`/`1AG` y etiqueta de nombre.
- **Evaluación:** `backend/app/query/engine.py`. El texto se compara sin distinguir mayúsculas ni tildes, con caché por conversación y filtro opcional por hablante. `POST /api/query/run` reutiliza `compute_kpis` y `services/listing.py`, así que explorador y listado devuelven las mismas filas.
- **Intérprete:** `backend/app/query/interpreter.py`, mock por reglas y sinónimos bancarios, sin LLM. Nunca ejecuta: devuelve una consulta editable y las palabras no entendidas.
- **Consultas guardadas:** en memoria, privadas de cada usuario (otro usuario recibe `404`), con identificador `1QY`. Una consulta guardada sin fechas sigue siendo relativa al periodo por defecto.
- **Front:**
  - la consulta vive en la URL (`q`, JSON en base64url);
  - las condiciones incompletas no se envían;
  - debounce de 300 ms;
  - las respuestas antiguas no sustituyen a las nuevas, porque TanStack Query guarda cada consulta bajo su propia clave.

### Búsqueda semántica (FE003)

- **Interfaz:** la API (`backend/app/routers/search.py`) solo conoce `SearchEngine` (`search`, `expansions`, `similar`) y la obtiene con `get_search_engine()`, sustituible con `dependency_overrides`. La implementación actual es `TfidfEngine`; la migración a embeddings no cambiaría la API ([ADR-005](../decisiones/adr-005-busqueda-vectorial-ligera.md)).
- **Índice:**
  - **Fragmentos:** ventanas de 3 turnos con paso 2, sin turnos de `sistema`; unos 7.150 fragmentos.
  - **Vectores:** TF-IDF de palabras y n-gramas de caracteres (3–5), en Python puro, con índice invertido compacto (`array`).
  - **IDF:** por conversación y sin suavizado, para anular el texto común (saludo, verificación, despedida).
  - **Construcción:** en el `lifespan` de `create_app`, unos 2,5 s.
- **Diccionario de sinónimos** (`backend/app/search/synonyms.py`): 33 grupos por concepto del dominio. Los términos añadidos pesan la mitad y la respuesta los devuelve (`expansions`).
- **Dos puntuaciones:**
  - `score` (fragmento completo) ordena, filtra y se muestra;
  - `focus` (80 % los turnos del cliente) elige el fragmento que representa a cada conversación (`best_per_conversation`).
- **Endpoints:** `GET /api/search/semantic` (filtros de FE001, umbral, agrupación, `max_score` antes del umbral) y `GET /api/search/similar/{id}` (TF-IDF de la conversación completa), con el permiso `search:use`.
- **Front:**
  - la búsqueda vive en la URL (`q`, `from`, `to`, `channel`, `queue`, `min_score`, `group` o `similar`) y se lanza al enviar;
  - el umbral muestra la mejor puntuación de la búsqueda y permite ajustarse a ella;
  - cada resultado abre el detalle en `/conversaciones/{id}?turn=N`, que desplaza el chat y resalta el turno.

### Flujos de insights (FE004)

- **Formato JSON (versión 1):** `{version, nodes: [{id, type, position, config}], edges: [{source, target}]}`, igual en `backend/app/flows/model.py` y `frontend/src/flows/types.ts`. Los nodos nuevos llevan una clave `tmp-<uuid>` y el backend les asigna su `1ND` al guardar (ver el [registro](../ingenieria/registro-de-identificadores.md)). Guardar y leer devuelve el mismo JSON (test de ida y vuelta).
- **Configuración por tipo:**
  - **Sampling:** consulta de FE002 (intervalo y condiciones), método y tamaño (1–1.000);
  - **Prompt:** plantilla con `{{transcripcion}}`, `{{summary}}`, `{{main_topic}}`, `{{metadatos}}` y `{{resultado_anterior}}`, modelo mock, temperatura y formato (texto, etiqueta o JSON con esquema);
  - **Output:** tabla, métrica (recuento o %) o informe, con un nombre de destino.
- **Dos niveles de validación:**
  - **integridad** (se exige al guardar): tipos, identificadores, rangos y reglas de conexión (`Sampling → Prompt`, `Prompt → Prompt`, `Prompt → Output`; una entrada por Prompt u Output; sin duplicados ni ciclos);
  - **completitud** (bloquea la ejecución; `POST /api/flows/validate` con un grafo sin guardar): nodos sin configurar, variables, nodos sueltos, métrica sin etiquetas y destinos repetidos.
- **Reglas en los dos lados:** las de conexión existen en Python y en TypeScript para responder al instante en el lienzo; `frontend/src/flows/rules.cases.json` se ejecuta en los dos lados. La completitud solo existe en el backend.
- **Ejecución:** `POST /api/flows/{id}/runs` valida, crea la ejecución (`1RN`, con copia del grafo y semilla) y la ejecuta en segundo plano (`BackgroundTasks`) en orden topológico. Cada nodo informa de estado y procesados; el front consulta el detalle cada 500 ms hasta que termina. El estado se protege con un cerrojo por ejecución y el arranque es atómico (`409` si ya hay una en curso). Se conservan las 50 ejecuciones más recientes de cada flujo (`MAX_RUNS_PER_FLOW`), sin descartar nunca una en curso.
- **Sampling real** sobre el dataset: aleatorio con semilla, estratificado proporcional (restos mayores) o primeros N por un criterio.
- **Permisos:** lecturas con `flows:view` y escrituras y ejecuciones con `flows:edit`. El esquema y las sugerencias de campos de FE002 aceptan también `flows:view`, porque los usa el nodo Sampling.
- **Front:** React Flow (`@xyflow/react`) en rutas diferidas: listado, editor (paleta arrastrable o con botón, lienzo, paneles por nodo, validar, guardar y ejecutar), ejecución (lienzo de solo lectura con progreso y pestañas por output) e historial.

### Configuración (FE005)

- **Modelo:** una instantánea inmutable (`Config`) con versión: General, conectores, taxonomía, checks, KPIs, privacidad e IA. Es global, vive en memoria y se pierde al reiniciar. Toda escritura pasa por `apply_change`, que guarda y audita (`1AU`) bajo el mismo cerrojo ([ADR-007](../decisiones/adr-007-configuracion-global-y-enmascarado.md)).
- **Lectura en caliente:** ningún módulo fuera de `app/data/` y `app/config/` importa el catálogo fijo de FE001 (hay un test estructural). Los nombres de los topics salen de `topic_name()`, los campos del explorador de `get_fields()` y el cumplimiento de `effective_compliance()`, cacheados por identidad de instantánea.
- **Propagación:**
  - **taxonomía:** `/api/catalog` (con `active`), esquema del explorador (que también usa el Sampling de FE004), etiquetas del listado, detalle, desgloses e informes;
  - **checks:** detalle, KPI y desglose de cumplimiento, filtro `compliant` del drill-down, campos `check:*` e intérprete; los desactivados siguen siendo válidos en consultas guardadas;
  - **KPIs:** `GET /api/metrics/summary` añade `target` y `status`, y con `dashboard` devuelve solo los que se muestran en él;
  - **zona horaria:** días de filtros, series, explorador e informes en la zona configurada; `started_at` lleva la zona del banco (`Europe/Madrid`);
  - **modelo por defecto:** `default_model` en `/api/flows/catalog`.
- **Rutas:** `GET /api/config` y el resto de lecturas con `config:view`; escrituras con `config:edit`; `GET /api/config/public` (nombre, zona horaria e idioma) sin sesión, porque el login y todos los roles lo necesitan.
- **Privacidad:** enmascarado activado por defecto al serializar detalle, listado, explorador y búsqueda. El índice de búsqueda y los prompts de los flujos usan **siempre** texto enmascarado. Lo justifica la regla del [gobierno del vault](../Governance.md) de no reproducir datos personales innecesarios.
- **Front:** `/configuracion` en diferido con ocho pestañas (la activa en `?tab=`); al guardar se invalidan todas las consultas en caché. La octava, «API» (FE010), muestra la especificación OpenAPI con Swagger UI en un chunk propio, con búsqueda, filtro por dominio y «Try it out» con la sesión; no tiene registro de cambios ([contrato de la API](contrato-api-front-back.md)). `AppLayout` lee la configuración pública y fija la zona horaria de `lib/format.ts`, el único módulo que formatea fechas.

### Usuarios y roles (FE006)

- **Modelo:** usuarios (`1US`, con estado y último acceso) y roles (`1RO`, v5 derivado del código, que no cambia). Los cuatro roles base no se borran ni se renombran, pero sus permisos sí se editan; los personalizados se crean, renombran y borran si no tienen usuarios.
- **Escritura única:** `UserStore.apply` calcula el estado resultante sobre copias, comprueba las protecciones, lo confirma, sube la versión y audita (sección `usuarios`) bajo un cerrojo. Las protecciones (`409`): quien cambia algo conserva `users:admin`; queda al menos un usuario activo con el rol `admin`; el rol `admin` conserva `users:admin` ([ADR-003](../decisiones/adr-003-auth-mock-por-roles.md)).
- **Rutas:** `/api/users`, `/api/roles` y `/api/users/audit`, todas con `users:admin`. `/api/config/audit` solo devuelve secciones de configuración, aunque el registro sea compartido.
- **Refresco de permisos:** el backend relee usuario y rol en cada petición. Un middleware añade `X-Auth-Version` (versión de usuarios y roles) a toda respuesta de una petición con sesión y CORS la expone; `api/client.ts` avisa cuando cambia y `AuthProvider` recarga `/api/auth/me`, así que menú y guardas cambian en la siguiente petición sin recargar.
- **Front:** `/usuarios` en diferido con pestañas Usuarios y Roles (en `?tab=`), matriz de permisos que guarda al cambiar cada casilla y el registro de cambios. Las pestañas (`components/Tabs.tsx`) y el registro (`config/AuditLog.tsx`) se comparten con la configuración.

### Ingesta de Genesys (FE011, [ADR-008](../decisiones/adr-008-postgresql-y-servicio-de-ingesta.md))

- **Procesos:**
  - el front habla solo con la API;
  - la API comprueba permisos y delega en el servicio de ingesta (`app/ingestion_client.py`, token interno, `503` si no responde);
  - el servicio de ingesta habla con Genesys Cloud y con PostgreSQL.
- **Pipeline** (`backend/ingestion/pipeline/`):
  - `extract`: búsqueda en tramos de 7 días; descarga de Speech & Text Analytics, transcripciones y mensajes;
  - `normalize`: tramos, turnos, hablantes, sentimiento, calidad de la transcripción y analítica; funciones puras;
  - `analyze`: `Analyzer`, hoy `PendingAnalyzer`;
  - `load`: `upsert` por conversación.
- **Ejecuciones** (`runs.py`, `scheduler.py`):
  - un pool de 2 hilos, una ejecución activa por flujo;
  - contadores guardados tras cada conversación;
  - log por etapas sin texto de turnos ni secretos;
  - un programador por tics de 30 s, que no recupera las ejecuciones perdidas.
- **Front** (`frontend/src/downloads/`):
  - el listado de «Flujos de insights» une los dos tipos;
  - el formulario del flujo de descarga está en `/flujos/descargas/{id}`;
  - la ejecución, con polling de 2 s y log por tramos (`after`), está en `/flujos/descargas/{id}/ejecuciones/{runId}`;
  - la tarjeta de Genesys está en Configuración → Fuentes de datos.
- **Qué da Genesys y qué no:** [datos de Genesys para STA](../producto/datos-de-genesys-para-sta.md).

### Rendimiento

- Con el dataset completo, cada endpoint responde en menos de 500 ms (hay tests con ese umbral). Una ejecución de flujo tarda unos 15 ms por conversación y prompt (retardo simulado configurable): 40 conversaciones con 2 prompts, unos 2 s. La búsqueda semántica tarda unos 12 ms de mediana sobre 90 días (55 ms en el peor caso medido, con consultas de 500 caracteres). A cambio, el arranque tarda unos 2,5 s y el índice retiene unos 52 MB, con un pico transitorio de unos 260 MB durante la construcción.
- En el front, el dashboard y los flujos se cargan en diferido: la carga inicial ocupa unos 448 kB, Recharts va en el chunk de dashboards (unos 353 kB) y React Flow, en otro de unos 176 kB, compartido por el editor y la vista de ejecución. Las barras en HTML (`dashboards/bars.tsx`) no dependen de Recharts, así que la vista de ejecución no lo descarga.

## Límites y excepciones

- Sin persistencia en la API: todo cambio de estado se pierde al reiniciar la API. La excepción son las conversaciones reales y los flujos de descarga (FE011), que guarda el servicio de ingesta en PostgreSQL. La plataforma aún no muestra esas conversaciones: el cambio entre datos sintéticos y reales es [FE012](../../features/FE012-switch-entre-datos-sinteticos-reales/spec.md).
- **FCR:** para conversaciones de los últimos 7 días del dataset aún no ha pasado la ventana de recontacto, así que su FCR es optimista. Es un **hecho** del cálculo que hay que tener en cuenta al comparar periodos recientes.
- El análisis (summary, main topic, sentimiento, CSAT…) sale de reglas del generador, no de un modelo.
- Desde FE005, los DNI e IBAN ficticios de las conversaciones de voz se enmascaran por defecto y nunca llegan al índice de búsqueda ni a los prompts. Los patrones son españoles más email y tarjeta completa; con datos reales podrían escaparse formatos no previstos (hipótesis, [ADR-007](../decisiones/adr-007-configuracion-global-y-enmascarado.md)).
- La configuración es global y en memoria: se pierde al reiniciar, y si dos administradores la editan a la vez gana la última escritura.
- Usuarios y roles creados desde la UI se pierden al reiniciar (fuera de alcance de FE006). La contraseña demo es la misma para todos, también para los usuarios nuevos ([ADR-003](../decisiones/adr-003-auth-mock-por-roles.md)).
- Flujos y ejecuciones viven en memoria. Si dos personas guardan el mismo flujo, gana el último guardado. Los resultados del prompt son simulados ([ADR-006](../decisiones/adr-006-ejecucion-de-prompts-simulada.md)).
- La búsqueda semántica es léxica: sus limitaciones medidas (puntuaciones bajas, dependencia del diccionario, sesgo hacia texto plantillado) están en [ADR-005](../decisiones/adr-005-busqueda-vectorial-ligera.md).

## Fuentes

- [Spec FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/spec.md)
- [Plan FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/plan.md)
- [ADR-002 — Stack](../decisiones/adr-002-stack-vite-fastapi-mock.md)
- [README del backend](../../backend/README.md)
- [README del frontend](../../frontend/README.md)
- [Spec FE002](../../features/FE002-explorador-de-queries-asistidas/spec.md)
- [Spec FE003](../../features/FE003-busqueda-semantica-de-conversaciones/spec.md)
- [Spec FE004](../../features/FE004-disenador-de-flujos-de-insights/spec.md)
- [Spec FE005](../../features/FE005-configuracion-de-la-plataforma/spec.md)
- [Spec FE006](../../features/FE006-gestion-de-usuarios-y-roles/spec.md)
- [Spec FE010](../../features/FE010-especificacion-openapi-en-configuracion/spec.md)
- [Spec FE011](../../features/FE011-ingesta-de-conversaciones-genesys/spec.md)
- [Contrato de la API entre front y back](contrato-api-front-back.md)
- [Gobierno del vault](../Governance.md)

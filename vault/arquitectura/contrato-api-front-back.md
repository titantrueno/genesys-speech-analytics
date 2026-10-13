---
title: "Contrato de la API entre front y back"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [arquitectura, api, contrato, frontend, backend, http, auth, errores, genesys, ingesta, llm]
created: 2026-10-02
updated: 2026-10-13
---

# Contrato de la API entre front y back

## Resumen

Referencia completa de la API HTTP que el front (React, `frontend/src/`) consume del backend (FastAPI, `backend/app/`) en `v0.7.0` más FE011, FE012, FE013 y FE014: **72 operaciones**, en 9 dominios (más la sonda de salud). FE011 añade 11: los flujos de descarga de Genesys y el conector real; FE012, el origen de datos; FE013, el estado y la prueba de los proveedores de LLM; FE014 no añade operaciones, amplía «Guardar en campos» y el detalle. Para cada una indica permiso, parámetros, cuerpo, respuesta, errores y qué módulo del front la usa. También recoge las convenciones transversales: autenticación, cabecera de versión, identificadores, fechas, paginación y los **seis formatos de error** que conviven.

Es la fuente canónica del contrato. La tabla de endpoints de [backend/README.md](../../backend/README.md) es un resumen. Las decisiones que explican el contrato están en sus ADR (enlazados en cada sección).

## Contexto

- **Cómo se obtuvo** (hecho): el inventario de rutas sale del esquema OpenAPI de la app (`app.openapi()`). Las formas de respuesta se capturaron el 2026-10-02 llamando a cada endpoint con `TestClient`, con `DATA_SEED=42` y `DATA_REFERENCE_DATE=2026-09-27`, y el consumo del front, de buscar `/api/` en `frontend/src/`. Los ejemplos están recortados («…»).
- **OpenAPI (especificación formal):** [backend/openapi.yaml](../../backend/openapi.yaml) (OpenAPI 3.1) describe cada operación con su permiso, sus parámetros, el cuerpo tipado, la respuesta correcta, cada código de error con su forma, la seguridad Bearer y la cabecera `X-Auth-Version`. Con la API arrancada, lo mismo se sirve en `/openapi.json`, `/docs` (Swagger) y `/redoc`, sin sesión.
  - **Consumo desde el front (FE010):** la pestaña «API» de Configuración (`config:view`) descarga `/openapi.json` sin token (`frontend/src/config/openapi/api.ts`; el proxy de Vite la reenvía como `/api`) y la muestra con Swagger UI. Su «Try it out» llama a la misma API con el token de la sesión (`authInterceptor`), así que pasa por `require_permission` como cualquier otra petición; no hay rutas nuevas. El token solo se añade a peticiones dirigidas al origen de la API (el de `VITE_API_URL` o el de la página), nunca a referencias remotas ni a otros orígenes.
  - **Generación:** lo construye `backend/app/openapi/spec.py` sobre el de FastAPI. Los modelos de respuesta (`app/openapi/schemas.py`) son solo documentación: las rutas siguen devolviendo `dict`.
  - **Exportación:** `python scripts/export_openapi.py`.
  - **Garantías:** `tests/test_openapi.py` falla si una ruta no está documentada, si el YAML no está al día o si una respuesta real no cumple su esquema en modo estricto (un campo añadido, quitado, renombrado o de otro tipo). `./scripts/ci.sh` lo valida además con `openapi-spec-validator`.
  - **Reparto:** este documento explica el contrato y su uso desde el front; el YAML es la referencia formal para herramientas (clientes generados, *mocks*, pruebas).
- **Sin versionado de API:** no hay prefijo `/v1` ni negociación. Front y back se despliegan juntos desde el mismo commit ([ADR-002](../decisiones/adr-002-stack-vite-fastapi-mock.md)).

## Conocimiento confirmado

### 1. Convenciones transversales

#### Origen y transporte

- **Base:** rutas absolutas bajo `/api`. En desarrollo, Vite reenvía `/api` a `http://localhost:8000` (`API_PROXY_TARGET`). Con `VITE_API_URL`, el front llama a otro origen y ese origen debe estar en `CORS_ORIGINS` del backend.
- **CORS:** métodos `*`; cabeceras admitidas `Authorization` y `Content-Type`; cabecera expuesta `X-Auth-Version`.
- **Formato:** JSON UTF-8 en cuerpos y respuestas. `204` sin cuerpo. El cliente del front (`api/client.ts`) envía siempre `Accept: application/json` y `Content-Type: application/json` cuando hay cuerpo.
- **Listas en la query:** se repite el parámetro (`?queue=1QU-…&queue=1QU-…`). `buildQuery` omite `undefined`, `null` y `''`.

#### Autenticación ([ADR-003](../decisiones/adr-003-auth-mock-por-roles.md))

- `POST /api/auth/login` devuelve un token **opaco** para el front: payload `{sub, exp}` en base64url más una firma HMAC-SHA256, válido 8 h (`AUTH_TOKEN_TTL_SECONDS`).
- El front lo guarda en `sessionStorage` (`sta.token`) y lo envía como `Authorization: Bearer <token>`.
- En **cada** petición se relee el usuario y su rol: desactivar a un usuario o cambiar los permisos de su rol surte efecto en su siguiente petición sin emitir otro token.
- **Rutas públicas** (sin token): `GET /api/health`, `POST /api/auth/login` y `GET /api/config/public`. **Solo autenticada** (sin permiso concreto): `GET /api/auth/me`. El resto exige al menos un permiso. Dos tests recorren el OpenAPI y lo garantizan (`401` sin token y `403` sin permisos).
- **`401`** (con `WWW-Authenticate: Bearer`): falta el token, está mal formado o manipulado, ha caducado, o el usuario no existe o está desactivado. El front, si tenía token, **cierra la sesión** (`onUnauthorized` → `logout`).
- **`403`:** con sesión, pero sin el permiso: `{"detail": "Falta el permiso explorer:use o flows:view"}`. El front muestra «Sin acceso» antes de llamar, porque las guardas de ruta usan los permisos de `/me`.

#### Permisos

| Permiso | Etiqueta | Lo exige |
|---|---|---|
| `dashboards:view` | Ver dashboards | `/api/metrics/*`; `/api/catalog` (o `conversations:view`) |
| `conversations:view` | Ver conversaciones | `/api/conversations*`; `/api/catalog` (o `dashboards:view`) |
| `explorer:use` | Usar el explorador | `/api/query/run`, `/interpret`, `/saved*`; `/schema` y `/suggest` (o `flows:view`) |
| `search:use` | Usar la búsqueda semántica | `/api/search/*` |
| `flows:view` | Ver flujos | Lecturas de `/api/flows*`, `/validate` y `/sampling/estimate` |
| `flows:edit` | Editar y ejecutar flujos | Crear, renombrar, guardar grafo, duplicar, borrar y ejecutar flujos |
| `config:view` | Ver configuración | Lecturas de `/api/config*` (salvo `/public`) |
| `config:edit` | Editar configuración | Escrituras de `/api/config*` |
| `users:admin` | Administrar usuarios y roles | `/api/users*` y `/api/roles*` |

Los permisos de cada rol son editables desde FE006. El estado inicial está en ADR-003.

#### Cabecera `X-Auth-Version` (FE006)

- **Qué es:** un entero que sube con cada cambio aceptado de usuarios o roles. Vuelve a `0` al reiniciar la API.
- **Cuándo se envía:** en **toda respuesta a una petición con `Authorization`**, también en las de error. Sin sesión no se envía.
- **Qué hace el front:** `api/client.ts` recuerda la última versión vista y, si cambia, avisa a `AuthProvider`, que vuelve a pedir `/api/auth/me` sin pantalla de carga. Así el menú y las guardas siguen a los permisos en la siguiente petición. La referencia se reinicia al cargar, iniciar y cerrar la sesión.

#### Identificadores ([registro](../ingenieria/registro-de-identificadores.md))

- Las entidades usan `PREFIJO-UUID` en mayúsculas: `1CO` conversación, `1CU` cliente, `1US` usuario, `1RO` rol, `1AG` agente, `1QU` cola, `1QY` consulta guardada, `1FL` flujo, `1ND` nodo, `1RN` ejecución, `1TP` main topic, `1TS` tema secundario, `1CK` check, `1CN` conector y `1AU` auditoría.
- **En rutas**, el backend normaliza (`strip` y mayúsculas): `/api/conversations/1co-…` funciona.
- **En filtros**, `queue` y `agent` exigen el prefijo correcto (`422` si no). Los códigos legibles (canal, resolución, riesgo, main topic, KPI, permiso, dashboard) **no** son identificadores.

#### Fechas y periodos

- **Instantes:** ISO 8601 con desfase. Las conversaciones llevan la zona del banco (`"2026-09-26T20:29:49+02:00"`). Los sellos de escritura (auditoría, flujos, ejecuciones, último acceso) van en UTC (`+00:00`). El front formatea todo con `lib/format.ts` en la zona de la plataforma (`GET /api/config/public`).
- **Días** (`from` y `to`, `YYYY-MM-DD`, ambos incluidos): se interpretan en la **zona horaria configurada** (FE005).
- **Periodo por defecto:** 30 días que terminan el día anterior a la fecha de referencia del dataset (`reference_date`, en `/api/catalog` y `/api/query/schema`). Con la referencia 2026-09-27, va del 2026-08-28 al 2026-09-26.
- **Periodo anterior** (resumen de métricas): misma longitud, justo antes de `from`.
- `from > to` → `422` (`"'from' debe ser anterior o igual a 'to'"`).

#### Paginación y orden

La usan `GET /api/conversations` y `POST /api/query/run`:

| Parámetro | Valores | Por defecto |
|---|---|---|
| `page` | ≥ 1 | 1 |
| `page_size` | 1–100 | 25 |
| `sort` | `date`, `duration`, `sentiment` | `date` |
| `order` | `asc`, `desc` | `desc` |

Respuesta: `{total, page, page_size, pages, items}`. Una página fuera de rango devuelve `items: []`. Los empates se resuelven por `id`, así que el orden es estable.

#### Enmascarado de datos personales ([ADR-007](../decisiones/adr-007-configuracion-global-y-enmascarado.md))

- Con `privacy.pii_masking` activado (por defecto), el backend sustituye teléfonos, emails, DNI/NIE, IBAN y tarjetas por `[TELÉFONO]`, `[EMAIL]`, `[DNI]`, `[IBAN]` y `[TARJETA]` **al serializar**: turnos y summary del detalle, summary del listado y del explorador, y turnos de la búsqueda.
- El índice de búsqueda y los prompts de los flujos usan **siempre** texto enmascarado.
- El front no enmascara nada: muestra lo que recibe.

#### Persistencia

Todo lo que se escribe (consultas guardadas, flujos de insights, ejecuciones, configuración, usuarios y roles) vive **en memoria** y se pierde al reiniciar la API. El dataset se regenera con la semilla. La excepción son los flujos de descarga, sus ejecuciones y sus logs (FE011): la API no los guarda, sino que los delega en el servicio de ingesta, que los persiste en PostgreSQL ([ADR-008](../decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)).

#### Códigos HTTP

| Código | Uso |
|---|---|
| `200` | Lectura o actualización correcta |
| `201` | Creación (consulta guardada, flujo, duplicado, tema, check, usuario, rol) |
| `202` | Ejecución de flujo o de descarga aceptada (se procesa en segundo plano) |
| `204` | Borrado correcto, sin cuerpo |
| `401` | Sin sesión válida (ver «Autenticación») |
| `403` | Falta el permiso |
| `404` | La entidad no existe, no es del usuario (consultas guardadas) o el identificador es de otro tipo |
| `409` | Conflicto con el estado: ejecución ya en curso; tema en uso o check del análisis al borrar; rol base o en uso; protecciones de administración; email, código o nombre de rol duplicados (FE006) |
| `422` | Validación: parámetros, cuerpo o reglas de negocio |
| `503` | El servicio de ingesta no está disponible (rutas de descargas y «Probar conexión», FE011) o, con el origen `real`, «Los datos reales no están disponibles» en las secciones de datos (FE012) |

#### Formatos de error

Todos los errores llevan `detail`, pero su forma depende del endpoint. El front los trata así:

| # | Forma de `detail` | Dónde | Cómo lo lee el front |
|---|---|---|---|
| E1 | Texto: `"Conversation not found"` | `401`, `403`, `404`, `409` de estado, y `422` de reglas sueltas (`from > to`, `queue` mal formado, nombre vacío, campo no categórico) | `ApiError.message` = el texto (`actionError` en usuarios y roles) |
| E2 | Lista nativa de FastAPI: `[{type, loc: ["query", "page_size"], msg, input, ctx}]`, con `msg` **en inglés** | Parámetros de query o ruta fuera de rango o tipo, y cuerpos con modelo declarado (`LoginRequest`, `SavedQueryIn`, `FlowName`…) | Mensaje genérico «Error 422» |
| E3 | Lista por campo, en inglés: `[{loc: ["body", "campo"], msg, type}]` | Escrituras de configuración (`422`) y de usuarios y roles (`422` y `409` por duplicado) | `fieldErrors()` → error junto a cada campo (`ConfigField`) |
| E4 | Lista de la consulta: `[{path: "root.conditions[0]", message}]` | `POST /api/query/run`, `/saved` (`query`), `/flows/sampling/estimate` | El explorador marca la condición por su ruta |
| E5 | Lista del grafo: `[{path: "nodes[0].position.y", node_id, message}]` | `PUT /api/flows/{id}/graph` y `POST /api/flows/validate` (integridad) | El editor marca el nodo |
| E6 | Lista de incidencias: `[{code, message, node_id}]` | `POST /api/flows/{id}/runs` (`422` si el flujo no es válido) | Igual que la respuesta de `/validate` |

#### Idioma de los mensajes (FE016, [ADR-010](../decisiones/adr-010-idioma-de-la-interfaz-y-api-en-ingles.md))

- **Todos los mensajes de la API están en inglés** y no dependen del idioma configurado ni de ninguna cabecera: `detail` de errores (E1 a E6), motivos por campo y mensajes de las ejecuciones, log de las descargas (etapas `start`, `authentication`, `search`, `download`, `normalization`, `analysis`, `load`), errores de los servicios de ingesta y de LLM, textos de auditoría y el OpenAPI. La API **no lee `Accept-Language`**.
- **Qué no es un mensaje:** las etiquetas de catálogo (operadores y campos del explorador, KPIs, opciones de flujos, permisos y nombres de rol) y los datos llegan con su texto (en español); el front traduce el catálogo por clave.
- **El front** muestra el `detail` tal cual, también con la interfaz en español. El 503 de datos reales se reconoce por su texto `Real data is not available` (`components/dataErrors.ts`).
- **Prueba:** `backend/tests/test_api_messages_english.py` falla si un mensaje del código o una descripción del OpenAPI está en español, o si el mismo error cambia con el idioma configurado o con `Accept-Language`.

### 2. Mapa de endpoints

| # | Método y ruta | Permiso | Consumidor en el front |
|---|---|---|---|
| 1 | `GET /api/health` | público | — (sondas) |
| 2 | `POST /api/auth/login` | público | `auth/AuthContext.tsx` |
| 3 | `GET /api/auth/me` | autenticado | `auth/AuthContext.tsx` |
| 4 | `GET /api/metrics/summary` | `dashboards:view` | `api/metrics.ts` |
| 5 | `GET /api/metrics/timeseries` | `dashboards:view` | `api/metrics.ts` |
| 6 | `GET /api/metrics/breakdown` | `dashboards:view` | `api/metrics.ts` |
| 7 | `GET /api/catalog` | `dashboards:view` o `conversations:view` | `api/metrics.ts` |
| 8 | `GET /api/conversations` | `conversations:view` | `api/conversations.ts` |
| 9 | `GET /api/conversations/{id}` | `conversations:view` | `api/conversations.ts` |
| 10 | `GET /api/query/schema` | `explorer:use` o `flows:view` | `explorer/api.ts` |
| 11 | `POST /api/query/run` | `explorer:use` | `explorer/hooks.ts` |
| 12 | `GET /api/query/suggest` | `explorer:use` o `flows:view` | `explorer/api.ts` |
| 13 | `POST /api/query/interpret` | `explorer:use` | `explorer/api.ts` |
| 14–18 | `GET/POST /api/query/saved`, `GET/PATCH/DELETE /api/query/saved/{id}` | `explorer:use` | `explorer/api.ts` (no usa el `GET` individual) |
| 19 | `GET /api/search/semantic` | `search:use` | `search/api.ts` |
| 20 | `GET /api/search/similar/{id}` | `search:use` | `search/api.ts` |
| 21–22 | `GET /api/flows`, `POST /api/flows` | `flows:view` / `flows:edit` | `flows/api.ts` |
| 23 | `GET /api/flows/catalog` | `flows:view` | `flows/api.ts` |
| 24 | `POST /api/flows/validate` | `flows:view` | `flows/api.ts` |
| 25 | `POST /api/flows/sampling/estimate` | `flows:view` | `flows/api.ts` |
| 26–28 | `GET/PATCH/DELETE /api/flows/{id}` | `flows:view` / `flows:edit` | `flows/api.ts` |
| 29 | `PUT /api/flows/{id}/graph` | `flows:edit` | `flows/api.ts` |
| 30 | `POST /api/flows/{id}/duplicate` | `flows:edit` | `flows/api.ts` |
| 31–33 | `POST/GET /api/flows/{id}/runs`, `GET /api/flows/{id}/runs/{run_id}` | `flows:edit` / `flows:view` | `flows/api.ts` |
| 34 | `GET /api/config/public` | público | `config/api.ts` (layout y login) |
| 35 | `GET /api/config` | `config:view` | `config/api.ts` |
| 36–38 | `PUT /api/config/general`, `/privacy`, `/ai` | `config:edit` | `config/api.ts` |
| 39–40 | `GET /api/config/connectors`, `POST /api/config/connectors/{id}/sync` | `config:view` / `config:edit` | `config/api.ts` |
| 41 | `GET /api/config/audit` | `config:view` | `config/api.ts` |
| 42–45 | `GET /api/config/taxonomy`, `POST/PUT/DELETE /api/config/taxonomy/{kind}[/{id}]` | `config:view` / `config:edit` | `config/api.ts` |
| 46–49 | `GET/POST /api/config/compliance-checks`, `PUT/DELETE …/{id}` | `config:view` / `config:edit` | `config/api.ts` |
| 50 | `PUT /api/config/kpis/{code}` | `config:edit` | `config/api.ts` |
| 51–53 | `GET/POST /api/users`, `PUT /api/users/{id}` | `users:admin` | `users/api.ts` |
| 54 | `GET /api/users/audit` | `users:admin` | `users/api.ts` |
| 55–58 | `GET/POST /api/roles`, `PUT/DELETE /api/roles/{id}` | `users:admin` | `users/api.ts` |
| 59–60 | `GET /api/config/connectors/genesys`, `POST /api/config/connectors/genesys/test` | `config:view` / `config:edit` | `downloads/api.ts` (tarjeta de Fuentes de datos) |
| 61–62 | `GET/POST /api/download-flows` | `flows:view` / `flows:edit` | `downloads/api.ts` |
| 63–65 | `GET/PUT/DELETE /api/download-flows/{id}` | `flows:view` / `flows:edit` | `downloads/api.ts` |
| 66–68 | `POST/GET /api/download-flows/{id}/runs`, `GET …/runs/{run_id}` | `flows:edit` / `flows:view` | `downloads/api.ts` |
| 69 | `GET /api/download-flows/{id}/runs/{run_id}/log` | `flows:view` | `downloads/api.ts` |
| 70 | `PUT /api/config/sources` | `config:edit` | `config/api.ts` (FE012) |
| 71–72 | `GET /api/config/ai/status`, `POST /api/config/ai/test/{provider}` | `config:view` / `config:edit` | `config/api.ts` (FE013) |

La numeración cuenta operaciones (método más ruta): son las 72 del OpenAPI.

### 3. Autenticación y sesión

**`POST /api/auth/login`** (público). Cuerpo `{email, password}`; el email no distingue mayúsculas.

```json
{"access_token": "<token>", "token_type": "bearer",
 "user": {"id": "1US-…", "name": "Admin Demo", "email": "admin@bancohorizonte.demo",
          "role": "admin", "role_name": "Administrador", "permissions": ["dashboards:view", "…"]}}
```

- `401 "Credenciales incorrectas"` si el usuario no existe, está desactivado o la contraseña no coincide (los tres casos responden igual, sin revelar cuál es).
- Guarda el **último acceso** del usuario.

**`GET /api/auth/me`** (autenticado). Devuelve el mismo `user`. `permissions` sigue el orden del catálogo de permisos. El front lo pide al arrancar con token y cada vez que cambia `X-Auth-Version`.

**`GET /api/health`** (público) → `{"status": "ok"}`. Responde cuando el índice de búsqueda ya está construido (unos 2,5 s tras arrancar).

### 4. Catálogo y métricas (FE001, FE005)

**Filtros comunes de dashboard** (`metrics/*` y `conversations`): `from`, `to`, `channel` (`voz` | `chat`), `queue` (`1QU-…`, repetible), `agent` (`1AG-…`, repetible) y `main_topic` (código, repetible; un código desconocido no da error, sino 0 resultados).

**`GET /api/catalog`.** Valores de los filtros y fecha de referencia:

```json
{"reference_date": "2026-09-27",
 "channels": [{"code": "voz", "label": "Voz"}, {"code": "chat", "label": "Chat"}],
 "queues": [{"id": "1QU-…", "name": "Particulares"}, "…"],
 "agents": [{"id": "1AG-…", "name": "Lucía Márquez", "queue_id": "1QU-…", "queue": "Particulares"}, "…"],
 "main_topics": [{"code": "cargo_no_reconocido", "name": "Cargo no reconocido", "active": true}, "…"],
 "compliance_checks": [{"code": "saludo", "label": "Saludo e identificación del agente"}, "…"],
 "resolutions": [{"code": "resuelta", "label": "Resuelta"}, "…"],
 "churn_risks": [{"code": "bajo", "label": "Bajo"}, "…"]}
```

`main_topics` incluye los desactivados (`active: false`), para poner nombre a filtros antiguos; el front solo ofrece los activos. `compliance_checks` solo trae los activos.

**`GET /api/metrics/summary`.** Filtros comunes y `dashboard` opcional (`vision-general`, `calidad-y-cumplimiento`, `experiencia-de-cliente`…). Con `dashboard`, solo vienen los KPIs configurados para ese dashboard:

```json
{"period": {"from": "2026-08-28", "to": "2026-09-26"},
 "previous_period": {"from": "2026-07-29", "to": "2026-08-27"},
 "kpis": [{"code": "aht_s", "label": "Duración media (AHT)", "unit": "s", "higher_is_better": false,
           "value": 232.02, "previous": 230.42, "delta": 1.6, "delta_pct": 0.69,
           "target": 240, "status": "verde"}, "…"],
 "compliance_by_check": [{"code": "saludo", "label": "…", "value": 93.42, "applicable": 319}, "…"]}
```

- **KPIs** (13, en este orden): `volume`, `aht_s`, `sentiment_avg`, `negative_pct`, `resolution_rate`, `escalation_rate`, `fcr_rate`, `csat_avg`, `effort_avg`, `compliance_rate`, `churn_high_pct`, `first_response_s` (solo chat) y `avg_turns`.
- **Unidades:** `conversaciones`, `s`, `índice` (de -1 a 1), `%`, `1-5` y `turnos`.
- **Nulos:** `value` es `null` cuando no hay conversaciones aplicables (por ejemplo, `first_response_s` en voz).
- **Datos reales (FE012, FE014):** `based_on` dice sobre cuántas conversaciones se calcula un KPI que no usa todas; los del análisis usan las que tienen su dato. `pending` es `true` si ninguna lo tiene y alguna espera análisis.
- **Variación:** `delta` es `null` si falta algún valor. `delta_pct` es `null` si el anterior es 0 o nulo, o si la unidad es `índice` (cruza el cero).
- **Estado:** `status` vale `verde`, `ambar`, `rojo` o `null` (sin umbrales), según los umbrales de Configuración y `higher_is_better`. Un valor igual al umbral toma el color mejor.
- `compliance_by_check` no depende de `dashboard`.

**`GET /api/metrics/timeseries`.** `kpi` (obligatorio, uno de los 13), `granularity` (`day` | `week`) y filtros comunes:

```json
{"kpi": "volume", "granularity": "week", "period": {"from": "2026-08-28", "to": "2026-09-26"},
 "points": [{"period_start": "2026-08-28", "period_end": "2026-08-30", "value": 22}, "…"]}
```

Las semanas son de lunes a domingo, recortadas al periodo (la primera y la última pueden ser parciales). Los días se cuentan en la zona configurada.

**`GET /api/metrics/breakdown`.** `dimension` (`main_topic` | `channel` | `queue` | `agent`) y filtros comunes:

```json
{"dimension": "channel", "period": {"…": "…"},
 "items": [{"key": "voz", "label": "voz", "kpis": {"volume": 192, "aht_s": 90.05, "…": "…", "first_response_s": null}}]}
```

- `key` es el código o el identificador de la dimensión; `label`, su nombre.
- Para `channel`, `label` es el código en crudo (`"voz"`), y el front lo traduce.
- Orden: volumen descendente y, a igualdad, etiqueta.
- `kpis` es un objeto plano de los 13 valores, sin estado.

### 5. Conversaciones (FE001)

**`GET /api/conversations`.** Filtros comunes, paginación y estos filtros de drill-down:

| Parámetro | Valores | Selecciona |
|---|---|---|
| `resolution` | `resuelta`, `no_resuelta`, `escalada` (repetible) | Resolución |
| `churn_risk` | `bajo`, `medio`, `alto` (repetible) | Riesgo de abandono |
| `sentiment_lt` | -1 a 1 | Sentimiento menor que el valor |
| `compliant` | `true` / `false` | Cumple o no todos los checks activos que le aplican |
| `repeat_contact` | `true` / `false` | El cliente vuelve en 7 días (lo contrario del FCR) |

**Contrato de drill-down:** cada elemento de un dashboard navega con el filtro que selecciona el **numerador** de su KPI, y los tests garantizan que `total` coincide con el valor mostrado ([arquitectura](arquitectura-de-la-plataforma.md)).

Elemento del listado (`list_item`, el mismo en explorador, búsqueda y outputs de flujos):

```json
{"id": "1CO-…", "started_at": "2026-09-26T20:29:49+02:00", "channel": "chat",
 "queue_id": "1QU-…", "queue": "Banca digital", "agent_id": "1AG-…", "agent": "Irene Vidal",
 "main_topic": "acceso_banca_digital", "main_topic_label": "Acceso a banca digital",
 "summary": "El cliente escribe porque…", "sentiment": 0.36, "resolution": "resuelta",
 "csat": 4.6, "duration_s": 382}
```

**`GET /api/conversations/{id}`.** Conversación completa, o `404 "Conversación no encontrada"`:

```json
{"id": "1CO-…", "channel": "chat", "started_at": "…", "duration_s": 382, "queue_id": "1QU-…", "queue": "…",
 "agent_id": "1AG-…", "agent": "…", "customer_id": "1CU-…",
 "turns": [{"speaker": "bot", "text": "Hola, soy el asistente…", "offset_s": 0, "sentiment": 0.1}, "…"],
 "analysis": {"summary": "…", "main_topic": "acceso_banca_digital", "secondary_topics": ["claves de acceso", "sms"],
              "sentiment": 0.36, "sentiment_timeline": [0.1, -0.27, "…"], "resolution": "resuelta",
              "csat": 4.6, "effort": 2.1, "churn_risk": "bajo",
              "compliance": {"saludo": true, "bloqueo_preventivo": null, "…": "…"},
              "entities": [{"type": "importe", "value": "…"}], "keywords": ["app", "…"]},
 "main_topic_label": "Acceso a banca digital"}
```

- `speaker`: `cliente`, `agente`, `bot` o `sistema`. `sentiment_timeline` tiene un valor por turno.
- `compliance` es el **cumplimiento efectivo** con los checks activos que tienen resultado: `true` cumple, `false` no cumple y `null` no aplica. `compliance_pending` (FE014) lista los checks activos aún sin resultado en una conversación real.
- Conversaciones reales (FE012, FE014): cada campo del análisis se da en cuanto existe; los que faltan son `null` o vacíos y `pending` es `true` mientras falte alguno de summary, main topic, resolución, CSAT, esfuerzo o riesgo. `sentiment` es el de Genesys o, si falta, el que generó un flujo con LLM.
- `entities.type`: `importe`, `producto`, `fecha` o `comercio`.
- El front abre el detalle en `?turn=N` y desplaza la vista hasta ese turno.

### 6. Explorador de consultas (FE002)

#### Formato de una consulta

```json
{"from": "2026-08-28", "to": "2026-09-26",
 "root": {"op": "and", "conditions": [
   {"field": "channel", "operator": "is", "value": "chat"},
   {"field": "sentiment", "operator": "lt", "value": -0.3},
   {"op": "or", "conditions": [
     {"field": "check:saludo", "operator": "fails"},
     {"field": "transcript", "operator": "contains", "value": "PIN", "speaker": "agente"}]}]}}
```

- `from` y `to` son opcionales: sin ellos se aplica el periodo por defecto, y una consulta guardada sin fechas sigue siendo relativa.
- **Grupos:** `op` es `and` u `or`, con anidamiento máximo de 2 niveles (raíz más uno).
- **Límites:** 50 condiciones por consulta y 200 valores por lista.
- Se rechazan los campos desconocidos (`extra="forbid"`).

| Tipo | Operadores | `value` |
|---|---|---|
| `categorical` | `is`, `is_not` · `in`, `not_in` | Texto · lista no vacía de valores del campo |
| `numeric` | `eq`, `ne`, `gt`, `gte`, `lt`, `lte` · `between` | Número dentro de `[min, max]` · `[mín, máx]` con mín ≤ máx |
| `check` | `passes`, `fails`, `not_applicable` | Se ignora |
| `text` | `contains`, `not_contains` | Texto no vacío; `transcript` admite `speaker` (`cliente`, `agente`, `bot`) |
| `boolean` | `is` | `true` / `false` |

Campos (`GET /api/query/schema` los devuelve con etiquetas, operadores, valores y rangos):

- **Categóricos:** `channel`, `queue` (`1QU-…`, se normaliza), `agent` (`1AG-…`), `main_topic`, `secondary_topic`, `resolution` y `churn_risk`.
- **Numéricos:** `sentiment` (-1 a 1), `csat` (1–5), `effort` (1–5), `duration` (0–86.400 s) y `turns` (0–1.000).
- **Checks:** `check:<código>`, uno por check activo.
- **Texto:** `summary` y `transcript`.
- **Booleano:** `repeat_contact`.

Los main topics y temas secundarios desactivados no se ofrecen en `values`, pero siguen siendo válidos en consultas guardadas.

#### Endpoints

- **`GET /api/query/schema`** → `{fields: [{key, label, type, operators: [{key, label}], values?: [{value, label}], min?, max?, speakers?}], reference_date, default_period: {from, to}}`.
- **`POST /api/query/run`.** Cuerpo: la consulta. Admite paginación por query. Responde `{period, kpis: [{code, label, unit, higher_is_better, value}], total, page, page_size, pages, items}`: los 13 KPIs del resultado, sin estado ni comparación. Errores en formato E4: `{"path": "root.conditions[0]", "message": "Campo desconocido: inventado"}`. El front ejecuta la consulta con un *debounce* de 300 ms.
- **`GET /api/query/suggest?field=&from=&to=`.** Valores de un campo **categórico** en el intervalo, con recuento: `{field, period, values: [{value, label, count}]}`, ordenados por recuento. Un campo no categórico devuelve `422` (E1).
- **`POST /api/query/interpret`** `{text}` (1–500 caracteres) → `{query, unrecognized: [palabras]}`. Convierte una frase en español en una consulta **editable**; no la ejecuta. Un texto vacío o largo devuelve `422` (E1).
- **Consultas guardadas** (`1QY`, **privadas**: la de otro usuario da `404`):
  - `GET /api/query/saved` → `{items}`, de la más reciente a la más antigua por `updated_at`;
  - `POST /api/query/saved` `{name (1–80), query}` → `201`; la consulta se guarda **canónica** (con `speaker: null` explícito y valores normalizados);
  - `GET`, `PATCH` (`{name?, query?}`) y `DELETE` (`204`) sobre `/api/query/saved/{id}`;
  - cada elemento: `{id, name, query, created_at, updated_at}`.

### 7. Búsqueda semántica (FE003, [ADR-005](../decisiones/adr-005-busqueda-vectorial-ligera.md))

**`GET /api/search/semantic`.** Parámetros:

| Parámetro | Valores | Por defecto |
|---|---|---|
| `q` | 1–500 caracteres, no solo espacios | — (obligatorio) |
| `from`, `to`, `channel`, `queue` | Como en los filtros comunes (sin `agent` ni `main_topic`) | Periodo por defecto |
| `min_score` | 0–1 | 0 |
| `group` | `conversation` (el mejor fragmento por conversación) o `fragment` | `conversation` |
| `limit` | 1–100 | 20 |

```json
{"query": "me han cobrado dos veces", "expansions": ["cargo", "cargos", "…"],
 "period": {"from": "…", "to": "…"}, "total": 319, "max_score": 0.4211,
 "results": [{"conversation_id": "1CO-…", "start_turn": 0, "end_turn": 2, "score": 0.4211,
              "turns": [{"index": 1, "speaker": "cliente", "text": "Quiero devolver un recibo…"}, "…"],
              "highlights": ["cobrado", "dos", "…"], "conversation": {"…": "list_item"}}]}
```

- **`total`:** resultados tras el umbral y la agrupación, antes de `limit`.
- **`max_score`:** la mejor puntuación **antes** del umbral (sirve para situar el control en la UI); `null` si no hay coincidencias.
- **`highlights`:** términos de la consulta y de sus expansiones presentes en el fragmento, para resaltarlos.
- **`score`:** similitud coseno con 4 decimales; no es una probabilidad.

**`GET /api/search/similar/{conversation_id}`** → `{conversation_id, results: [{conversation_id, score, conversation}]}`, con las 10 más parecidas. Sin filtros. Si la conversación no existe, `404`.

### 8. Flujos de insights (FE004, [ADR-006](../decisiones/adr-006-ejecucion-de-prompts-simulada.md))

#### Formato del grafo (`version: 1`)

```json
{"version": 1,
 "nodes": [
   {"id": "tmp-s", "type": "sampling", "position": {"x": 0, "y": 0},
    "config": {"query": {"root": {"…": "…"}}, "method": "aleatorio", "size": 3}},
   {"id": "tmp-p", "type": "prompt", "position": {"x": 300, "y": 0},
    "config": {"template": "Clasifica: {{transcripcion}}", "model": "mock-rapido", "temperature": 0.2,
               "output": {"type": "etiqueta", "labels": ["queja", "consulta"]}}},
   {"id": "tmp-o", "type": "output", "position": {"x": 600, "y": 0},
    "config": {"kind": "metrica", "aggregation": "porcentaje", "destination": "Motivos"}}],
 "edges": [{"source": "tmp-s", "target": "tmp-p"}, {"source": "tmp-p", "target": "tmp-o"}]}
```

- **Identificadores de nodo:** `1ND-…` o temporales `tmp-<1–40 caracteres>`. Al guardar, el backend asigna `1ND` a los temporales y devuelve `id_map`.
- **Sampling:**
  - `method`: `aleatorio`, `estratificado` (exige `stratify_by`: `canal`, `cola` o `main_topic`) o `primeros_n` (exige `order_by`: `fecha`, `duracion`, `sentimiento` o `csat`, y `order`: `asc` o `desc`);
  - `size` entre 1 y 1.000;
  - `query` con el formato del explorador.
- **Prompt:**
  - `template` de hasta 4.000 caracteres, con variables `{{transcripcion}}`, `{{summary}}`, `{{main_topic}}`, `{{metadatos}}` y `{{resultado_anterior}}` (esta solo en prompts encadenados);
  - `provider` (FE013): `gemini`, `openai`, `anthropic` o `simulado`; sin él, el nodo es simulado (flujos anteriores);
  - `model`: uno del proveedor (`mock-rapido` y `mock-preciso` en el simulado);
  - `temperature` de 0 a 1; solo se envía a los modelos que la admiten (`providers[].models[].temperature` del catálogo);
  - `output.type`: `texto`, `etiqueta` (de 2 a 20 `labels`, hasta 60 caracteres) o `json` (de 1 a 40 `fields` `{name, type: texto|numero|booleano|lista, options?}`; `options`, hasta 100 valores permitidos de un campo de texto o de cada elemento de una lista, que el LLM recibe como `enum`; `lista` es una lista de textos, FE014).
- **Output:** `kind` es `tabla`, `metrica` (exige un prompt de etiqueta; `aggregation`: `recuento` o `porcentaje`), `informe` o `campo` (FE013); `destination` tiene hasta 80 caracteres y es único (no se pide en `campo`).
  - **`campo`** («Guardar en campos de la conversación»): hasta 60 `mappings: [{target, source?}]` (`source`, un campo del JSON del Prompt; sin él, la respuesta entera de un Prompt de texto o etiqueta, solo para summary o main topic) y `overwrite` (`false` por defecto). Solo con datos reales. Un Prompt JSON con varios campos guarda todos con una llamada por conversación.
  - `target` (FE014): `summary`, `main_topic`, `resolution`, `csat`, `effort`, `churn_risk`, `sentiment`, `secondary_topics`, `keywords`, `entity:<importe|producto|fecha|comercio>` o `compliance:<código de check>`. Cada destino exige un campo JSON de su tipo: texto con valores permitidos válidos para resolución, riesgo y checks (`cumple`, `no_cumple`, `no_aplica`), número para CSAT, esfuerzo y sentimiento, lista con temas secundarios activos o lista libre para palabras clave, y texto para entidades.
- **Conexiones:** solo `sampling → prompt`, `prompt → prompt` y `prompt → output`, sin ciclos. Límites: 50 nodos y 100 conexiones.
- **Dos niveles de validación:**
  - **integridad**, siempre exigida al guardar (`422` E5: tipos, rangos, identificadores, conexiones imposibles);
  - **completitud**, que no impide guardar, pero sí ejecutar. Devuelve incidencias E6 con `code`: `missing_sampling`, `missing_output`, `node_unconfigured`, `invalid_config`, `disconnected_node`, `prompt_without_variables`, `unknown_variable`, `previous_result_without_chain`, `metric_requires_labels` o `duplicate_destination`; desde FE013, también `model_not_in_provider`, `provider_without_key`, `llm_unavailable`, `invalid_mapping`, `summary_requires_text`, `main_topic_requires_taxonomy`, `duplicate_target` y `field_output_requires_real_data`, y el aviso (`severity: warning`) `simulated_values_to_real_data` cuando un Prompt simulado alimenta «Guardar en campos»; desde FE014, `unknown_check` (un `compliance:<código>` de un check borrado o desactivado).

#### Endpoints

- **`GET /api/flows`** → `{items: [{id, name, author: {id, name}, created_at, updated_at, status: "valido"|"con_errores", last_run: {id, created_at, status} | null}]}`, del modificado más recientemente al más antiguo.
- **`POST /api/flows`** `{name (1–80), template?}` → `201`, el flujo con su grafo vacío o, con `template` (`summary`, `main_topic`, `summary_main_topic`), ya configurado con la taxonomía activa y el proveedor por defecto (FE013); desde FE014, también `analisis_completo` («Generar análisis completo»), que responde `422` con el motivo si los checks activos no caben en una llamada.
- **`GET /api/flows/catalog`** → opciones con `{value, label}` de `node_types`, `sampling_methods`, `strata`, `order_keys`, `orders`, `models`, `variables`, `output_formats`, `field_types`, `output_kinds`, `target_fields`, `templates` y `aggregations`; además, `providers` (con sus modelos y si admiten temperatura), `default_provider` y `default_model` (los de Configuración, que toma un Prompt nuevo), `origin` (origen de datos activo) y `limits` (con `max_mappings` desde FE014). `target_fields` lleva además `group` (`analisis`, `cumplimiento` o `entidades`) y un `compliance:<código>` por check activo (FE014).
- **`POST /api/flows/validate`** (grafo) → `{valid, issues: [{code, message, node_id}]}`. Un grafo sin integridad responde `422` E5.
- **`POST /api/flows/sampling/estimate`** `{query, size?}` → `{available, sample_size, period}`: cuántas conversaciones cumplen los filtros y cuántas tendría la muestra.
- **`GET /api/flows/{id}`** → el resumen más `graph`. **`PATCH`** `{name}` lo renombra. **`DELETE`** → `204` (borra también sus ejecuciones).
- **`PUT /api/flows/{id}/graph`** (grafo completo, reemplaza el anterior) → el flujo más `id_map: {"tmp-s": "1ND-…"}`. El front reescribe sus claves con `id_map`.
- **`POST /api/flows/{id}/duplicate`** → `201`, «Copia de …» con nodos `1ND` nuevos.
- **`POST /api/flows/{id}/runs`** → **`202`** con la instantánea inicial (`status: "pendiente"`):
  - `422` E6 si el flujo no es válido;
  - `409` si ya hay una ejecución en curso de ese flujo;
  - la ejecución corre en segundo plano, a un ritmo de `FLOW_RUN_STEP_DELAY_MS` (15 ms por elemento).
- **`GET /api/flows/{id}/runs`** → `{items: [resumen]}`, de la más reciente a la más antigua. Se conservan las 50 últimas por flujo.
- **`GET /api/flows/{id}/runs/{run_id}`** → la instantánea completa:

```json
{"id": "1RN-…", "created_at": "…", "started_at": "…", "finished_at": "…", "duration_ms": 1,
 "status": "ok", "sample_size": 3, "user": {"id": "1US-…", "name": "Admin Demo"},
 "flow_id": "1FL-…", "seed": 1109677792, "graph": {"…": "copia del grafo ejecutado"},
 "nodes": {"1ND-…": {"status": "ok", "processed": 3, "total": 3, "message": null, "rejected": 0, "failed": 0}},
 "failures": {"1ND-…": [{"conversation_id": "1CO-…", "status": "rechazado", "reason": "…"}]},
 "outputs": {"1ND-…": {"node_id": "1ND-…", "kind": "metrica", "destination": "Motivos",
                       "result": {"aggregation": "porcentaje", "total": 3,
                                  "items": [{"label": "queja", "count": 1, "percent": 33.3}, "…"]}}}}
```

- **Estados** (de la ejecución y de cada nodo): `pendiente`, `en_curso`, `ok` o `error`. `message` explica el error de un nodo.
- **`result` según el tipo de output:**
  - `tabla`: `{rows: [{conversation: list_item, result}]}`, donde `result` es texto, etiqueta u objeto JSON según el prompt;
  - `metrica`: `{aggregation, total, items: [{label, count, percent}]}`, con porcentajes de un decimal que suman exactamente 100;
  - `informe`: `{text}`;
  - `campo` (FE013): `{targets, rows: [{conversation, values, states, reason, reasons}], counts: {campo: {escrito, omitido, rechazado, sin_valor, error}}}`, con una fila por conversación que llegó al Prompt. Desde FE014, un valor no válido deja solo su campo en `rechazado`, `sin_valor` es una entidad o lista vacía, `values` va tipado (checks como `true|false|null`) y `reasons` da el motivo por campo (rechazo, ya tenía valor, Genesys ya da el sentimiento).
- **Prompts con LLM (FE013):** `rejected` cuenta respuestas fuera de formato y `failed` conversaciones sin respuesta del proveedor; `failures` da el motivo de cada una. Se excluyen de los outputs.
- **Progreso por *polling*:** el front pide la instantánea cada 500 ms mientras el estado es `pendiente` o `en_curso` (`RUN_POLL_MS`, `staleTime: 0`). No hay WebSocket ni SSE.

### 9. Configuración (FE005, [ADR-007](../decisiones/adr-007-configuracion-global-y-enmascarado.md))

Toda escritura aceptada sube `version` y crea una entrada de auditoría `1AU`. Una escritura que no cambia nada no hace ninguna de las dos cosas. Todos los cuerpos rechazan campos desconocidos, con errores E3.

- **`GET /api/config/public`** (público) → `{platform_name, timezone, language}`. La usan el login y todos los roles.
- **`GET /api/config`** → `{version, general, sources: {origin}, privacy: {pii_masking}, ai: {provider, model, simulated} (`simulated` solo con el proveedor `simulado`), kpis: [{code, label, unit, higher_is_better, target, green, amber, dashboards}], options: {languages, timezones, providers: [{value, label, models: [{value, label, temperature}]}], sections, dashboards}}`.
- **`GET /api/config/ai/status`** (FE013) → `{service: "disponible", providers: [{value, label, key_configured}]}`; `503` si el servicio de LLM no responde. **`POST /api/config/ai/test/{provider}`** `{model}` (`config:edit`) → `{ok, provider, model, message}`; un error del proveedor (sin clave, clave rechazada) es `200` con `ok: false`; un modelo de otro proveedor, `422`.
- **`PUT /api/config/general`** `{platform_name (1–60), timezone (IANA), language ("es-ES" o "en-US")}`. **`PUT /api/config/privacy`** `{pii_masking}`. **`PUT /api/config/ai`** `{provider, model}` (el modelo debe ser del proveedor). Las tres responden con la configuración completa.
- **`PUT /api/config/kpis/{code}`** `{target, green, amber, dashboards}`:
  - los valores deben estar dentro del rango de la unidad;
  - `green` y `amber`, los dos o ninguno, y coherentes con el sentido del KPI (si más es mejor, `amber < green`);
  - respuesta: la configuración completa;
  - un KPI desconocido da `404`.
- **`GET /api/config/connectors`** → `{items: [{id: "1CN-…", name, channel, status: "conectado", last_sync, conversations}]}`. **`POST …/{id}/sync`** simula una sincronización: actualiza `last_sync` y devuelve el conector, sin cambiar el dataset.
- **`GET /api/config/taxonomy`** → `{main_topics: [...], secondary_topics: [...]}`; cada tema: `{id: "1TP-…"|"1TS-…", code, name, description, keywords, active, conversations}`.
  - **Crear o editar:** `POST /api/config/taxonomy/{main-topics|secondary-topics}` y `PUT …/{id}` con `{code, name (1–80), description (≤300), keywords (≤30, cada una ≤60), active}`.
  - **Código:** `snake_case` en los main topics; texto en minúsculas con espacios en los temas secundarios (`"compras online"`). Es único e inmutable: cambiarlo al editar da `422`.
  - **Nombres:** los de main topic son únicos (`422`).
  - **Borrar:** `DELETE …/{id}` → `204`; un tema en uso da `409` (se desactiva en su lugar). Desde FE013, un main topic se comprueba también en las conversaciones reales, sea cual sea el origen activo (el `409` da el recuento de cada origen; `503` si PostgreSQL no responde).
- **`GET/POST /api/config/compliance-checks`**, **`PUT/DELETE …/{id}`**:
  - cuerpo `{code, name, description, phrases (1–20, cada una ≤120), channel: voz|chat|ambos, active}`;
  - la respuesta añade `id` (`1CK-…`), `evaluation` (`analisis` en los seis originales, `frases` en los nuevos) y `builtin`;
  - un código o nombre duplicado da **`422`** (no `409`, a diferencia de FE006);
  - borrar un check del análisis da `409`.
- **`GET /api/config/audit?section=`** → `{items: [{id: "1AU-…", user: {id, name}, at, section, element, before, after}]}`, de la más reciente a la más antigua.
  - `section` ∈ `general`, `fuentes`, `taxonomia`, `kpis`, `cumplimiento`, `privacidad`, `modelos`;
  - solo devuelve secciones de configuración, aunque el registro sea compartido con FE006.
- **En el front**, toda mutación de configuración invalida **todas** las consultas en caché, porque un cambio puede afectar a cualquier sección.

### 10. Usuarios y roles (FE006, [ADR-003](../decisiones/adr-003-auth-mock-por-roles.md))

Toda escritura pasa por las **protecciones**, que devuelven `409` con el motivo en texto (E1):

- nadie se quita a sí mismo `users:admin`;
- debe quedar al menos un usuario activo con el rol `admin`;
- el rol `admin` conserva `users:admin`.

Cada cambio aceptado sube `X-Auth-Version` y audita en la sección `usuarios`.

- **`GET /api/users?q=&role=&active=`** → `{items: [{id: "1US-…", name, email, role, role_name, active, last_login}]}`, ordenados por nombre.
  - `q` (≤100) busca en nombre o email, sin distinguir tildes ni mayúsculas;
  - `role` es el código del rol (uno desconocido devuelve una lista vacía);
  - `active` es `true` o `false`;
  - `last_login` es `null` si el usuario no ha entrado nunca.
- **`POST /api/users`** `{name (1–80), email, role, active?}` → `201`. El email se guarda sin espacios y en minúsculas, y debe tener la forma `algo@dominio.tld`. Un email duplicado da **`409` E3** en `email`; un rol desconocido, `422` en `role`. El usuario nuevo entra con la contraseña demo.
- **`PUT /api/users/{id}`** `{name, email, role, active}` (completo; desactivar = `active: false`) → el usuario. Si no existe, `404`. Desactivar invalida su sesión en la siguiente petición (`401`).
- **`GET /api/roles`** → `{items: [{id: "1RO-…", code, name, builtin, permissions, users}], permissions: [{value, label}]}`. `permissions` es el catálogo de los 9 permisos con su etiqueta, para la matriz.
- **`POST /api/roles`** `{code (^[a-z][a-z0-9_]{1,39}$), name (1–40), permissions}` → `201`. Un código o nombre duplicado (sin tildes ni mayúsculas) da **`409` E3**; un permiso desconocido, `422`.
- **`PUT /api/roles/{id}`** `{name, permissions}` (lista completa; se devuelve en el orden del catálogo y sin duplicados). Renombrar un rol base da `422`.
- **`DELETE /api/roles/{id}`** → `204`. Un rol base o con usuarios da `409`.
- **`GET /api/users/audit`** → el registro de la sección `usuarios`. `before` y `after` son `{name, email, role, active}` para usuarios y `{name, permissions}` para roles; `null` en altas y bajas.

### 11. Flujos de descarga y conector de Genesys (FE011, [ADR-008](../decisiones/adr-008-postgresql-y-servicio-de-ingesta.md))

La API no guarda nada: comprueba la sesión y los permisos y delega en el servicio de ingesta (`app/ingestion_client.py`, `INGESTION_URL` e `INGESTION_TOKEN`).

- **Qué añade la API:** la autoría de quien crea, la zona horaria vigente de la plataforma al crear y al guardar, y quién lanza una ejecución. Ignora la autoría y la zona horaria que envíe el cliente.
- **Errores:**
  - `404` y `409` se reenvían tal cual (E1);
  - los `422` se reducen a `loc`, `msg` y `type` (E3, sin `input`);
  - si el servicio no responde, responde `401` (tokens distintos) o `5xx`, o falta el token, la API devuelve `503` con «El servicio de ingesta no está disponible».

**Flujo de descarga:** `{id, name, interval, channels, schedule, active, overwrite, timezone, author, created_at, updated_at, next_run_at, last_run}`. `overwrite` (FE013, `false` por defecto): sin marcar, las conversaciones que ya están en la base no se descargan; marcado, se sustituyen y se borran su summary y main topic.

- `interval` es relativo (`{type: "relativo", unit: "hoy"|"ayer"|"horas"|"dias", amount}`, con horas de 1 a 720 y días de 1 a 90) o específico (`{type: "especifico", from, to}`, en hora local, sin zona, como mucho 90 días y sin futuro).
- `schedule` es `{type: "desactivada"}`, `{type: "cada_horas", hours}` (de 1 a 24, alineadas con la medianoche) o `{type: "diaria", time: "HH:MM"}`. Una programación necesita un intervalo relativo.

**Ejecución:** `{id, flow_id, origin: manual|programada, status: pendiente|en_curso|completada|completada_con_avisos|error, interval: {from, to}, channels, overwrite (nulo en las anteriores a FE013), counters, error, started_by, created_at, started_at, finished_at, duration_s}`.

- `counters` lleva `found`, `downloaded`, `inserted`, `updated`, `skipped` (en curso o de otro canal), `skipped_existing` (ya en la base, sin «Sobrescribir»; FE013), `errors`, `by_channel`, `by_quality` y `undelivered_messages`. Al terminar, `found = inserted + updated + skipped + skipped_existing + errors`.
- `POST …/runs` devuelve `202` con la ejecución `pendiente`, o `409` si ya hay una activa. El front consulta `GET …/runs/{run_id}` cada 2 s hasta que termina.

**Log:** `GET …/runs/{run_id}/log?after=&level=` devuelve `{items: [{id, at, level: info|aviso|error, stage, message, genesys_id}]}`, con `after` como cursor. Con `format=text`, devuelve el log completo como adjunto `text/plain`. Nunca contiene el texto de los turnos ni secretos.

**Conector:**

- `GET /api/config/connectors/genesys` devuelve `{service: disponible|no_disponible, region, credentials_configured, database, last_test, last_download, conversations: {total, by_channel, by_quality}}`. Con el servicio caído, responde `200` con `service: no_disponible` y el resto nulo.
- `POST …/genesys/test` devuelve `{ok, at, organization, region, message}`. Unas credenciales malas son `200` con `ok: false`.

### 12. Integración en el front

- **Cliente único:** `apiRequest<T>(path, {method, body, query, signal})` en `frontend/src/api/client.ts`.
  - Añade el token y serializa el cuerpo.
  - Vigila `X-Auth-Version`.
  - Ante una respuesta no correcta lanza `ApiError(status, message, detail)`: `message` es `detail` si es texto, o `Error <código>` si no.
  - Un `401` con token dispara `onUnauthorized`.
  - Las peticiones se cancelan con el `AbortSignal` de TanStack Query.
- **Caché (TanStack Query 5):**
  - por defecto, `staleTime` de 60 s, sin reintentos y sin recargar al volver a la ventana;
  - las claves siguen el recurso: `['metrics', 'summary', filtros, dashboard]`, `['conversations', query]`, `['conversation', id]`, `['query-run', consulta, opciones]`, `['search', 'semantic', parámetros]`, `['flow-run', flowId, runId]`, `['users', filtros]`, `['roles']`…
- **Invalidación tras escribir:**

| Mutación | Invalida |
|---|---|
| Configuración | Todas las consultas |
| Usuarios y roles | Todas las consultas (la mutación sigue pendiente hasta que termina la recarga) |
| Consultas guardadas | `['saved-queries']` |
| Flujos | La lista de flujos; al ejecutar, también `['flow-runs', id]` |

- **Datos remotos:** todo componente maneja cargando, error y vacío ([lecciones](../aprendizaje/lecciones-construccion-plataforma.md)).

## Límites y excepciones

- **Seis formatos de error** (E1–E6): es un hecho heredado de cada feature, no una decisión. Un cliente nuevo debe distinguirlos por endpoint. Unificarlos (por ejemplo, con `application/problem+json`) sería una decisión nueva con su ADR.
- **Mensajes en inglés:** los errores nativos de FastAPI (E2) y algunos de integridad del grafo (E5, como `"Field required"`) salen en inglés; el resto, en español.
- **Duplicados con códigos distintos:** en Configuración, un código o nombre duplicado responde `422`; en Usuarios y roles, `409`. La UI muestra los dos junto al campo.
- **Sin uso desde el front:** `GET /api/health` y `GET /api/query/saved/{id}`.
- **Modelos de respuesta solo documentales:** las rutas devuelven `dict` y FastAPI no valida la salida contra `app/openapi/schemas.py`. La coherencia la garantiza el test de contrato, que recorre las 72 operaciones con respuestas reales, no el tipado de las rutas.
- **Hipótesis no verificada:** el contrato no se ha probado con clientes que no sean el front (por ejemplo, integraciones de terceros). Varias respuestas exponen detalles pensados para la UI (`label`, `max_score`, `options`).
- **Mantenimiento:** al añadir o cambiar una ruta, documéntala en `app/openapi/spec.py` (si no, la API no arranca su `/openapi.json` y la suite falla), regenera `backend/openapi.yaml` y actualiza este documento en el mismo cambio.

## Origen de datos (FE012)

- `PUT /api/config/sources` (`config:edit`, auditado en `fuentes`) cambia el origen; `GET /api/config` devuelve `sources.origin` y `GET /api/catalog`, `origin`, `queues` y `agents` del origen activo.
- Listado: `phone` (ANI exacto, con o sin +34) y `external_tag` (exacto) y los campos `analysis_pending`, `ani`, `external_tag`, `contained_in_bot` y `transcript_quality`. Los campos del análisis pueden ser `null`.
- Detalle: `genesys` con tramos, temas, métricas y contención; `analysis.pending`; `turns[].delivered`.
- KPIs: `pending` y `based_on` en `/summary`; `pending` en `/timeseries` y `/breakdown`.
- Explorador: operadores `is_empty` e `is_not_empty` y campos `gc_*` solo con el origen `real`. Flujos: las incidencias de `/validate` pueden llevar `severity: "warning"`.

## Fuentes

- [Spec FE016](../../features/FE016-idioma-ingles-de-la-interfaz/spec.md) y [ADR-010](../decisiones/adr-010-idioma-de-la-interfaz-y-api-en-ingles.md)

- [Routers del backend](../../backend/app/routers/): `auth.py`, `metrics.py`, `conversations.py`, `query.py`, `search.py`, `flows.py`, `config.py` y `users.py`
- [Aplicación, CORS y middleware](../../backend/app/main.py) · [Autenticación](../../backend/app/auth.py) · [Filtros](../../backend/app/services/filters.py) · [Paginación](../../backend/app/services/listing.py) · [Modelo de consulta](../../backend/app/query/model.py) · [Modelo de grafo](../../backend/app/flows/model.py)
- [Cliente HTTP del front](../../frontend/src/api/client.ts) · [Sesión](../../frontend/src/auth/AuthContext.tsx) · [Pestaña «API»](../../frontend/src/config/tabs/ApiTab.tsx) · [Spec FE010](../../features/FE010-especificacion-openapi-en-configuracion/spec.md)
- [Tests de recorrido de rutas](../../backend/tests/test_auth.py) · [OpenAPI exportado](../../backend/openapi.yaml) · [Construcción del OpenAPI](../../backend/app/openapi/spec.py) · [Tests de contrato](../../backend/tests/test_openapi.py)
- [Arquitectura de la plataforma](arquitectura-de-la-plataforma.md) · [ADR-003](../decisiones/adr-003-auth-mock-por-roles.md) · [ADR-005](../decisiones/adr-005-busqueda-vectorial-ligera.md) · [ADR-006](../decisiones/adr-006-ejecucion-de-prompts-simulada.md) · [ADR-007](../decisiones/adr-007-configuracion-global-y-enmascarado.md) · [Registro de identificadores](../ingenieria/registro-de-identificadores.md)
- [Rutas de descargas](../../backend/app/routers/downloads.py) · [Cliente del servicio de ingesta](../../backend/app/ingestion_client.py) · [Rutas internas del servicio](../../backend/ingestion/api.py) · [Front de descargas](../../frontend/src/downloads/api.ts) · [Spec FE011](../../features/FE011-ingesta-de-conversaciones-genesys/spec.md)
- [FastAPI — Handling Errors](https://fastapi.tiangolo.com/tutorial/handling-errors/) (formato E2) · [FastAPI — CORS](https://fastapi.tiangolo.com/tutorial/cors/)

---
title: "Arquitectura de la plataforma"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [arquitectura, frontend, backend, api, mock, busqueda, flujos]
created: 2026-09-27
updated: 2026-09-28
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
| Auth | `backend/app/auth.py` | Usuarios demo, token HMAC y `require_permission` (ver [ADR-003](../decisiones/adr-003-auth-mock-por-roles.md)). |
| Identificadores | `backend/app/ids.py` | `PREFIJO-UUID` (ver el [registro](../ingenieria/registro-de-identificadores.md)). |
| Búsqueda semántica | `backend/app/search/` | Índice por fragmentos construido al arrancar, interfaz `SearchEngine`, TF-IDF y diccionario de sinónimos (ver [ADR-005](../decisiones/adr-005-busqueda-vectorial-ligera.md)). |
| Flujos de insights | `backend/app/flows/` | Formato JSON del flujo, integridad y reglas de conexión, validación, sampling, prompt simulado detrás de `PromptRunner`, outputs y ejecuciones en segundo plano (ver [ADR-006](../decisiones/adr-006-ejecucion-de-prompts-simulada.md)). |
| Front | `frontend/src/` | Sesión, navegación por permisos, dashboards, listado, detalle, explorador, búsqueda semántica y diseñador de flujos. |

### Flujo de datos

1. El front autentica con `POST /api/auth/login` y envía `Authorization: Bearer` en cada petición. En desarrollo, el proxy de Vite reenvía `/api` al puerto 8000.
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
- **Ejecución:** `POST /api/flows/{id}/runs` valida, crea la ejecución (`1RN`, con copia del grafo y semilla) y la ejecuta en segundo plano (`BackgroundTasks`) en orden topológico. Cada nodo informa de estado y procesados; el front consulta el detalle cada 500 ms hasta que termina. El estado se protege con un cerrojo por ejecución y el arranque es atómico (`409` si ya hay una en curso).
- **Sampling real** sobre el dataset: aleatorio con semilla, estratificado proporcional (restos mayores) o primeros N por un criterio.
- **Permisos:** lecturas con `flows:view` y escrituras y ejecuciones con `flows:edit`. El esquema y las sugerencias de campos de FE002 aceptan también `flows:view`, porque los usa el nodo Sampling.
- **Front:** React Flow (`@xyflow/react`) en rutas diferidas: listado, editor (paleta arrastrable o con botón, lienzo, paneles por nodo, validar, guardar y ejecutar), ejecución (lienzo de solo lectura con progreso y pestañas por output) e historial.

### Rendimiento

- Con el dataset completo, cada endpoint responde en menos de 500 ms (hay tests con ese umbral). Una ejecución de flujo tarda unos 15 ms por conversación y prompt (retardo simulado configurable): 40 conversaciones con 2 prompts, unos 2 s. La búsqueda semántica tarda unos 12 ms de mediana sobre 90 días (55 ms en el peor caso medido, con consultas de 500 caracteres). A cambio, el arranque tarda unos 2,5 s y el índice retiene unos 52 MB, con un pico transitorio de unos 260 MB durante la construcción.
- En el front, el dashboard y los flujos se cargan en diferido: la carga inicial ocupa unos 448 kB, Recharts va en un chunk de unos 347 kB y React Flow, en otro de unos 176 kB, compartido por el editor y la vista de ejecución.

## Límites y excepciones

- Sin persistencia: todo cambio de estado se pierde al reiniciar la API.
- **FCR:** para conversaciones de los últimos 7 días del dataset aún no ha pasado la ventana de recontacto, así que su FCR es optimista. Es un **hecho** del cálculo que hay que tener en cuenta al comparar periodos recientes.
- El análisis (summary, main topic, sentimiento, CSAT…) sale de reglas del generador, no de un modelo.
- Las conversaciones de voz muestran DNI e IBAN ficticios sin enmascarar hasta FE005. La búsqueda semántica indexa los números como palabras, así que buscar un DNI encuentra sus conversaciones; FE005 debe enmascararlos también en el índice.
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

# FE001 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-09-27. Siguiente paso: `/build`, una tarea cada vez y en orden.

## Contraste con el vault

| Entrada | Estado | Impacto |
|---|---|---|
| [Propósito del proyecto](../../vault/producto/proposito-del-proyecto.md) | `draft` | Se actualiza y pasa a `active` (T9). |
| [Arquitectura del harness](../../vault/arquitectura/arquitectura-del-harness.md) | `active` | No se invalida; se enlaza desde la nueva arquitectura de la plataforma (T9). |
| [Decisiones](../../vault/decisiones/Index.md) | Solo ADR-001 | Los números ADR-002 y ADR-003 están libres (T1 y T2). |
| [Glosario](../../vault/glosario/terminos-del-harness.md) | `active` | Se amplía (T9). |
| [Ciclo de entrega](../../vault/ingenieria/ciclo-de-entrega.md) | `active` | Se añaden los comandos de front y back (T9). |
| [Gobierno del vault](../../vault/Governance.md) | Reglas | Las credenciales demo y el secreto del token no se escriben en el vault; solo en el README del backend, marcados como demo. |

No se han encontrado decisiones previas que contradigan la spec.

## Entorno verificado

Node 26.8, npm 11.19 y Python 3.14.7 de Homebrew. Como PEP 668 bloquea `pip install` global, el backend usará un venv propio en `backend/.venv` con `requirements.txt`. No hay repositorio Git: la regla «una tarea = un commit» de `/build` exige ejecutar `git init` antes de T1.

## Estructura objetivo

```text
backend/
  app/
    main.py            # FastAPI, CORS, routers
    auth.py            # login mock, token, dependencia de permisos
    data/              # catálogo, plantillas y generador determinista
    services/          # filtros, KPIs, listado
    routers/           # health, auth, catalog, metrics, conversations
  tests/
  requirements.txt
  README.md
frontend/
  src/
    api/  auth/  layout/  pages/  components/
  package.json  vite.config.ts  tailwind.config
```

## Tareas

| Id | Título | Criterio de «hecho» | Depende de | Criterios de la spec |
|---|---|---|---|---|
| T1 | Backend base y dataset mock bancario | Ver detalle T1 | `git init` | 1 (back), 2, 6, 7, 8, 9 |
| T2 | Auth mock y permisos por rol | Ver detalle T2 | T1 | 3, 4 (back) |
| T3 | API de métricas y KPIs | Ver detalle T3 | T1, T2 | 12, 13 (back), 14, 25 |
| T4 | API de conversaciones y catálogo | Ver detalle T4 | T1, T2 | 16 (back), 17 (back), 25 |
| T5 | Front base: login, layout y navegación | Ver detalle T5 | T2 | 1 (front), 4 (front), 5 |
| T6 | Dashboards y filtros globales | Ver detalle T6 | T3, T5 | 10, 11, 12, 13, 14 |
| T7 | Drill-down y listado de conversaciones | Ver detalle T7 | T4, T6 | 15, 16, 17 |
| T8 | Detalle de conversación tipo chat | Ver detalle T8 | T4, T7 | 18–23 |
| T9 | Conocimiento, documentación y verificación final | Ver detalle T9 | T1–T8 | 24 y Conocimiento afectado |

### T1 — Backend base y dataset mock bancario

- **Qué:** proyecto FastAPI en `backend/` con venv, `requirements.txt` (fastapi, uvicorn, pydantic, pytest, httpx) y `GET /api/health`. Catálogo de 15 main topics, 7 colas, agentes ficticios y checks de cumplimiento. Generador determinista (`seed`, `reference_date`) de 1.000 conversaciones con plantillas por main topic (varias por topic, con variación de importes, comercios, productos y desenlace), turnos con sentimiento, summary y análisis correlacionado.
- **Hecho cuando:** `pytest` pasa en verde con tests que primero fallan y que comprueban:
  - health `200`;
  - dos generaciones idénticas con la misma semilla;
  - 1.000 conversaciones en 90 días;
  - `main_topic` válido y `summary` de 2 a 4 frases en todas;
  - la transcripción contiene una expresión característica de su topic;
  - los 15 topics presentes, con `cargo_no_reconocido` y `acceso_banca_digital` en el top 5 y `cargo_no_reconocido` mayoritario en «Fraude y seguridad»;
  - ningún número de tarjeta completo (regex).
- **Conocimiento:** crear `vault/producto/catalogo-de-main-topics.md` (fuente canónica del catálogo) y `vault/decisiones/adr-002-stack-vite-fastapi-mock.md`, enlazarlos desde sus índices y dejar la auditoría en verde.

### T2 — Auth mock y permisos por rol

- **Qué:** 4 usuarios demo (uno por rol), `POST /api/auth/login` y `GET /api/auth/me`, token HMAC con caducidad (el secreto sale de una variable de entorno, con un valor por defecto solo para dev), permisos por rol y una única dependencia `require_permission(...)` usada por todos los routers de datos.
- **Hecho cuando:** hay tests para:
  - login válido → token;
  - login inválido → `401`;
  - endpoint sin token o con token manipulado o caducado → `401`;
  - matriz rol × endpoint → `403` donde corresponde;
  - un test que recorre todas las rutas `/api` salvo health y login y falla si alguna no exige auth.
- **Conocimiento:** crear `vault/decisiones/adr-003-auth-mock-por-roles.md` con los riesgos (solo demo) y enlazarla desde el índice.

### T3 — API de métricas y KPIs

- **Qué:** módulo de filtros común (fechas, canal, cola, agente, main topic) y endpoints:
  - `GET /api/metrics/summary`: los 13 KPIs con valor, valor del periodo anterior equivalente y variación en %;
  - `GET /api/metrics/timeseries`: granularidad día o semana;
  - `GET /api/metrics/breakdown`: por canal, cola, agente o main topic.
- **Hecho cuando:**
  - cada KPI coincide con un cálculo independiente escrito en el test sobre el dataset, en al menos dos combinaciones de filtros;
  - el periodo anterior tiene la misma longitud que el actual;
  - la suma de los desgloses es igual al volumen total;
  - los tres endpoints responden en menos de 500 ms con el dataset completo.

### T4 — API de conversaciones y catálogo

- **Qué:**
  - `GET /api/conversations`: mismos filtros que T3 más filtro por día o semana del punto pulsado, paginación de 25 y orden por fecha, duración o sentimiento; devuelve el summary completo;
  - `GET /api/conversations/{id}`: turnos y análisis completos, `404` si no existe;
  - `GET /api/catalog`: canales, colas, agentes, main topics y checks.
- **Hecho cuando:**
  - el `total` del listado con los filtros de un desglose es igual al volumen de ese desglose en T3 (test cruzado);
  - la paginación y el orden son correctos;
  - `404` en un id inexistente;
  - el listado responde en menos de 500 ms.

### T5 — Front base: login, layout y navegación

- **Qué:** Vite + React + TS + Tailwind en `frontend/`, con Vitest, Testing Library y ESLint; cliente API con `VITE_API_URL` y token; TanStack Query, React Router, pantalla de login, rutas protegidas, layout con barra lateral de las 7 secciones filtrada por permisos y páginas «Próximamente».
- **Hecho cuando:** hay tests de componente para:
  - login correcto que redirige;
  - error visible con `401`;
  - ruta protegida sin sesión que va a login;
  - menú del rol `viewer` sin Configuración ni Usuarios y roles;
  - sección no implementada que muestra «Próximamente».

  Además, `npm run build` y `npm run lint` terminan en verde, y con el backend levantado el login funciona en el navegador.

### T6 — Dashboards y filtros globales

- **Qué:** los tres dashboards predefinidos con tarjetas de KPI (valor, anterior y variación), serie temporal día o semana, desgloses, distribución por main topic y tabla de KPIs por main topic en Visión general. Barra de filtros globales sincronizada con la URL.
- **Hecho cuando:** hay tests para:
  - cada dashboard renderiza sus widgets con datos de la API mockeada;
  - cambiar un filtro actualiza la URL y relanza las consultas;
  - montar la página con una URL con filtros restaura el estado;
  - el selector día o semana cambia la granularidad pedida.

  Además, se comprueba manualmente en el navegador contra el backend real.

### T7 — Drill-down y listado de conversaciones

- **Qué:** clic en tarjeta, punto, barra o segmento → navegación a `/conversaciones` con filtros heredados más el del elemento; listado con chips eliminables, paginación, orden y columnas de la spec (summary truncado con tooltip).
- **Hecho cuando:** hay tests para:
  - el clic en la barra de un main topic navega con `main_topic` y los filtros del dashboard;
  - los chips reflejan y eliminan filtros;
  - la paginación y el orden llaman a la API con los parámetros correctos.

  Además, una comprobación manual confirma que el total del listado coincide con el valor pulsado (la equivalencia de datos ya la garantiza el test cruzado de T4).

### T8 — Detalle de conversación tipo chat

- **Qué:**
  - cabecera con main topic destacado y summary completo;
  - chat tipo WhatsApp: cliente a la izquierda, agente a la derecha, bot con otro color, sistema centrado, hora relativa, icono de voz o chat, indicador de sentimiento y palabras clave resaltadas;
  - panel lateral de análisis con gráfico de evolución del sentimiento, que desplaza el chat al turno al hacer clic;
  - volver al listado conservando filtros, página y orden.
- **Hecho cuando:** hay tests para:
  - alineación y estilo por `speaker`;
  - resaltado de palabras clave;
  - cabecera con topic y summary;
  - el clic en un punto del gráfico llama a `scrollIntoView` del turno correcto;
  - el botón volver restaura la URL del listado.

  Además, se hace una revisión visual en el navegador.

### T9 — Conocimiento, documentación y verificación final

- **Qué:**
  - README en la raíz y README de backend y front con arranque, tests y usuarios demo;
  - actualizar el propósito (a `active`);
  - crear `vault/arquitectura/arquitectura-de-la-plataforma.md`;
  - ampliar el glosario (AHT, FCR, CSAT, summary, main topic, drill-down, riesgo de abandono);
  - añadir los comandos al ciclo de entrega;
  - actualizar `AGENTS.md` con los comandos reales de test.
- **Hecho cuando:**
  - `pytest`, `npm test`, `npm run build` y `npm run lint` están en verde;
  - `python scripts/audit_vault.py` devuelve `0`;
  - todas las entradas nuevas están enlazadas desde su `Index.md` y tienen `## Fuentes`.

## Riesgos del plan

- **Python 3.14:** si alguna dependencia no tiene wheel para 3.14, se fija la versión compatible más reciente o se crea el venv con `uv` y Python 3.12. Se decide en T1 con evidencia.
- **Realismo de los datos:** la calidad de las plantillas de T1 condiciona todo lo demás. Se dedica T1 entera al generador y sus tests, sin mezclarla con la API.
- **Sin Git:** sin repositorio no hay commits atómicos por tarea. Hay que ejecutar `git init` antes de empezar T1.

## Progreso

| Id | Estado | Evidencia |
|---|---|---|
| T1 | Hecha | `backend/.venv/bin/pytest`: 12 tests en verde (rojo previo: 7 fallos por falta de datos, health y catálogo); auditoría del vault `0`. |
| T2 | Hecha | `pytest`: 28 tests en verde (rojo previo: 15 fallos con stub de auth). Prueba de mutación: una ruta sin auth y otra solo con login rompen los tests de recorrido OpenAPI. Auditoría del vault `0`. |
| T3 | Hecha | `pytest`: 50 tests en verde (rojo previo: 22 fallos por 404). KPIs, periodo anterior, series y desgloses comparados con un cálculo independiente en 4 combinaciones de filtros; < 500 ms. Mutaciones (ventana FCR de 8 días y umbral negativo `<=`) detectadas. Decisión: `delta` absoluto en todos los KPIs y `delta_pct` nulo para el índice de sentimiento, que cruza el cero. |
| T4 | Hecha | `pytest`: 78 tests en verde (rojo previo: 27 fallos). Tests cruzados: el total del listado es igual al volumen del desglose (main topic, cola, agente y canal), de cada punto semanal y de cada KPI de tarjeta (escalado, resolución, riesgo alto, negativas, incumplimiento y recontacto). Paginación completa sin duplicados, orden, 404, 422 y < 500 ms. `require_permission` admite permisos alternativos para el catálogo. |
| T5 | Hecha | `npm test`: 11 tests de componente en verde (rojo previo: 11 fallos con stubs); `npm run build` y `npm run lint` (oxlint, el linter de la plantilla de Vite 8, en lugar de ESLint) sin avisos. Backend: CORS configurable (`CORS_ORIGINS`), 80 tests. Recorrido en Chrome headless contra la API real: redirección al login, menú por rol, «Sin acceso», error de credenciales, sesión persistente al recargar. |

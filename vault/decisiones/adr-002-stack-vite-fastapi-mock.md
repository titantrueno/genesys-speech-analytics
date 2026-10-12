---
title: "ADR-002 — Stack Vite + FastAPI con datos mock deterministas"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, stack, frontend, backend, mock]
created: 2026-09-27
updated: 2026-10-12
---

# ADR-002 — Stack Vite + FastAPI con datos mock deterministas

## Contexto

La plataforma de speech & text analytics para la atención al cliente del banco necesita un front React + TypeScript + Tailwind y un backend Python que exponga una API. En esta fase el backend solo debe servir datos mock que simulen el funcionamiento real, a partir de transcripciones de llamadas y chats (sin audio).

## Decisión

- **Front:** SPA con Vite + React + TypeScript + Tailwind CSS, React Router, TanStack Query y Recharts, en `frontend/`.
- **Back:** FastAPI + Pydantic en `backend/`, con un venv propio (`backend/.venv`), porque el Python 3.14 de Homebrew bloquea las instalaciones globales (PEP 668).
- **Datos:** generados en memoria al arrancar mediante un generador determinista (semilla y fecha de referencia): 1.000 conversaciones de los 90 días anteriores. No hay base de datos.

## Alternativas

- **Next.js:** descartado. La web no necesita SSR y el backend Python ya es la capa de servidor, así que Next.js añadiría una segunda capa de servidor.
- **Base de datos (SQLite o Postgres):** pospuesta. Los datos mock se regeneran igual en cada arranque y no hay escrituras que persistir en FE001.
- **Fixtures JSON estáticas:** descartadas. El generador permite volúmenes y fechas relativas al día actual, y sus propiedades se verifican con tests.

## Consecuencias

- Los dashboards siempre tienen datos de los últimos 90 días.
- Los tests pueden fijar la semilla y la fecha para obtener resultados reproducibles.
- Las escrituras de fases posteriores (configuración, usuarios, flujos) se pierden al reiniciar mientras no se decida persistencia.
- Sustituir los mocks por datos reales exigirá una capa de repositorio que ofrezca el mismo contrato de modelos.

## Ampliaciones

- **FE011 (2026-10-12):** la alternativa «Base de datos (pospuesta)» se resuelve con **PostgreSQL** para las conversaciones reales de Genesys, que descarga y guarda un servicio de ingesta aparte ([ADR-008](adr-008-postgresql-y-servicio-de-ingesta.md)). El backend añade `psycopg[binary]` (3.3, LGPL-3.0). El dataset mock, la configuración, los usuarios y los flujos de insights siguen en memoria.
- **FE010 (2026-10-03):** el front añade `swagger-ui-react` (Apache-2.0) para la pestaña «API» de Configuración. Va en un chunk diferido (unos 1,3 MB, 363 kB gzip, más 184 kB de CSS) que solo se descarga al abrir la pestaña; la carga inicial no cambia. Consecuencias aceptadas:
  - `npm ci` avisa de que dos dependencias transitivas (`react-debounce-input` y `react-inspector`) declaran React ≤18, aunque funciona con React 19 sin flags;
  - la sección «Schemas» de Swagger UI rompe el orden de hooks en React 19, así que se oculta (`defaultModelsExpandDepth: -1`);
  - Vite avisa del tamaño del chunk.
  - entre sus dependencias está `@scarf/scarf`, cuyo `postinstall` envía telemetría de instalación. Hoy `allowScripts` de npm lo bloquea; no hay que aprobarlo, porque Swagger UI no lo necesita;
  - la versión queda fijada (`5.33.1`, sin `^`): el filtro depende de que Swagger UI recargue la prop `spec`, algo que su README no garantiza ([lección 32](../aprendizaje/lecciones-construccion-plataforma.md)).

  Se descartaron un visor propio y un iframe a `/docs` ([spec FE010](../../features/FE010-especificacion-openapi-en-configuracion/spec.md)).
- **FE004 (2026-09-28):** el front añade `@xyflow/react` (React Flow, licencia MIT) para el lienzo del diseñador de flujos. Se carga en diferido con las rutas de flujos, así que no aumenta la carga inicial. El backend no añade dependencias: la ejecución simulada usa `BackgroundTasks` de FastAPI y `threading` ([ADR-006](adr-006-ejecucion-de-prompts-simulada.md)).

## Fuentes

- [Spec FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/spec.md)
- [Plan FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/plan.md)
- [Generador de datos](../../backend/app/data/generator.py)
- [Modelos](../../backend/app/models.py)
- [Spec FE004](../../features/FE004-disenador-de-flujos-de-insights/spec.md)
- [React Flow · licencia MIT](https://github.com/xyflow/xyflow/blob/main/LICENSE)
- [Swagger UI · licencia Apache-2.0](https://github.com/swagger-api/swagger-ui/blob/master/LICENSE)
- [Plan FE010](../../features/FE010-especificacion-openapi-en-configuracion/plan.md)

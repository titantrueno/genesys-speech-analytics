---
title: "ADR-002 — Stack Vite + FastAPI con datos mock deterministas"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, stack, frontend, backend, mock]
created: 2026-09-27
updated: 2026-09-27
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

## Fuentes

- [Spec FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/spec.md)
- [Plan FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/plan.md)
- [Generador de datos](../../backend/app/data/generator.py)
- [Modelos](../../backend/app/models.py)

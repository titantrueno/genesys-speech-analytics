---
title: "Arquitectura de la plataforma"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [arquitectura, frontend, backend, api, mock]
created: 2026-09-27
updated: 2026-09-27
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
| Front | `frontend/src/` | Sesión, navegación por permisos, dashboards, listado y detalle. |

### Flujo de datos

1. El front autentica con `POST /api/auth/login` y envía `Authorization: Bearer` en cada petición. En desarrollo, el proxy de Vite reenvía `/api` al puerto 8000.
2. Los filtros de los dashboards viven en la URL (`from`, `to`, `channel`, `queue`, `agent`, `main_topic`) y se pasan tal cual a métricas y listado.
3. **Contrato de drill-down:** cada elemento de un dashboard navega a `/conversaciones` con los filtros del dashboard más un filtro que selecciona el **numerador** de su KPI (`frontend/src/dashboards/drilldown.ts`). Los tests del backend garantizan que el total del listado coincide con el valor mostrado.
4. El detalle carga `GET /api/conversations/{id}` y el catálogo para las etiquetas de los checks.

### Rendimiento

- Con el dataset completo, cada endpoint responde en menos de 500 ms (hay tests con ese umbral).
- En el front, el dashboard se carga en diferido: el bundle principal ocupa unos 397 kB y el chunk de dashboards, con Recharts, unos 369 kB.

## Límites y excepciones

- Sin persistencia: todo cambio de estado se pierde al reiniciar la API.
- **FCR:** para conversaciones de los últimos 7 días del dataset aún no ha pasado la ventana de recontacto, así que su FCR es optimista. Es un **hecho** del cálculo que hay que tener en cuenta al comparar periodos recientes.
- El análisis (summary, main topic, sentimiento, CSAT…) sale de reglas del generador, no de un modelo.
- Las conversaciones de voz muestran DNI e IBAN ficticios sin enmascarar hasta FE005.

## Fuentes

- [Spec FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/spec.md)
- [Plan FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/plan.md)
- [ADR-002 — Stack](../decisiones/adr-002-stack-vite-fastapi-mock.md)
- [README del backend](../../backend/README.md)
- [README del frontend](../../frontend/README.md)

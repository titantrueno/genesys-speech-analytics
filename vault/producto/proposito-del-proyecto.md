---
title: "Propósito del proyecto"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [producto, speech-analytics, banca]
created: 2026-09-27
updated: 2026-10-12
---

# Propósito del proyecto

## Resumen

**Hecho:** `genesys-speech-analytics` es una plataforma web de speech & text analytics para la **atención al cliente de un banco**. Analiza conversaciones a partir de **transcripciones de llamadas y chats**; nunca trabaja con grabaciones de audio.

## Usuarios y necesidad

Supervisores, analistas de calidad y responsables de experiencia de cliente necesitan:

- ver KPIs agregados de la atención (volumen, resolución, escalado, FCR, satisfacción y esfuerzo predichos, cumplimiento, riesgo de abandono);
- bajar de un KPI al listado de conversaciones que lo explican y a cada conversación, leída como un chat, con su análisis (summary, main topic, sentimiento, cumplimiento);
- en fases posteriores: consultas asistidas, búsqueda semántica, flujos de generación de insights con prompts, configuración de la plataforma y gestión de usuarios y roles.

## Alcance actual

- **Implementado:** FE001 (dashboards, drill-down, listado y detalle), FE007 (fila clicable) y FE008 (identificadores `PREFIJO-UUID`).
- **Especificado:** FE002 a FE006.
- **Decisión:** en esta fase el backend solo sirve **datos mock** generados de forma determinista ([ADR-002](../decisiones/adr-002-stack-vite-fastapi-mock.md)). El catálogo de motivos de contacto está en el [catálogo de main topics](catalogo-de-main-topics.md).
- **Hipótesis:** el catálogo de main topics y la lista de KPIs cubren las necesidades de un contact center bancario. Validarlos con datos reales queda para la fase con LLM: FE012 muestra las conversaciones reales con el análisis de la plataforma pendiente.

## Fuentes

- [README del proyecto](../../README.md)
- [Spec FE001](../../features/FE001-base-dashboards-y-detalle-conversaciones/spec.md)
- [Specs de features](../../features/README.md)

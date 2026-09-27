---
title: "ADR-001 — Markdown versionado y compatible con Obsidian"
type: adr
status: active
owners: [harness-team]
tags: [adr, vault, obsidian]
created: 2026-09-07
updated: 2026-09-07
---

# ADR-001 — Markdown versionado y compatible con Obsidian

## Contexto

El conocimiento debe servir tanto a personas como a agentes, permanecer junto al código y poder consultarse sin depender de un servicio externo.

## Decisión

El directorio `vault/` usa Markdown UTF-8 versionado como fuente de verdad. Los enlaces internos son Markdown estándar con rutas relativas y extensión `.md`. Obsidian es un cliente opcional y su configuración personal no se versiona.

## Alternativas

- Wikilinks de Obsidian: se descartaron como convención principal porque reducen la portabilidad fuera de Obsidian.
- Notion o Confluence: se pospusieron porque añaden sincronización, permisos y dependencia externa.
- RAG o base vectorial: queda fuera de la primera versión por complejidad prematura.

## Consecuencias

- El contenido puede revisarse mediante diff y consumirse con herramientas estándar.
- Los autores deben mantener enlaces e índices explícitos.
- La búsqueda inicial será textual; capacidades semánticas podrán evaluarse con evidencia futura.

## Fuentes

- [Reglas del vault](../Governance.md)
- [README del vault](../README.md)

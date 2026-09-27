---
title: "Arquitectura del harness"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [arquitectura, skills, devin]
created: 2026-09-27
updated: 2026-09-27
---

# Arquitectura del harness

## Componentes

- `AGENTS.md`: instrucciones del proyecto para los agentes.
- `.devin/skills/`: los skills `spec`, `plan`, `build`, `test`, `review`, `ship` y `vault`.
- `vault/`: conocimiento versionado del proyecto.
- `scripts/audit_vault.py`: valida metadatos, enlaces, entradas huérfanas, wikilinks y posibles secretos del vault.
- `features/`: una carpeta `FEXXX-descripcion-breve/` por feature con sus artefactos del ciclo.

## Flujo

Los skills encadenan `Define → Plan → Build → Verify → Review → Ship`. Cada feature deja `spec.md`, `plan.md`, `VERIFY.md`, `REVIEW.md` y `SHIP.md` en su carpeta de `features/`, mientras `/vault` consulta y conserva el conocimiento permanente.

## Límites

Todavía no existe código de aplicación, infraestructura ni CI. La arquitectura del producto se documentará en esta área cuando se defina.

## Fuentes

- [Instrucciones del proyecto](../../AGENTS.md)
- [Skill spec](../../.devin/skills/spec/SKILL.md)
- [Skill vault](../../.devin/skills/vault/SKILL.md)
- [Script de auditoría](../../scripts/audit_vault.py)

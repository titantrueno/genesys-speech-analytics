---
title: "Lecciones iniciales del harness"
type: lesson
status: active
owners: [equipo-del-proyecto]
tags: [aprendizaje, skills, yaml]
created: 2026-09-27
updated: 2026-09-27
---

# Lecciones iniciales del harness

## Situación

Heredadas del montaje del harness: los skills se guardaron primero fuera de la carpeta de skills del agente y este no los descubrió. Primero se usó `.devin/skills/<nombre>/SKILL.md` (Devin) y ahora `.claude/skills/<nombre>/SKILL.md`, la carpeta que Claude Code descubre.

## Resultado observado

Un skill fuera de esa ruta no aparece como comando. Una descripción YAML con `:` sin comillas también impide descubrirlo.

## Causa

La ubicación y el frontmatter forman parte del contrato ejecutable del agente (hoy, Claude Code).

## Aprendizaje

- Comprueba el descubrimiento real de cada skill, no solo que el archivo exista.
- El agente localiza la configuración local desde la raíz del repositorio (donde está `.git`); sin ese marcador, `.claude/skills/` puede no detectarse.
- La auditoría de enlaces debe ignorar ejemplos dentro de código inline o bloques cercados.

## Acción preventiva

Mantén las descripciones YAML entre comillas cuando contengan puntuación, inicializa el repositorio Git antes de trabajar y abre una sesión nueva tras añadir skills.

## Fuentes

- [Instrucciones del proyecto](../../AGENTS.md)
- [Skill spec](../../.claude/skills/spec/SKILL.md)

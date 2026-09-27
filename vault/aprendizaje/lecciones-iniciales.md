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

Heredadas del montaje del harness: los skills se guardaron primero fuera de `.devin/skills/<nombre>/SKILL.md` y Devin no los descubrió.

## Resultado observado

Un skill fuera de esa ruta no aparece como comando. Una descripción YAML con `:` sin comillas también impide descubrirlo.

## Causa

La ubicación y el frontmatter forman parte del contrato ejecutable de Devin.

## Aprendizaje

- Comprueba el descubrimiento real de cada skill, no solo que el archivo exista.
- Devin localiza la configuración local subiendo directorios hasta encontrar `.git` o `.jj`; sin ese marcador, `.devin/skills/` puede no detectarse.
- La auditoría de enlaces debe ignorar ejemplos dentro de código inline o bloques cercados.

## Acción preventiva

Mantén las descripciones YAML entre comillas cuando contengan puntuación, inicializa el repositorio Git antes de trabajar y abre una sesión nueva de Devin tras añadir skills.

## Fuentes

- [Instrucciones del proyecto](../../AGENTS.md)
- [Skill spec](../../.devin/skills/spec/SKILL.md)

---
title: "Ciclo de entrega del harness"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [ingenieria, tdd, entrega]
created: 2026-09-27
updated: 2026-09-27
---

# Ciclo de entrega del harness

## Fases

1. `/spec` crea `features/FEXXX-descripcion-breve/` y convierte una idea en criterios verificables.
2. `/plan` ordena tareas atómicas por dependencias.
3. `/build` ejecuta una tarea con test rojo y código mínimo verde.
4. `/test` exige evidencia y prueba casos límite.
5. `/review` evalúa corrección, spec, simplicidad, seguridad, rendimiento y conocimiento.
6. `/ship` exige CI, observabilidad y rollback.

## Documentación de features

- Cada feature tiene su carpeta `features/FEXXX-descripcion-breve/` con `spec.md`, `plan.md`, `VERIFY.md`, `REVIEW.md` y `SHIP.md`.
- `XXX` es un número de tres dígitos que se incrementa respecto al mayor existente, empezando en `FE001`.
- La descripción resume la feature en 4 o 5 palabras en `kebab-case`, sin tildes.

## Integración del conocimiento

- `/spec` consulta el vault y declara el conocimiento afectado.
- `/plan` crea tareas verificables para actualizarlo.
- `/build` usa `/vault capture` cuando surge una decisión o aprendizaje no previsto.
- `/test` ejecuta la auditoría y registra su código de salida.
- `/review` clasifica conocimiento faltante o desactualizado.
- `/ship` actualiza entradas permanentes y registra la entrega en `vault/entregas/`.

## Regla operativa

No se avanza cuando falta evidencia para superar el gate de la fase. Una tarea de build debe demostrar la transición rojo → verde y mantenerse separada de las siguientes.

## Fuentes

- [Instrucciones del proyecto](../../AGENTS.md)
- [Skill spec](../../.devin/skills/spec/SKILL.md)
- [Skill build](../../.devin/skills/build/SKILL.md)
- [Skill test](../../.devin/skills/test/SKILL.md)
- [Skill vault](../../.devin/skills/vault/SKILL.md)

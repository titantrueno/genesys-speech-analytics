---
title: "Ciclo de entrega del harness"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [ingenieria, tdd, entrega, git, github]
created: 2026-09-27
updated: 2026-10-12
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

## Comandos del proyecto

| Qué | Comando |
|---|---|
| Arrancar la API | `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000` |
| Arrancar la web | `cd frontend && npm run dev` |
| Tests del backend | `cd backend && .venv/bin/pytest` |
| Tests del backend con otro dataset | `cd backend && DATA_SEED=7 DATA_REFERENCE_DATE=2026-11-10 .venv/bin/pytest` |
| Gate completo | `./scripts/ci.sh` (vault, backend con dos datasets, front, lint, build y auditorías) |
| Tests del front | `cd frontend && npm test` |
| Lint y build del front | `cd frontend && npm run lint && npm run build` |
| Auditoría del vault | `python3 scripts/audit_vault.py` |

La primera vez hay que crear el entorno del backend (`python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`) e instalar el front (`cd frontend && npm install`).

## Commits y publicación en GitHub

**Decisión de la persona propietaria del proyecto (2026-10-12):** los commits, las etiquetas y los pull requests de este repositorio **no mencionan la coautoría del código**.

- No llevan la línea `Co-Authored-By: …` ni ninguna otra atribución a un asistente (por ejemplo, «Generated with Claude Code» en la descripción de un PR).
- Esta regla prevalece sobre la atribución por defecto de las herramientas de agentes.
- **Antes de cada `git push`**, `git log origin/main..HEAD --format=%B | grep -c "^Co-Authored-By"` debe devolver `0`.
- Si algún commit local aún sin publicar lleva la línea, se quita antes de subir. Para ello se reescribe solo el rango `origin/main..HEAD` y se deja una rama de respaldo.
- La historia ya publicada no se reescribe: los commits anteriores a FE011 que están en `origin` conservan la línea, porque cambiarlos exigiría un `push --force` sobre `main`.
- **CI en GitHub Actions** (`.github/workflows/ci.yml`): el runner está fijado a `ubuntu-24.04` y las acciones van en v7 (Node.js 24). Pasar a `ubuntu-26.04` es un cambio deliberado, que se valida con el propio workflow ([actions/runner-images#14748](https://github.com/actions/runner-images/issues/14748)).

## Regla operativa

No se avanza cuando falta evidencia para superar el gate de la fase. Una tarea de build debe demostrar la transición rojo → verde y mantenerse separada de las siguientes.

## Fuentes

- [Spec FE009](../../features/FE009-tests-independientes-del-dataset-mock/spec.md)
- [Instrucciones del proyecto](../../AGENTS.md)
- [README del proyecto](../../README.md)
- [Skill spec](../../.devin/skills/spec/SKILL.md)
- [Skill build](../../.devin/skills/build/SKILL.md)
- [Skill test](../../.devin/skills/test/SKILL.md)
- [Skill vault](../../.devin/skills/vault/SKILL.md)

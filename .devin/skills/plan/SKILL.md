---
name: plan
description: "Harness starter — Plan. Descompón la spec en tareas atómicas, verificables y ordenadas por dependencias."
---

# /plan — Plan

> Fase 2 del ciclo `Define → Plan → Build → Verify → Review → Ship`.
> Aquí muere el *one-shotting*: no se implementa de un tirón, se descompone.

## Cuándo se invoca

- `/plan` después de que `spec.md` esté aprobada. Si no hay spec, lanza `/spec` primero.

## Pasos

1. **Lee la `spec.md`.** Parte de los criterios de aceptación y de su sección **Conocimiento afectado**, no de tu intuición.
2. **Contrasta el vault.** Comprueba en `vault/Home.md` que las entradas citadas existen y detecta decisiones, runbooks o convenciones adicionales que el cambio pueda invalidar.
3. **Descompón en tareas atómicas.** Cada tarea:
   - es **pequeña** (idealmente un slice vertical completable en una sesión),
   - tiene su **criterio de aceptación** propio (cómo sabrás que está hecha),
   - es **verificable por separado** (si no lo es, pártela más).
4. **Planifica el conocimiento.** Por cada entrada afectada, incluye una tarea verificable para actualizar la canónica o crearla con `/vault capture`; exige fuente, índice actualizado y auditoría verde.
5. **Ordena por dependencias.** Numera las tareas en el orden en que deben ejecutarse.
6. **Escribe `plan.md`** con la lista ordenada (id, título, criterio de "done", dependencias y conocimiento afectado).

## Gate (default-FAIL)

- ⏸ No avances a `/build` si alguna tarea no es verificable de forma independiente. Repártela.
- Una tarea que toca "todo a la vez" es señal de que falta descomponer.

## Salida

- `plan.md` con 3–9 tareas atómicas ordenadas, en la misma carpeta `features/FEXXX-descripcion-breve/` que la spec.
- Siguiente paso: **`/build`** (una tarea cada vez).

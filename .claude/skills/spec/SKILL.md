---
name: spec
description: "Harness starter — Define. Convierte una idea difusa en una spec verificable ANTES de tocar código."
argument-hint: '"quiero añadir X"'
---

# /spec — Define

> Fase 1 del ciclo `Define → Plan → Build → Verify → Review → Ship`.
> Regla de oro: **sin spec cerrada, no hay implementación.** La spec es la *policy* del agente.

## Cuándo se invoca

- `/spec "quiero añadir X"` — o `/spec` y el agente te entrevista.
- Automático: ante una petición que implica código sin spec asociada, propón lanzar `/spec` antes.

## Pasos

1. **Consulta el vault.** Empieza en `vault/Home.md`, busca conocimiento relacionado y cita las entradas que condicionen la feature. Si no hay evidencia, declara el vacío en vez de asumir.
2. **Entrevista breve.** Pregunta lo mínimo para cerrar ambigüedad: objetivo de negocio, usuarios,
   datos de entrada/salida, casos límite, restricciones. No asumas; pregunta.
3. **Crea la carpeta de la feature** en `features/FEXXX-descripcion-breve/`: `XXX` es el siguiente
   número de tres dígitos tras el mayor `FE` existente (empieza en `FE001`) y la descripción resume
   la feature en 4 o 5 palabras en `kebab-case`, sin tildes. Ejemplo: `features/FE001-transcripcion-de-llamadas-genesys/`.
4. **Escribe `spec.md`** en esa carpeta con estas secciones obligatorias:
   - **Objetivo** — qué problema resuelve, en una frase.
   - **Criterios de aceptación** — lista *comprobable* (cada uno debe poder convertirse en un test).
   - **Conocimiento afectado** — entradas consultadas, a actualizar o crear, con una cita a cada fuente.
   - **Alcance** — qué entra.
   - **Fuera de alcance** — qué NO se hace (tan importante como lo anterior).
   - **Riesgos / asunciones** — lo que podría ser falso y habrá que verificar.
5. **Marca lo no verificable.** Si un criterio no se puede comprobar objetivamente, reescríbelo hasta
   que sí, o muévelo a fuera-de-alcance.

## Gate (default-FAIL)

- ⏸ No avances a `/plan` hasta que **cada criterio de aceptación sea comprobable** y la spec esté
  aprobada por el humano. Ante la duda, **falla**: pide aclaración, no implementes.

## Salida

- `features/FEXXX-descripcion-breve/spec.md`. Es el contrato contra el que se mide "hecho".
- Siguiente paso: **`/plan`**.

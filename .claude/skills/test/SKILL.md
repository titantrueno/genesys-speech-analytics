---
name: test
description: "Harness starter — Verify. Verificación escéptica: tests reales, fuentes oficiales y rutina de duda (default-FAIL)."
---

# /test — Verify

> Fase 4 del ciclo `Define → Plan → Build → Verify → Review → Ship`.
> Ataca el fallo de "declarar hecho". Verificar = **dudar de forma disciplinada**.

## Cuándo se invoca

- `/test` cuando las tareas de `/build` están implementadas, antes de la revisión.

## Pasos

1. **Tests que prueban de verdad.** Revisa cada test: ¿fallaría si el comportamiento se rompe? Añade
   los casos límite que falten (vacío, límites, errores, concurrencia si aplica).
2. **Audita el vault.** Ejecuta `python scripts/audit_vault.py` y registra en `VERIFY.md` el comando, el código de salida y los hallazgos. Si el código es distinto de cero, no avances: corrige enlaces, metadatos, entradas huérfanas o conocimiento inseguro.
3. **Fundamenta en documentación oficial.** Para cada decisión de framework/librería/API, cita la
   página oficial. Si el agente "cree recordar" una opción y no hay fuente, trátalo como alucinación.
4. **Rutina de duda** sobre las decisiones de riesgo: afirmar → extraer la asunción → dudar →
   reconciliar con la evidencia.
5. **Depura con runtime real** si algo falla: reproducir → localizar → reducir → arreglar → blindar
   (añade un test de regresión).

## Gate (default-FAIL)

- ⏸ Si no hay **evidencia** de que algo pasa, se considera **que falla**. Una salida no verificada no
  es una salida terminada.
- Toda la batería de tests debe estar en verde y cubrir los criterios de aceptación de la `spec.md`.

## Salida

- `features/FEXXX-descripcion-breve/VERIFY.md` con: grounding (fuentes citadas), log de duda (CLAIM→…→STOP), bug/causa-raíz/test de
  regresión y la evidencia (suite en verde).
- Siguiente paso: **`/review`**.

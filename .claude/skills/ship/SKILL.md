---
name: ship
description: "Harness starter — Ship. Envía con confianza: commits atómicos, CI con gates, observabilidad y rollout reversible."
---

# /ship — Ship

> Fase 6 del ciclo `Define → Plan → Build → Verify → Review → Ship`.
> La paradoja: **más rápido es más seguro**, porque los lotes pequeños y reversibles fallan barato.

## Cuándo se invoca

- `/ship` con la revisión (`/review`) cerrada, para llevar el cambio a producción.

## Pasos

1. **Comprueba trazabilidad.** Verifica que existen y están cerrados `spec.md`, `plan.md`, `VERIFY.md` y `REVIEW.md` en `features/FEXXX-descripcion-breve/`.
2. **Registra la entrega.** Crea o actualiza una entrada en `vault/entregas/` que enlace esos cuatro artefactos, resuma el cambio y documente rollout, observabilidad y rollback.
3. **Actualiza conocimiento permanente.** Revisa la sección Conocimiento afectado de la spec, actualiza cada entrada canónica y marca como `superseded` cualquier contenido sustituido.
4. **Audita antes de enviar.** Ejecuta `python scripts/audit_vault.py`; un código distinto de cero bloquea la entrega.
5. **Integración trunk-based.** Commits atómicos sobre la rama principal (o PR pequeño y de vida corta).
6. **Pipeline con gates.** Asegura que CI ejecuta lint + tests + checks de seguridad y **bloquea** si
   algo falla. Nada llega a producción saltándose los gates.
7. **Observabilidad desde el principio.** Instrumenta logging estructurado, una métrica de éxito/error
   y trazas para la feature. Si no puedes verla en producción, no la has terminado.
8. **Rollout reversible.** Despliega escalonado (p. ej. feature flag a un % de usuarios) con un **plan
   de rollback** claro (apagar el flag, revertir el deploy).

## Gate (default-FAIL)

- ⏸ No despliegues sin: pipeline en verde, una señal observable de salud y una vía de rollback.
- Ante la duda sobre el blast radius, reduce el alcance del rollout.

## Salida

- `features/FEXXX-descripcion-breve/SHIP.md` con: resumen del PR, pipeline CI, observabilidad y plan de rollout/rollback.
- Cambio en producción, observable y reversible.
- Ciclo completo: la feature pasó por `Define → Plan → Build → Verify → Review → Ship`.

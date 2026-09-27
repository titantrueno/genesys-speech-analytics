---
name: review
description: "Harness starter — Review. Quality gate en seis ejes, incluido conocimiento, antes de mergear."
---

# /review — Review

> Fase 5 del ciclo `Define → Plan → Build → Verify → Review → Ship`.
> La pregunta que ordena todo: *¿aprobaría este PR un staff engineer?*

## Cuándo se invoca

- `/review` con la verificación (`/test`) en verde, antes del merge.

## Pasos

1. **Acota el cambio.** Si el diff supera ~100 líneas revisables, propón partirlo. Lotes pequeños se
   revisan mejor.
2. **Comprueba la evidencia.** Confirma que `VERIFY.md` contiene la auditoría del vault en verde; si no existe o está desactualizada, crea un hallazgo major.
3. **Revisa en seis ejes** y marca cada hallazgo con severidad (**critical / major / minor / nit**):
   - **Corrección** — ¿la lógica es correcta? ¿casos límite? ¿los tests prueban de verdad?
   - **Adherencia a la spec** — ¿cumple los criterios de aceptación y respeta el fuera-de-alcance?
   - **Simplicidad** — ¿se puede simplificar sin cambiar el comportamiento?
   - **Seguridad** — repasa OWASP Top 10 (inyección, authz, secretos, validación de input…).
   - **Rendimiento** — mide antes de optimizar; señala costes evidentes.
   - **Conocimiento** — ¿las entradas afectadas están completas, trazables y vigentes? Marca como major el conocimiento faltante o desactualizado que pueda inducir decisiones incorrectas.
4. **Decide cada hallazgo:** resolver ahora o justificar conscientemente por qué se acepta.

## Gate (default-FAIL)

- ⏸ No mergees con hallazgos **critical** o **major** sin resolver (especialmente de seguridad).
- Si no lo aprobaría un staff engineer, no está listo.

## Salida

- `features/FEXXX-descripcion-breve/REVIEW.md` con los hallazgos por eje (evidencia + severidad), resueltos o justificados.
- Siguiente paso: **`/ship`**.

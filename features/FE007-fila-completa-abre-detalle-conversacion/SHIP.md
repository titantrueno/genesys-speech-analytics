# FE007 — Ship

> Fase `/ship`. Fecha: 2026-09-27. Entrega conjunta: [Plataforma v0.1.0](../../vault/entregas/2026-09-27-plataforma-v0-1-0.md). Pipeline, observabilidad y rollback en [FE001/SHIP](../FE001-base-dashboards-y-detalle-conversaciones/SHIP.md).

## Trazabilidad

[spec](spec.md) aprobada · [plan](plan.md) T1 a T3 hechas · [VERIFY](VERIFY.md) verde · [REVIEW](REVIEW.md) aprobado.

## Resumen del cambio

Commits `09f6928`, `6c6e9dc` y `2a36ead`: toda la fila del listado abre el detalle, con pestaña nueva mediante Ctrl/Cmd+clic o clic central, protección de la selección de texto y un único punto de foco. El patrón queda documentado en el vault.

## Rollback

`git revert 09f6928 6c6e9dc 2a36ead`: el listado vuelve a abrir el detalle solo desde el enlace de la fecha.

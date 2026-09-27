# FE008 — Ship

> Fase `/ship`. Fecha: 2026-09-27. Entrega conjunta: [Plataforma v0.1.0](../../vault/entregas/2026-09-27-plataforma-v0-1-0.md). Pipeline, observabilidad y rollback en [FE001/SHIP](../FE001-base-dashboards-y-detalle-conversaciones/SHIP.md).

## Trazabilidad

[spec](spec.md) aprobada · [plan](plan.md) T1 a T4 hechas · [VERIFY](VERIFY.md) verde · [REVIEW](REVIEW.md) aprobado.

## Resumen del cambio

Commits `ff0b930`, `850788d`, `08cbf83` y `0ecf73e`: identificadores `PREFIJO-UUID` para conversaciones, clientes, usuarios, agentes y colas; registro de prefijos en el vault sincronizado por test; regla en `AGENTS.md`.

## Impacto

- **Contrato de API:** los filtros `queue` y `agent` pasan de nombres a identificadores y los nombres se rechazan con 422. No afecta a consumidores externos porque no hay ninguno.
- **Enlaces antiguos** (`CNV-…`, `queue=<nombre>`): no se soportan. La UI muestra un aviso en lugar de fallar en silencio.

## Rollback

Revertir los cuatro commits en orden inverso. El contenido del dataset no cambia en ninguno de los dos sentidos, porque así lo garantiza el test de huella.

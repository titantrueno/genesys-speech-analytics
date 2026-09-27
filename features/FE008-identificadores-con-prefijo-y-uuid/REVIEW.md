# FE008 — Revisión

> Fase `/review`. Fecha: 2026-09-27. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Revisión conjunta en [FE001/REVIEW](../FE001-base-dashboards-y-detalle-conversaciones/REVIEW.md).

## Resultado

**Aprobado.** Sin hallazgos critical ni major pendientes.

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Conocimiento | minor | La spec y el vault citaban RFC 4122, que ya está obsoleta | **Resuelto en `/test`:** referencias actualizadas a RFC 9562 |
| R2 | Corrección | minor | Los enlaces antiguos con nombres de cola o agente reciben 422 | **Aceptado** (enlaces antiguos fuera de alcance); tras la corrección de FE001, la UI muestra un aviso en lugar de quedarse cargando |
| R3 | Corrección | minor | Los UUID v5 de agentes y colas dependen del nombre: renombrar cambia el identificador | **Aceptado y documentado** en el [registro](../../vault/ingenieria/registro-de-identificadores.md); FE005 generará identificadores persistentes |
| R4 | Seguridad | — | Los identificadores v4 no son secuenciales: no exponen volumen ni orden | Correcto |
| R5 | Simplicidad | — | Un único módulo `app/ids.py`; test que impide construir identificadores a mano y test de sincronía con el vault | Correcto |
| R6 | Rendimiento | — | El detalle usa un índice por identificador en lugar de una búsqueda lineal | Mejora |
| R7 | Conocimiento | — | Registro, ADR-004, glosario y regla en `AGENTS.md` al día | Correcto |

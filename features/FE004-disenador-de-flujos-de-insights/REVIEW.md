# FE004 — Revisión

> Fase `/review`. Fecha: 2026-09-28. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Siguiente paso: `/ship`.

## Resultado

**Aprobado.** No hay hallazgos critical ni major abiertos. Durante la revisión se resolvieron dos hallazgos minor (Recharts en la vista de ejecución y el historial sin límite). Otros cuatro minor se aceptan de forma justificada y quedan documentados.

## Tamaño del cambio

El cambio supera con mucho las ~100 líneas recomendadas. Se entregó en 11 commits atómicos (spec y plan, T1–T9 y la verificación con la revisión), cada uno con su evidencia de rojo a verde y sus mutaciones en el [plan](plan.md#progreso). `VERIFY.md` incluye la auditoría del vault en verde.

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Corrección | major | Un nodo con `type` no hashable daba `500` en `PUT …/graph` y `validate` (fuzzing de la verificación) | **Resuelto en `/test`** con 6 tests de regresión; 0 `5xx` en 9.000 peticiones |
| R2 | Corrección | minor | Los tests de flujos dependían de la fecha de referencia del dataset (22 fallaban con otra) | **Resuelto en `/test`**: fechas relativas; 190/190 con 4 semillas y fechas |
| R3 | Rendimiento | minor | La vista de ejecución descargaba Recharts (347 kB) por usar `RankedBars`, que vive junto a un gráfico de Recharts | **Resuelto**: `RankedBars` pasa a `dashboards/bars.tsx` (reexportado desde `charts.tsx`); la vista de ejecución carga 1,9 kB de barras |
| R4 | Seguridad / rendimiento | minor | El historial de ejecuciones crecía sin límite en memoria (~1 MB por ejecución de 1.000 conversaciones) | **Resuelto**: se conservan las 50 más recientes por flujo (`MAX_RUNS_PER_FLOW`), nunca se descarta una en curso; test con el límite a 3 |
| R5 | Adherencia a la spec | minor | Con los roles por defecto, todo rol con `flows:view` tiene `flows:edit`, así que la solo lectura (criterio 19) solo se ve con un rol creado a mano | **Justificado**: la matriz de [ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md) no se cambia sin decisión; está probado con un rol de test y FE006 permitirá crearlo. Anotado en la spec como asunción |
| R6 | Seguridad | minor | Los flujos son del equipo: cualquier persona con `flows:edit` puede editar o borrar el flujo de otra, y el último guardado gana | **Aceptado por la spec** (concepto «flujo de insights» y fuera de alcance «edición colaborativa»). El autor se muestra en el listado |
| R7 | Seguridad | minor | `{{transcripcion}}` y `{{metadatos}}` incluyen datos personales ficticios (DNI, IBAN) | **Aceptado**: el prompt simulado no envía nada fuera del proceso. [ADR-006](../../vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md) exige enmascararlos (FE005) antes de conectar un LLM real |
| R8 | Simplicidad | minor | Las reglas de conexión existen en Python y en TypeScript | **Justificado**: el lienzo necesita respuesta inmediata; `rules.cases.json` se ejecuta en los dos lados. La completitud tiene una sola implementación (backend) |
| R9 | Corrección | nit | En T7 y T8 el código se escribió antes que los tests | **Mitigado**: rojo demostrado con 20 mutaciones (todas detectadas tras endurecer dos tests). Queda como lección 22 |
| R10 | Seguridad | — | Permisos por ruta (`flows:view` / `flows:edit`) con tests de rol de solo lectura y recorrido del OpenAPI; identificadores validados (`404` con otro prefijo); plantilla ≤ 4.000, ≤ 50 nodos, ≤ 100 conexiones, muestra ≤ 1.000; `extra="forbid"` y sin `inf`/`nan`; `render_template` sustituye con una función (sin interpretar la plantilla como regex ni código); React escapa todos los textos (sin `innerHTML`); arranque de ejecución atómico | Correcto |
| R11 | Rendimiento | — | 1.000 conversaciones con 2 prompts en 21 ms sin retardo; detalle de 0,92 MB en 4 ms; polling solo mientras la ejecución está activa; React Flow en un chunk diferido (la carga inicial sigue en ~448 kB) | Correcto |
| R12 | Conocimiento | — | ADR-006 nuevo; ADR-002, arquitectura, glosario, registro de identificadores, patrones de interfaz, runbook y lecciones 16–22 actualizados; auditoría con código 0 | Correcto |

## Revisión por ejes

- **Corrección:** ver R1, R2 y R9.
  - Propiedad de 500 grafos y fuzzing de 9.000 peticiones.
  - Progreso observado paso a paso, con un hilo real y con uvicorn.
  - Carrera de arranque probada de forma determinista.
  - Mutaciones detectadas en cada tarea.
- **Adherencia a la spec:** los 21 criterios están trazados en [VERIFY](VERIFY.md#matriz-de-trazabilidad). El fuera de alcance se respeta: sin LLM real, sin programación periódica, sin nodos de código o condicionales, sin edición colaborativa ni cancelación. Ver R5 y R6.
- **Simplicidad:** ver R8. El editor delega en funciones puras (`graph.ts`, `rules.ts`, `freePosition`) y reutiliza el constructor de FE002, `useRowNavigation`, `ChartCard` y `RankedBars` sin duplicarlos.
- **Seguridad:** ver R4, R6, R7 y R10.
- **Rendimiento:** ver R3, R4 y R11.
- **Conocimiento:** ver R12.

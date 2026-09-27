# FE008 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-09-27. Siguiente paso: `/build`, en orden.

## Contraste con el vault

| Entrada | Estado | Impacto |
|---|---|---|
| [Índice de ingeniería](../../vault/ingenieria/Index.md) | Solo contiene el ciclo de entrega | Se añade el registro de identificadores (T1). |
| [Decisiones](../../vault/decisiones/Index.md) | ADR-001 a ADR-003 | ADR-004 está libre (T1). |
| [ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md) | `active` | El `sub` del token cambia de formato (T3). |
| [Catálogo de main topics](../../vault/producto/catalogo-de-main-topics.md) | `active` | No cambia: los main topics conservan su código (prefijo `1TP` reservado). |

Usos de identificadores antiguos localizados: `backend/app/auth.py`, `backend/app/data/generator.py`, `backend/tests/test_conversations.py` y los fixtures y tests del front.

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Módulo `app/ids.py`, registro en el vault y convención | — | 1 (módulo), 8 y conocimiento |
| T2 | Identificadores en el dataset: conversaciones, clientes, agentes y colas | T1 | 1 (sin patrones antiguos), 2, 3, 5 (modelo) |
| T3 | API con identificadores: usuarios, catálogo, filtros, desgloses y detalle | T2 | 4, 5 (API), 6, 7 |
| T4 | Front con identificadores y verificación en navegador | T3 | 9, 10, 11 |

### T1 — Módulo de identificadores y registro

- **Qué:** `app/ids.py` con `PREFIXES`, `new_id(prefix, rng)` (UUID v4 a partir de un `random.Random`), `stable_id(prefix, name)` (UUID v5 con un namespace fijo del proyecto), `is_valid(value, prefix=None)` y `normalize(value)` (pasa a mayúsculas). Además, `vault/ingenieria/registro-de-identificadores.md`, ADR-004, la regla en `AGENTS.md` y el glosario.
- **Hecho cuando:**
  - hay tests para el formato, la versión (4 o 5), la variante, las mayúsculas, el determinismo con semilla, la estabilidad de v5 y el rechazo de prefijos desconocidos o valores mal formados;
  - un test compara `PREFIXES` con la tabla del registro en el vault;
  - la auditoría del vault devuelve `0`.

### T2 — Identificadores en el dataset

- **Qué:**
  - las conversaciones usan `1CO` y los clientes `1CU`, ambos con UUID v4 de un `random.Random` independiente derivado de la semilla;
  - los agentes (`1AG`) y las colas (`1QU`) tienen UUID v5 en el catálogo;
  - el modelo `Conversation` añade `agent_id` y `queue_id`.
- **Hecho cuando:**
  - los tests de T1 de FE001 se adaptan: formato, unicidad y determinismo;
  - el contenido del dataset, sin contar los identificadores, es igual al que se genera con la misma semilla en la versión anterior (se compara con un resumen del commit anterior fijado en el test: recuentos por main topic, cola y resolución);
  - un test busca `CNV-`, `CLI-` y `"u-` en `backend/app` y falla si los encuentra.

### T3 — API con identificadores

- **Qué:**
  - los usuarios demo pasan a `1US` + v5 del email;
  - `/api/catalog` devuelve colas y agentes como `{id, name}`;
  - los filtros `queue` y `agent` reciben identificadores;
  - los desgloses por cola y agente usan el identificador como `key` y el nombre como `label`;
  - el detalle busca sin distinguir mayúsculas y devuelve `404` si el identificador está mal formado o no existe.
- **Hecho cuando:**
  - los tests de auth, métricas y conversaciones se adaptan y quedan en verde, incluidos los cruces listado = desglose;
  - un test nuevo cubre el identificador en minúsculas y el mal formado;
  - ADR-003 queda actualizada.

### T4 — Front con identificadores

- **Qué:**
  - tipos del catálogo `{id, name}`;
  - `MultiSelect` de cola y agente con el identificador como valor y el nombre como etiqueta;
  - chips con nombres;
  - identificador abreviado en el listado (completo al pasar el ratón) y completo en el detalle;
  - fixtures y tests adaptados.
- **Hecho cuando:**
  - `npm test`, `npm run build` y `npm run lint` terminan en verde;
  - hay tests nuevos para el identificador abreviado y para el chip de cola con nombre;
  - en Chrome contra la API real, los drill-downs de T7 coinciden (incluido uno por cola) y no hay errores en consola.

## Riesgos del plan

- **Resultado de T3 de FE001:** debe mantenerse, porque el contenido no cambia; solo cambian los identificadores. Si se usara el mismo generador aleatorio para los identificadores, cambiarían todos los datos. Por eso se usa uno independiente.

## Progreso

| Id | Estado | Evidencia |
|---|---|---|
| T1 | Hecha | `tests/test_ids.py`: 9 tests en verde (rojo previo: 9 fallos con el módulo vacío), incluido el que compara `PREFIXES` con la tabla del vault. Registro, ADR-004, glosario y regla en `AGENTS.md`. Auditoría `0`. |

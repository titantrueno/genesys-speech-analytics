# FE008 — Identificadores con prefijo y UUID

> Estado: **pendiente de aprobación**. Fase `/spec`. Modifica el backend y el front de FE001, que todavía no se ha entregado, y fija la convención para las features siguientes.

## Objetivo

Que todo identificador de entidad de la plataforma tenga el formato `PREFIJO-UUID`: un prefijo legible de tres caracteres que indica el tipo de entidad y un UUID estándar en mayúsculas.

## Formato

```text
1CO-4B2E9A7F-3D1C-4A9B-8E5D-8F0A6C3E71AB
└┬┘ └──────────────── UUID RFC 9562 ───────────────┘
prefijo
```

- **Prefijo:** `1` seguido de dos letras mayúsculas.
- **UUID:** estándar RFC 9562 en mayúsculas.
  - **v4 (aleatorio)** para entidades que se crean: conversaciones y clientes.
  - **v5 (derivado del nombre)** para entidades de catálogo que deben ser estables: agentes, colas y usuarios demo.
- **Expresión regular de validación:** `^1[A-Z]{2}-[0-9A-F]{8}-[0-9A-F]{4}-[45][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$`.
- **Motivo del separador:** O, U y S no son dígitos hexadecimales, así que el prefijo no puede formar parte del propio UUID. Con el separador, la parte UUID sigue siendo válida para bases de datos y librerías estándar.

## Registro de prefijos

| Prefijo | Entidad | Estado |
|---|---|---|
| `1CO` | Conversación | Se aplica en esta feature |
| `1CU` | Cliente | Se aplica en esta feature |
| `1US` | Usuario | Se aplica en esta feature |
| `1AG` | Agente | Se aplica en esta feature |
| `1QU` | Cola | Se aplica en esta feature |
| `1RO` | Rol | Reservado (FE006) |
| `1TP` | Main topic | Reservado (FE005) |
| `1CK` | Check de cumplimiento | Reservado (FE005) |
| `1QY` | Consulta guardada | Reservado (FE002) |
| `1FL` | Flujo de insights | Reservado (FE004) |
| `1ND` | Nodo de flujo | Reservado (FE004) |
| `1RN` | Ejecución de flujo | Reservado (FE004) |
| `1CN` | Conector de datos | Reservado (FE005) |
| `1AU` | Entrada de auditoría | Reservado (FE005/FE006) |

Los códigos de enumeraciones fijas no son identificadores de entidad y se mantienen legibles: permisos, KPIs, canal, resolución, riesgo, slugs de dashboard y dimensiones.

## Criterios de aceptación

### Backend

1. Un único módulo `app/ids.py` define el registro de prefijos y las funciones para generar (v4 con un generador aleatorio con semilla, o v5 a partir de un nombre) y validar identificadores. Ningún otro módulo construye identificadores a mano (test que busca patrones `CNV-`, `CLI-` y `u-` en el código).
2. Todas las conversaciones tienen `id` con prefijo `1CO` y UUID v4, únicos y reproducibles con la misma semilla y fecha. Los identificadores salen de un generador aleatorio independiente, de modo que el resto del contenido del dataset no cambia (tests adaptados de T1).
3. `customer_id` usa `1CU` + UUID v4. El cálculo del FCR sigue coincidiendo con el cálculo independiente de los tests de T3.
4. Los usuarios demo tienen `id` `1US` + UUID v5 derivado de su email. `/api/auth/login` y `/api/auth/me` lo devuelven, y el token lo usa como `sub` (tests de auth adaptados).
5. Agentes y colas tienen identificador:
   - `1AG` + UUID v5 del nombre del agente y `1QU` + UUID v5 del nombre de la cola;
   - las conversaciones incluyen `agent_id` y `queue_id` además de los nombres;
   - `/api/catalog` devuelve `{id, name}` para ambos;
   - los filtros `agent` y `queue` de métricas y listado reciben identificadores;
   - los desgloses por agente y cola usan el identificador como `key` y el nombre como `label`.
6. Los tests cruzados de T4 (total del listado = volumen del desglose) siguen en verde con los nuevos identificadores.
7. `GET /api/conversations/{id}` acepta el identificador sin distinguir mayúsculas de minúsculas. Un identificador inexistente o mal formado devuelve `404`.
8. Un test comprueba que los prefijos de `app/ids.py` coinciden exactamente con la tabla del registro en `vault/ingenieria/registro-de-identificadores.md`.

### Front

9. El listado muestra el identificador abreviado (`1CO-4B2E9A7F`) y el completo al pasar el ratón. El detalle muestra el identificador completo.
10. Los filtros de cola y agente muestran nombres pero guardan identificadores en la URL. Los chips, el listado y los desgloses muestran siempre el nombre (tests adaptados).
11. El drill-down sigue devolviendo exactamente el valor pulsado (repetir en navegador la verificación de T7).

## Conocimiento afectado

- **Crear** `vault/ingenieria/registro-de-identificadores.md`: fuente canónica del formato y del registro de prefijos (activos y reservados), enlazada desde el índice de ingeniería.
- **Crear** ADR-004 «Identificadores con prefijo y UUID» en [Decisiones](../../vault/decisiones/Index.md), con las alternativas descartadas (prefijo dentro del UUID y prefijos solo hexadecimales).
- [ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md): actualizar el formato del `sub` del token.
- [Glosario](../../vault/glosario/terminos-del-harness.md): añadir «identificador de entidad» y «prefijo».
- [AGENTS.md](../../AGENTS.md): añadir la regla «todo identificador de entidad nuevo usa `PREFIJO-UUID`; consulta y amplía el registro antes de crear uno».
- Specs [FE003](../FE003-busqueda-semantica-de-conversaciones/spec.md) y [FE004](../FE004-disenador-de-flujos-de-insights/spec.md): renumerar sus ADR previstos a ADR-005 y ADR-006, porque ADR-004 pasa a ser este.

## Alcance

- Generación, validación y uso de identificadores en backend y front para conversaciones, clientes, usuarios, agentes y colas.
- Registro de prefijos en el vault y regla en `AGENTS.md`.

## Fuera de alcance

- Convertir main topics, checks y roles a identificadores. Tienen prefijo reservado y se harán cuando FE005 y FE006 los hagan editables.
- Mantener enlaces antiguos (`/conversaciones/CNV-…`): no hay nada entregado que los use.
- Persistencia o migración de datos.

## Riesgos y asunciones

- **Asunción:** los prefijos se escriben siempre en mayúsculas, y el UUID también.
- **Riesgo:** las URLs de filtros son menos legibles (`queue=1QU-…`). Se mitiga mostrando siempre nombres en chips y controles.
- **Riesgo:** los UUID v5 de agentes y colas dependen del nombre; renombrar uno cambiaría su identificador. Se acepta porque el catálogo es mock. Cuando FE005 lo haga editable, el identificador se generará una vez y se conservará.

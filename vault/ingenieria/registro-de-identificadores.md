---
title: "Registro de identificadores"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [ingenieria, identificadores, uuid, convencion]
created: 2026-09-27
updated: 2026-10-12
---

# Registro de identificadores

## Resumen

**Decisión:** todo identificador de entidad de la plataforma tiene el formato `PREFIJO-UUID`. Esta entrada es la fuente canónica del formato y de los prefijos; un test del backend falla si el código y esta tabla divergen.

## Conocimiento confirmado

**Formato:** `1CO-4B2E9A7F-3D1C-4A9B-8E5D-8F0A6C3E71AB`, siempre en mayúsculas.

- **Prefijo:** `1` seguido de dos letras mayúsculas, con un guion como separador.
- **UUID RFC 9562:**
  - **v4 (aleatorio):** para entidades que se crean, como conversaciones o clientes.
  - **v5 (derivado del nombre, namespace fijo del proyecto):** para entidades de catálogo que deben ser estables, como agentes, colas o usuarios demo.
- **Validación:** `^1[A-Z]{2}-[0-9A-F]{8}-[0-9A-F]{4}-[45][0-9A-F]{3}-[89AB][0-9A-F]{3}-[0-9A-F]{12}$`.
- **Implementación:** `backend/app/ids.py` (`new_id`, `stable_id`, `is_valid`, `normalize`). Ningún otro módulo construye identificadores a mano.

| Prefijo | Entidad | Estado |
|---|---|---|
| `1CO` | Conversación | Activo (FE008) |
| `1CU` | Cliente | Activo (FE008) |
| `1US` | Usuario | Activo (FE008) |
| `1AG` | Agente | Activo (FE008) |
| `1QU` | Cola | Activo (FE008) |
| `1RO` | Rol | Activo (FE006) |
| `1TP` | Main topic | Activo (FE005) |
| `1TS` | Tema secundario | Activo (FE005) |
| `1CK` | Check de cumplimiento | Activo (FE005) |
| `1QY` | Consulta guardada | Activo (FE002) |
| `1FL` | Flujo de insights | Activo (FE004) |
| `1ND` | Nodo de flujo | Activo (FE004) |
| `1RN` | Ejecución de flujo | Activo (FE004) |
| `1CN` | Conector de datos | Activo (FE005) |
| `1AU` | Entrada de auditoría | Activo (FE005; compartido con FE006) |

## Cómo añadir un prefijo

1. Busca en esta tabla una entidad equivalente antes de crear un prefijo nuevo.
2. Añade la fila aquí y la constante en `PREFIXES` de `backend/app/ids.py` en el mismo cambio. El test `test_prefixes_match_vault_registry` lo exige.
3. Elige v4 si la entidad se crea en tiempo de ejecución, o v5 si es un catálogo que debe ser estable.

## Límites y excepciones

- **No son identificadores de entidad** y se mantienen como códigos legibles: permisos, KPIs, canal, resolución, riesgo, slugs de dashboard y dimensiones.
- **Conexiones entre nodos** (FE004) no son entidades: se identifican por su nodo de origen y de destino.
- **Claves temporales de nodo** (FE004): el editor crea los nodos nuevos con `tmp-<uuid>` y el backend les asigna su `1ND` al guardar (`PUT /api/flows/{id}/graph` devuelve el `id_map`). Así ningún identificador de entidad se genera fuera de `app/ids.py`.
- **Código más identificador** (FE005): main topics (`1TP`), temas secundarios (`1TS`) y checks de cumplimiento (`1CK`) tienen un identificador v5 derivado de su **código**, que la API de configuración usa en sus rutas. El código sigue siendo la clave en conversaciones, filtros, URLs, consultas guardadas y flujos, y no se puede cambiar ([ADR-007](../decisiones/adr-007-configuracion-global-y-enmascarado.md)). El código de un tema secundario es el propio texto que guardan las conversaciones («compras online»).
- **Datos reales de Genesys** (FE011): los `1CO`, `1CU`, `1AG` y `1QU` de las conversaciones descargadas son **v5 derivados del identificador de Genesys** (`stable_id(prefijo, "genesys:<id>")`; el `1CU`, del contacto externo o, si no lo hay, del ANI), para que repetir una descarga no duplique nada. El espacio `genesys:` evita colisiones con el dataset sintético, y hay un test que lo comprueba. Los flujos y ejecuciones de descarga reutilizan `1FL` y `1RN`, en v4. Los flujos de IVR, los wrap-ups, las divisiones y los temas de STA no son entidades de la plataforma: se guardan con su identificador de Genesys. Ver [ADR-008](../decisiones/adr-008-postgresql-y-servicio-de-ingesta.md).
- **Riesgo de los v5:** dependen del nombre, así que renombrar un agente o una cola cambia su identificador. Se acepta mientras el catálogo sea mock.

## Fuentes

- [ADR-004 — Identificadores con prefijo y UUID](../decisiones/adr-004-identificadores-con-prefijo-y-uuid.md)
- [Spec FE008](../../features/FE008-identificadores-con-prefijo-y-uuid/spec.md)
- [Implementación](../../backend/app/ids.py)
- [Spec FE004](../../features/FE004-disenador-de-flujos-de-insights/spec.md)
- [Spec FE005](../../features/FE005-configuracion-de-la-plataforma/spec.md)
- [Spec FE011](../../features/FE011-ingesta-de-conversaciones-genesys/spec.md)
- [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562) (sustituye a RFC 4122)

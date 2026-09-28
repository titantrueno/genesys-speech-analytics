---
title: "Registro de identificadores"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [ingenieria, identificadores, uuid, convencion]
created: 2026-09-27
updated: 2026-09-28
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
| `1RO` | Rol | Reservado (FE006) |
| `1TP` | Main topic | Activo (FE005) |
| `1TS` | Tema secundario | Activo (FE005) |
| `1CK` | Check de cumplimiento | Reservado (FE005, constante `CHECK`) |
| `1QY` | Consulta guardada | Activo (FE002) |
| `1FL` | Flujo de insights | Activo (FE004) |
| `1ND` | Nodo de flujo | Activo (FE004) |
| `1RN` | Ejecución de flujo | Activo (FE004) |
| `1CN` | Conector de datos | Activo (FE005) |
| `1AU` | Entrada de auditoría | Activo (FE005; FE006 lo reutilizará) |

## Cómo añadir un prefijo

1. Busca en esta tabla una entidad equivalente antes de crear un prefijo nuevo.
2. Añade la fila aquí y la constante en `PREFIXES` de `backend/app/ids.py` en el mismo cambio. El test `test_prefixes_match_vault_registry` lo exige.
3. Elige v4 si la entidad se crea en tiempo de ejecución, o v5 si es un catálogo que debe ser estable.

## Límites y excepciones

- **No son identificadores de entidad** y se mantienen como códigos legibles: permisos, KPIs, canal, resolución, riesgo, slugs de dashboard y dimensiones.
- **Conexiones entre nodos** (FE004) no son entidades: se identifican por su nodo de origen y de destino.
- **Claves temporales de nodo** (FE004): el editor crea los nodos nuevos con `tmp-<uuid>` y el backend les asigna su `1ND` al guardar (`PUT /api/flows/{id}/graph` devuelve el `id_map`). Así ningún identificador de entidad se genera fuera de `app/ids.py`.
- **Main topics y checks** conservan su código legible hasta que FE005 los haga editables (prefijos `1TP` y `1CK` reservados).
- **Riesgo de los v5:** dependen del nombre, así que renombrar un agente o una cola cambia su identificador. Se acepta mientras el catálogo sea mock.

## Fuentes

- [ADR-004 — Identificadores con prefijo y UUID](../decisiones/adr-004-identificadores-con-prefijo-y-uuid.md)
- [Spec FE008](../../features/FE008-identificadores-con-prefijo-y-uuid/spec.md)
- [Implementación](../../backend/app/ids.py)
- [Spec FE004](../../features/FE004-disenador-de-flujos-de-insights/spec.md)
- [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562) (sustituye a RFC 4122)

---
title: "ADR-004 — Identificadores con prefijo y UUID"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, identificadores, uuid]
created: 2026-09-27
updated: 2026-09-27
---

# ADR-004 — Identificadores con prefijo y UUID

## Contexto

Los identificadores eran heterogéneos: `CNV-000001` secuenciales en las conversaciones, `CLI-00001` en los clientes, `u-admin` en los usuarios, y agentes y colas identificados por su nombre. Se quiere un formato único, no secuencial y que muestre el tipo de entidad de un vistazo, con prefijos elegidos por producto: `1CO` para conversaciones, `1CU` para clientes y `1US` para usuarios.

## Decisión

Todo identificador de entidad es `PREFIJO-UUID` en mayúsculas: un prefijo registrado, un guion y un UUID RFC 9562 (v4 para entidades creadas y v5 para catálogos estables). El formato y los prefijos viven en el [registro de identificadores](../ingenieria/registro-de-identificadores.md) y en `backend/app/ids.py`, y un test mantiene ambos sincronizados.

## Alternativas

- **Prefijo dentro del UUID** (`1CO2E9A7-…`, 36 caracteres): descartada. O, U y S no son hexadecimales, así que el valor no sería un UUID válido y lo rechazarían tipos `uuid` y parsers estándar.
- **Prefijos solo hexadecimales** (`1C0`, `1CC`…): descartada porque pierde legibilidad frente a CO, CU y US.
- **Mantener identificadores secuenciales:** descartada. Exponen volumen y orden, y no son únicos entre entornos.

## Consecuencias

- Los identificadores miden 40 caracteres, así que la UI los abrevia en listados (`1CO-4B2E9A7F`) y los muestra completos en el detalle.
- Los filtros por cola y agente llevan identificadores en la URL. La UI muestra siempre nombres.
- La parte UUID puede guardarse en columnas `uuid` si en el futuro hay base de datos.
- Toda entidad nueva debe registrar su prefijo antes de implementarse (regla en `AGENTS.md`).

## Fuentes

- [Spec FE008](../../features/FE008-identificadores-con-prefijo-y-uuid/spec.md)
- [Registro de identificadores](../ingenieria/registro-de-identificadores.md)
- [RFC 9562](https://www.rfc-editor.org/rfc/rfc9562) (sustituye a RFC 4122)

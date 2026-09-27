---
title: "Términos del harness"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [glosario, harness]
created: 2026-09-27
updated: 2026-09-27
---

# Términos del harness

## Definiciones

- **Harness:** conjunto de instrucciones, skills, gates y herramientas que condicionan cómo trabaja el agente.
- **Skill:** paquete invocable definido en `.devin/skills/<nombre>/SKILL.md`.
- **Gate:** condición observable que debe cumplirse antes de avanzar de fase.
- **Vault:** base de conocimiento Markdown versionada para personas y agentes.
- **Feature:** unidad de cambio documentada en `features/FEXXX-descripcion-breve/`, donde `XXX` es un número incremental y la descripción tiene 4 o 5 palabras.
- **Spec:** contrato de alcance y criterios de aceptación verificables.
- **TDD:** ciclo en el que una prueba falla primero y la implementación mínima la hace pasar.
- **Default-FAIL:** principio por el que la ausencia de evidencia se trata como fallo.
- **Identificador de entidad:** valor `PREFIJO-UUID` en mayúsculas (por ejemplo `1CO-4B2E9A7F-…`) que identifica una conversación, un cliente, un usuario, etc. Ver el [registro de identificadores](../ingenieria/registro-de-identificadores.md).
- **Prefijo:** tres caracteres (`1` + dos letras) que indican el tipo de entidad de un identificador.
- **ADR:** registro del contexto, decisión, alternativas y consecuencias de una decisión arquitectónica.

## Términos del producto

- **Summary:** resumen de 2 a 4 frases de una conversación: motivo, gestión y resultado.
- **Main topic:** motivo principal del contacto, con un valor del [catálogo bancario](../producto/catalogo-de-main-topics.md).
- **AHT (Average Handle Time):** duración media de las conversaciones.
- **FCR (First Contact Resolution):** % de conversaciones cuyo cliente no vuelve a contactar en los 7 días siguientes.
- **CSAT predicho:** satisfacción estimada de 1 a 5 a partir del contenido de la conversación.
- **Esfuerzo del cliente:** esfuerzo estimado de 1 a 5 que la gestión exige al cliente.
- **Riesgo de abandono:** probabilidad (baja, media o alta) de que el cliente deje el banco.
- **Drill-down:** navegar de un elemento agregado de un dashboard al listado de las conversaciones que lo componen.

## Fuentes

- [Instrucciones del proyecto](../../AGENTS.md)
- [Gobierno del vault](../Governance.md)

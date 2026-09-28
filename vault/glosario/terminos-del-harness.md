---
title: "Términos del harness"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [glosario, harness]
created: 2026-09-27
updated: 2026-09-28
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
- **Query asistida:** consulta del explorador construida visualmente o a partir de una frase, que se revisa antes de ejecutarse.
- **Condición:** regla `campo operador valor` de una query (por ejemplo, `Sentimiento < -0,3`).
- **Grupo:** conjunto de condiciones combinadas con Y (`and`) u O (`or`); puede anidarse un nivel.
- **Búsqueda semántica:** búsqueda de conversaciones por significado y no solo por palabras exactas, que devuelve el fragmento relevante. En la plataforma actual es una aproximación léxica con sinónimos ([ADR-005](../decisiones/adr-005-busqueda-vectorial-ligera.md)).
- **Fragmento:** ventana de 3 turnos consecutivos de una conversación, sin los turnos de sistema. Se identifica por la conversación y sus turnos de inicio y fin.
- **Puntuación de similitud:** similitud coseno entre la consulta y un fragmento, de 0 a 1. No es una probabilidad y no se puede comparar entre consultas.
- **Expansión de consulta:** términos que el diccionario de sinónimos del dominio añade a una consulta (por ejemplo, «visa» → «tarjeta»).
- **Flujo de insights:** grafo de nodos `Sampling → Prompt → Output` que toma una muestra de conversaciones, les aplica un prompt y produce un resultado. Tiene identificador `1FL` y se guarda como JSON ([arquitectura](../arquitectura/arquitectura-de-la-plataforma.md#flujos-de-insights-fe004)).
- **Nodo:** caja de un flujo (`1ND`) de tipo Sampling, Prompt u Output, con su posición en el lienzo y su configuración.
- **Conexión:** arista entre dos nodos de un flujo. Solo se admiten `Sampling → Prompt`, `Prompt → Prompt` y `Prompt → Output`, sin ciclos.
- **Sampling:** selección de una muestra de conversaciones con los filtros del explorador y un método (aleatorio, estratificado o primeros N).
- **Ejecución:** ejecución simulada (`1RN`) de la versión guardada de un flujo, con el estado de cada nodo (pendiente, en curso, ok o error), los resultados de cada output y una copia del grafo ejecutado ([ADR-006](../decisiones/adr-006-ejecucion-de-prompts-simulada.md)).
- **Drill-down:** navegar de un elemento agregado de un dashboard al listado de las conversaciones que lo componen.

## Fuentes

- [Instrucciones del proyecto](../../AGENTS.md)
- [Gobierno del vault](../Governance.md)
- [Spec FE004](../../features/FE004-disenador-de-flujos-de-insights/spec.md)

---
title: "Términos del harness"
type: knowledge
status: active
owners: [equipo-del-proyecto]
tags: [glosario, harness]
created: 2026-09-27
updated: 2026-10-12
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

- **Servicio de ingesta:** proceso aparte de la API que descarga conversaciones de Genesys Cloud y las guarda en PostgreSQL (FE011, [ADR-008](../decisiones/adr-008-postgresql-y-servicio-de-ingesta.md)).
- **Flujo de descarga:** flujo (`1FL`) con intervalo, canales y programación que lanza descargas de Genesys, a mano o programadas. Convive con los flujos de insights.
- **Analítica de Genesys:** lo que Genesys da de una conversación además de sus turnos (recorrido, tiempos, contención, Speech & Text Analytics). Es distinto del análisis de la plataforma.
- **Origen de datos:** `sintetico` (dataset generado, en memoria) o `real` (conversaciones de PostgreSQL de FE011). Es global y se elige en Configuración → Fuentes de datos (FE012).
- **Repositorio de conversaciones:** interfaz por la que todos los servicios obtienen las conversaciones; tiene una implementación por origen (FE012).
- **Análisis pendiente:** estado de una conversación real a la que aún falta el análisis de la plataforma (summary, main topic, CSAT, resolución, cumplimiento…).
- **Tramo:** cada paso de una conversación por un participante (cliente, flujo, IVR o bot, cola, agente).
- **Contención en el bot:** conversación que termina en el IVR o el bot sin pasar a una cola. Si pasa, es **derivada a agente**.
- **Transcripción parcial:** un agente o un bot intervino según las métricas, pero no tiene frases.
- **Mensaje no entregado:** mensaje de chat con estado `delivery-failed` (por ejemplo, el agente responde cuando el cliente ya se ha ido).
- **Análisis pendiente:** conversación real que aún no tiene el análisis de la plataforma (summary, main topic, CSAT…); lo calculará la fase con LLM.
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
- **Configuración:** ajustes globales de la plataforma (no por usuario) que se aplican en caliente al resto de secciones: taxonomía, checks, KPIs, zona horaria, privacidad y modelo por defecto ([ADR-007](../decisiones/adr-007-configuracion-global-y-enmascarado.md)).
- **Taxonomía:** catálogo editable de main topics (`1TP`) y temas secundarios (`1TS`). Un tema en uso no se borra: se **desactiva**, deja de ofrecerse en los filtros y sus conversaciones lo conservan.
- **Check por frases:** check de cumplimiento creado en Configuración que se cumple si el agente dice alguna de sus frases. Los seis checks de FE001 son **checks del análisis**: su resultado viene del análisis de cada conversación.
- **Umbral (verde / ámbar):** valores de un KPI que colorean su tarjeta. Si más es mejor, verde a partir del umbral verde, ámbar a partir del ámbar y rojo por debajo; si más es peor, al revés. Un valor igual al umbral toma el color mejor.
- **Enmascarado de PII:** sustitución de teléfonos, emails, DNI/NIE, IBAN y tarjetas completas por `[TELÉFONO]`, `[EMAIL]`, `[DNI]`, `[IBAN]` y `[TARJETA]`. Activado por defecto; el índice de búsqueda y los prompts lo aplican siempre.
- **Registro de auditoría:** entrada `1AU` por cada cambio aceptado de configuración (FE005) o de usuarios y roles (FE006), con quién, cuándo, sección, elemento, valor anterior y nuevo. El registro es compartido; cada sección muestra solo sus entradas.
- **Rol:** conjunto de permisos con código (clave en los usuarios, no cambia), nombre e identificador `1RO`. Los roles **base** (`admin`, `supervisor`, `analista` y `viewer`) no se pueden borrar; los **personalizados** se crean desde Usuarios y roles ([ADR-003](../decisiones/adr-003-auth-mock-por-roles.md)).
- **Permiso:** acción o sección que un rol habilita. La lista es fija: `dashboards:view` (ver dashboards), `conversations:view` (ver conversaciones), `explorer:use` (usar el explorador), `search:use` (usar la búsqueda semántica), `flows:view` (ver flujos), `flows:edit` (editar y ejecutar flujos), `config:view` (ver configuración), `config:edit` (editar configuración) y `users:admin` (administrar usuarios y roles).
- **Matriz de permisos:** tabla de la pestaña Roles con los permisos en filas y los roles en columnas; cada casilla se guarda al cambiarla y se aplica en la siguiente petición de los usuarios del rol.
- **Drill-down:** navegar de un elemento agregado de un dashboard al listado de las conversaciones que lo componen.

## Fuentes

- [Instrucciones del proyecto](../../AGENTS.md)
- [Gobierno del vault](../Governance.md)
- [Spec FE004](../../features/FE004-disenador-de-flujos-de-insights/spec.md)
- [Spec FE005](../../features/FE005-configuracion-de-la-plataforma/spec.md)
- [Spec FE006](../../features/FE006-gestion-de-usuarios-y-roles/spec.md)

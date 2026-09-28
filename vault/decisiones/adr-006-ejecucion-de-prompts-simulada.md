---
title: "ADR-006 — Ejecución de prompts simulada con punto de extensión para un LLM real"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, flujos, llm, prompts, fe004]
created: 2026-09-28
updated: 2026-09-28
---

# ADR-006 — Ejecución de prompts simulada con punto de extensión para un LLM real

## Contexto

FE004 permite diseñar flujos `Sampling → Prompt → Output` y ejecutarlos. El piloto quiere validar la experiencia de diseño, no la calidad de los insights. Las llamadas reales a un LLM y la gestión de claves de proveedor quedan fuera de alcance de la [spec](../../features/FE004-disenador-de-flujos-de-insights/spec.md). Además, el backend es deliberadamente ligero y sin dependencias pesadas ([ADR-002](adr-002-stack-vite-fastapi-mock.md)).

## Decisión

- **Interfaz `PromptRunner`** (`backend/app/flows/prompting.py`): `run(config, conversation, previous)` devuelve el resultado de un prompt para una conversación. `previous` es el resultado del prompt anterior en una cadena. La API la obtiene con `get_prompt_runner()` (`backend/app/routers/flows.py`), sustituible con `dependency_overrides`; un test lo hace sin cambiar la API.
- **Implementación actual, `MockPromptRunner`:** no llama a ningún modelo. Deriva un resultado **determinista** (con `sha256`, no con `hash()`, que cambia entre procesos) del análisis mock de cada conversación y respeta el formato de salida:
  - **texto:** main topic y primera frase del summary (más detalle con el modelo `mock-preciso`);
  - **etiqueta:** siempre una de la lista; elige la idéntica a un hecho del análisis y, si no hay, la que lo contiene, con prioridad main topic > sentimiento (umbrales ±0,3 de la UI) > resolución > riesgo de abandono > temas secundarios; sin coincidencias, una fija por conversación;
  - **JSON:** exactamente los campos y tipos del esquema; los nombres conocidos (`main_topic`, `sentimiento`, `resolucion`, `csat`, `riesgo_abandono`, `canal`, `cola`, `resumen`) toman el valor del análisis.
- **Ejecución en segundo plano** con `BackgroundTasks` y un retardo por elemento (`FLOW_RUN_STEP_DELAY_MS`, 15 ms por defecto) para que el progreso sea visible por polling. Cualquier excepción del runner marca el nodo en `error` («Error al ejecutar el prompt: …»); los nodos que dependen de él quedan en `pendiente`.
- **Modelos y temperatura** se guardan en la configuración del nodo, aunque el simulador solo use el modelo para variar la longitud del texto.

## Alternativas

- **Llamar ya a un LLM real:** descartada por alcance (claves, coste, privacidad de las transcripciones y evaluación de calidad pendientes).
- **Resultados aleatorios:** descartada. Impiden tests de ida y vuelta y confunden en la demo: la misma ejecución daría resultados distintos.
- **Ejecutar en el propio `POST`:** descartada. Bloquearía la petición y no habría progreso que mostrar.
- **Cola de tareas externa (Celery, RQ):** descartada para el piloto por infraestructura; es la evolución natural con un LLM real.

## Consecuencias

- La demo muestra resultados coherentes con cada conversación (por ejemplo, etiquetas de sentimiento que coinciden con el de la conversación), pero **no demuestran la calidad de un LLM**.
- **Migrar a un LLM real** consiste en:
  1. implementar un `PromptRunner` que renderice la plantilla con `render_template` y llame al proveedor;
  2. validar la respuesta contra el formato (etiqueta de la lista, esquema JSON) y convertir los fallos en `NodeFailure`;
  3. inyectarlo en `get_prompt_runner()`.

  La API, el formato JSON del flujo y el front no cambian.
- **Pendiente con un LLM real** (hipótesis, sin validar): concurrencia y límites de tasa del proveedor, reintentos, coste por ejecución, cancelación, enmascarado de datos personales antes de enviar transcripciones (FE005) y ejecutar fuera del proceso de la API.
- Las ejecuciones viven en memoria y se pierden al reiniciar, como el resto de escrituras.

## Fuentes

- [Spec FE004](../../features/FE004-disenador-de-flujos-de-insights/spec.md)
- [Plan y evidencia de FE004](../../features/FE004-disenador-de-flujos-de-insights/plan.md)
- [Implementación del prompt](../../backend/app/flows/prompting.py)
- [Ejecutor](../../backend/app/flows/runs.py)
- [FastAPI · Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [FastAPI · Testing dependencies with overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/)

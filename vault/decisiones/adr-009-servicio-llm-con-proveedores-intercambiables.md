---
title: "ADR-009 — Servicio de LLM aparte con proveedores intercambiables"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, llm, gemini, openai, anthropic, flujos, summary, main-topic, fe013]
created: 2026-10-12
updated: 2026-10-12
---

# ADR-009 — Servicio de LLM aparte con proveedores intercambiables

## Contexto

Hasta FE013 los prompts de los flujos de insights eran simulados ([ADR-006](adr-006-ejecucion-de-prompts-simulada.md)) y las conversaciones reales de Genesys llegaban sin summary ni main topic ([ADR-008](adr-008-postgresql-y-servicio-de-ingesta.md)). La persona usuaria pidió en la [spec de FE013](../../features/FE013-servicio-llm-summary-main-topic/spec.md):

- un «nuevo backend» que conecte con un LLM;
- Gemini por defecto, pero cambiar a OpenAI o Anthropic de forma sencilla;
- generar summary y main topic desde los flujos de insights, eligiendo en un desplegable el campo donde se guarda;
- y, ya en la implementación, obtener los dos campos **en una sola petición** al LLM.

## Decisión

- **Proceso aparte** `backend/llm/` (`uvicorn llm.main:app`, puerto 8002), como el de ingesta:
  - es el **único** que lee `GEMINI_API_KEY`, `OPENAI_API_KEY` y `ANTHROPIC_API_KEY` (lista blanca `LLM_KEYS` de `app/envfile.py`; test estructural);
  - solo importa de `app` los módulos `ids`, `clock` y `envfile`;
  - la API lo llama con el token interno `LLM_TOKEN` (`app/llm_client.py`); `/health` dice qué proveedores tienen clave, nunca la clave.
- **Proveedores intercambiables:** interfaz `LlmProvider` y registro `llm/providers/__init__.py` con `gemini`, `openai`, `anthropic` y `simulado`. Añadir uno es escribir su clase, darlo de alta en el registro y poner sus modelos en `app/flows/catalog.py`.
  - Llamadas REST con `httpx`, sin SDK de cada proveedor, para no añadir dependencias ([ADR-002](adr-002-stack-vite-fastapi-mock.md)) y probar sin red con `MockTransport`.
  - Errores con código (`missing_key` → `503`, `key_rejected` y `provider_failure` → `502`); `429` y `5xx` se reintentan 2 veces; un semáforo limita las llamadas simultáneas (`LLM_MAX_CONCURRENCY`, 4).
  - Los logs registran proveedor, modelo, duración y resultado, nunca el prompt, la respuesta ni las claves.
- **Catálogo de modelos** en la API, con la marca `temperature` por modelo: solo se envía a los modelos que la admiten. Por defecto, `gemini` con `gemini-3.5-flash-lite` (a petición de la persona usuaria).
- **Prompts:** `RoutingPromptRunner` usa `MockPromptRunner` si el nodo es simulado (o no tiene proveedor, como los flujos anteriores) y `LlmPromptRunner` en otro caso. La respuesta se valida por formato; las rechazadas o fallidas se excluyen de los outputs y se cuentan por nodo; servicio caído o clave rechazada detienen el nodo. Prompts en paralelo (4).
- **Una llamada para summary y main topic:** un campo de texto del esquema JSON puede llevar **valores permitidos**, que el proveedor recibe como `enum`. Un Prompt JSON con `summary` y `main_topic` (con los main topics activos como valores permitidos) y un Output «Guardar en campos» con dos asignaciones guardan los dos campos con una llamada por conversación.
- **Output «Guardar en campos»** (`kind: campo`): asignaciones `{target: summary|main_topic, source}` y `overwrite`. Solo con datos reales. La API escribe en lotes de 100 por `POST /analysis/fields` del servicio de ingesta, **único escritor** de PostgreSQL; el main topic se guarda por código y la trazabilidad (proveedor, modelo, `1RN`, instante) va en `analysis.llm_meta`, sin cambiar el `status`.
- **Plantillas** «Generar summary», «Generar main topic» y «Generar summary y main topic» (`app/flows/templates.py`).

## Alternativas

- **Módulo dentro de la API:** descartada en la entrevista; la API conocería las claves.
- **SDK oficial de cada proveedor:** tres dependencias más y tests más difíciles sin red.
- **Dos llamadas (una por campo):** descartada por la persona usuaria por coste y latencia.
- **Que la API escriba en PostgreSQL:** rompería el escritor único de ADR-008; la API sigue leyendo en solo lectura.
- **Fechas fijas en las plantillas («últimos 7 días»):** se quedarían desfasadas; el Sampling sin fechas es relativo al periodo por defecto.

## Consecuencias

- Hay un cuarto proceso que arrancar: [runbook del servicio de LLM](../operaciones/runbook-servicio-llm.md). `dev.sh` lo arranca si hay `LLM_TOKEN`.
- **Hecho:** comprobado contra Gemini real el 2026-10-12: prueba de proveedor, etiqueta, JSON con `enum` y un flujo de 3 conversaciones. La forma REST de la guía de Google para JSON (`responseFormat.text`) responde `400`; el adaptador usa `responseMimeType` + `responseJsonSchema`.
- **Hipótesis:** los adaptadores de OpenAI y Anthropic siguen su documentación, pero no se han probado contra las APIs reales (no hay claves). Los modelos de OpenAI no confirman si admiten `temperature`; por prudencia no se envía.
- Las transcripciones salen hacia el proveedor **enmascaradas** ([ADR-007](adr-007-configuracion-global-y-enmascarado.md)); el enmascarado por patrones puede no cubrir toda la PII, aceptado para el laboratorio.
- Una muestra grande tarda y consume cuota; no hay cancelación ni control de coste (fuera de alcance).

## Fuentes

- [Spec FE013](../../features/FE013-servicio-llm-summary-main-topic/spec.md) y [plan, con la documentación contrastada](../../features/FE013-servicio-llm-summary-main-topic/plan.md)
- [Servicio de LLM](../../backend/llm/main.py) y [proveedores](../../backend/llm/providers/__init__.py)
- [Runner de prompts con LLM](../../backend/app/flows/llm_runner.py) y [catálogo](../../backend/app/flows/catalog.py)
- [Escritura de campos en la ingesta](../../backend/ingestion/analysis.py)
- [Gemini · Generating content](https://ai.google.dev/api/generate-content)
- [OpenAI · Create chat completion](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create)

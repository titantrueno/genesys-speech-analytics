---
title: "Runbook del servicio de LLM"
type: runbook
status: active
owners: [equipo-del-proyecto]
tags: [operaciones, runbook, llm, gemini, openai, anthropic, fe013, fe014]
created: 2026-10-12
updated: 2026-10-13
---

# Runbook del servicio de LLM

## Cuándo usarlo

Para arrancar el servicio de LLM, comprobar qué proveedores tienen clave, cambiar de proveedor y diagnosticar un Prompt que falla ([ADR-009](../decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md)).

## Prerrequisitos

- **`.env` en la raíz** con `LLM_TOKEN` (compartido por la API y el servicio) y la clave de cada proveedor que se use: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. Opcionales: `LLM_MAX_CONCURRENCY` (1–64, 4 por defecto) y, en la API, `LLM_URL` (`http://localhost:8002`). Nunca se versiona ni se copia en el vault.
- Para guardar campos del análisis (summary, main topic y, desde FE014, el resto): datos reales, PostgreSQL y el servicio de ingesta ([runbook de la ingesta](runbook-ingesta-de-genesys.md)).
- **Concurrencia:** cada nodo Prompt con LLM lanza hasta 4 llamadas a la vez. Si se baja `LLM_MAX_CONCURRENCY`, las demás esperan en el servicio; la API espera cada respuesta hasta 240 s, más que el peor caso del servicio (3 intentos de 60 s).

## Procedimiento

1. **Arrancar:** `./scripts/dev.sh` lo arranca si hay `LLM_TOKEN` (puerto `LLM_PORT`, 8002). A mano: `cd backend && .venv/bin/uvicorn llm.main:app --port 8002`.
2. **Comprobar:** `curl localhost:8002/health` devuelve `keys` con `true`/`false` por proveedor. En la plataforma: Configuración → Modelos de IA → «Probar» en cada proveedor.
3. **Cambiar de proveedor por defecto:** Configuración → Modelos de IA (afecta a los Prompt nuevos). Cada nodo Prompt guarda su proveedor y su modelo.
4. **Añadir una clave:** escribirla en el `.env` y **reiniciar el servicio de LLM** (la lee al arrancar).
5. **Generar summary y main topic:** Flujos de insights → «Nuevo flujo» → plantilla «Generar summary y main topic» (una llamada por conversación). Ajustar el tamaño de la muestra y ejecutar.
6. **Generar el análisis completo (FE014):** plantilla «Generar análisis completo»: resolución, CSAT, esfuerzo, riesgo, sentimiento (solo si Genesys no lo da), un campo por check activo, temas secundarios, palabras clave y entidades, en una llamada. Si se crea un check después, la plantilla lo incluye en un flujo nuevo; en uno existente hay que añadir su campo y su asignación.

## Verificación

- «Probar» responde «El proveedor respondió correctamente».
- En la ejecución, el Output «Guardar en campos» muestra los recuentos por campo y el detalle de la conversación enseña cada campo escrito, aunque el resto del análisis siga pendiente; los KPIs del periodo se calculan con las conversaciones que ya tienen el dato (`based_on`).

## Diagnóstico

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Validación: «El servicio de LLM no está disponible» | El servicio no responde o `LLM_TOKEN` difiere entre API y servicio | Arrancarlo; comprobar el mismo `LLM_TOKEN` en los dos procesos |
| «El proveedor X no tiene clave configurada» | Falta la clave en el `.env` o el servicio no se reinició | Añadirla y reiniciar el servicio |
| «El proveedor rechazó la clave» | Clave caducada o de otro proyecto | Sustituirla; el nodo se detiene sin seguir llamando |
| Muchas conversaciones «rechazado» | El modelo no respeta el formato (etiqueta fuera de la lista, JSON fuera del esquema) | Revisar la plantilla; para main topic, usar valores permitidos |
| «Guardar en campos solo funciona con datos reales» | Origen `sintetico` | Configuración → Fuentes de datos → origen real |
| Un campo «Rechazado» con motivo (fuera de rango, no es un tema activo…) | El modelo devolvió un valor no válido para ese destino; los demás campos se guardan | Reforzar la instrucción del campo en la plantilla; volver a ejecutar sin «Sobrescribir» |
| Sentimiento «Omitido: Genesys ya da el sentimiento» | La conversación tiene sentimiento de Genesys, que siempre manda | Nada: es lo esperado |
| Validación `unknown_check` | Un check asignado se borró o desactivó | Quitar su asignación (y su campo del JSON) |
| «Generar análisis completo» responde que los checks no caben | Más de 27 checks activos | Desactivar checks o crear el flujo con varios Prompts |
| Output «campo» en error «servicio de ingesta» | El servicio de ingesta no responde | Arrancarlo; lo escrito antes del fallo se conserva |

El log del servicio (`.dev-logs/llm.log`) registra proveedor, modelo, intento, duración y resultado; nunca el prompt, la respuesta ni las claves.

## Rollback

- Volver a «Simulado» en Configuración → Modelos de IA y en los nodos Prompt: no se llama a ningún LLM.
- Para borrar lo que escribió un LLM en unas conversaciones: redescargarlas con un flujo de descarga con «Sobrescribir», que deja su análisis `pendiente`, vacía todos sus campos (también `sentiment`, `compliance` y `entities`) y vacía `llm_meta`.

## Escalado

Propietario: equipo del proyecto. Un fallo persistente de un proveedor se revisa en su consola y en su página de estado; la plataforma no reintenta más de 2 veces.

## Fuentes

- [ADR-009](../decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md)
- [Servicio de LLM](../../backend/llm/main.py)
- [scripts/dev.sh](../../scripts/dev.sh) y [.env.example](../../.env.example)
- [Plan de FE013](../../features/FE013-servicio-llm-summary-main-topic/plan.md)
- [Spec de FE014](../../features/FE014-analisis-completo-con-llm/spec.md) y [plan](../../features/FE014-analisis-completo-con-llm/plan.md)

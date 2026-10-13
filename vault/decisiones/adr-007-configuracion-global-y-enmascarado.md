---
title: "ADR-007 — Configuración global en memoria, leída en caliente, y enmascarado de PII por defecto"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, configuracion, privacidad, pii, cumplimiento, fe005, fe014]
created: 2026-09-29
updated: 2026-10-13
---

# ADR-007 — Configuración global en memoria, leída en caliente, y enmascarado de PII por defecto

## Contexto

FE005 hace editables la taxonomía, los checks de cumplimiento, los umbrales de los KPIs, la zona horaria, la privacidad y el modelo de IA por defecto ([spec](../../features/FE005-configuracion-de-la-plataforma/spec.md)). Hasta entonces eran constantes de módulo leídas por FE001–FE004, así que cada cambio debe llegar a dashboards, listado, detalle, explorador, búsqueda y flujos sin reiniciar. El backend no tiene persistencia ([ADR-002](adr-002-stack-vite-fastapi-mock.md)). Además, el [gobierno del vault](../Governance.md) prohíbe almacenar o reproducir datos personales innecesarios, y las transcripciones de voz contienen DNI e IBAN ficticios.

## Decisión

- **Una instantánea inmutable y versionada** (`Config` en `backend/app/config/store.py`), global a la plataforma. Los servicios la leen en cada petición con `get_config()`; nada copia su contenido a constantes.
- **Una sola ruta de escritura:** `apply_change(user, section, element, change)` lee el valor anterior, guarda la nueva instantánea y crea la entrada de auditoría (`1AU`) bajo el mismo cerrojo. Un cambio rechazado (`403`, `422`, `409`) o sin efecto no deja entrada.
- **Cachés derivadas por identidad de instantánea**, no por versión: campos del explorador (`get_fields()`) y cumplimiento efectivo. La versión vuelve a 0 al reiniciar el store, y un número repetido devolvería datos de otro estado.
- **Código legible más identificador:** main topics (`1TP`), temas secundarios (`1TS`) y checks (`1CK`) tienen un identificador v5 derivado de su código para la API de configuración, pero el código sigue siendo la clave en conversaciones, filtros, URLs, consultas guardadas y flujos, y no se puede cambiar. Un elemento en uso no se borra: se desactiva. Deja de ofrecerse, pero sigue siendo un valor válido.
- **Checks del análisis y checks por frases:** los seis de FE001 conservan el resultado del análisis mock; uno nuevo se evalúa por sus frases en los turnos del agente. Todo lo que muestra cumplimiento pasa por `effective_compliance`, así que el drill-down sigue cuadrando con el KPI.
- **Enmascarado de PII activado por defecto** (`backend/app/privacy/masking.py`). Se aplica al serializar, sobre una copia: el dataset no cambia y el interruptor es reversible. **Siempre**, con independencia del interruptor, el índice de la búsqueda semántica y la entrada de los prompts de los flujos usan texto enmascarado.
- **Configuración pública:** `GET /api/config/public`, sin sesión, devuelve solo nombre, zona horaria e idioma, porque el login y todos los roles los necesitan. El resto de la configuración exige `config:view`.
- **Zona horaria:** `started_at` lleva la zona del banco (`Europe/Madrid`); los días de filtros, series, listado, explorador e informes se calculan en la zona configurada, y el front formatea todas las fechas con ella en `frontend/src/lib/format.ts`.

## Alternativas

- **Configuración por usuario o por tenant:** descartada por la spec; la plataforma es de un solo banco.
- **Recalcular el dataset al cambiar la taxonomía** (reclasificar conversaciones): descartada. El análisis es mock y reclasificar cambiaría KPIs ya vistos; un main topic nuevo empieza sin conversaciones.
- **Migrar filtros, URLs, consultas y flujos a identificadores `1TP`:** descartada con el usuario al revisar la spec: más coherente con [ADR-004](adr-004-identificadores-con-prefijo-y-uuid.md), pero rompía cuatro features entregadas.
- **Reconstruir el índice al cambiar el interruptor:** descartada. Unos 2,5 s de reconstrucción y una ventana en la que un DNI sí sería buscable; indexar siempre el texto enmascarado es más simple y más privado.
- **Enmascarar el dataset al generarlo:** descartada. El interruptor dejaría de ser reversible y los checks por frases perderían el texto original.

## Consecuencias

- Un cambio de configuración se ve en todas las secciones en la siguiente petición; el front invalida todas sus consultas en caché al guardar.
- La configuración, como el resto de escrituras, **se pierde al reiniciar la API**.
- Buscar un DNI o un IBAN no encuentra nada, ni con el interruptor desactivado. Se acepta: reduce algo la recuperación de términos numéricos.
- Los patrones de PII son españoles (DNI/NIE con letra de control, IBAN, teléfonos 6/7/8/9 con o sin +34) más email y tarjeta completa. Los últimos 4 dígitos de una tarjeta se conservan. **Hipótesis:** con datos reales habrá formatos que se escapen; el test de dataset completo solo cubre los del generador.
- Un check nuevo evaluado por frases es una aproximación léxica, no un modelo: «no dijo la frase» no siempre significa «no cumplió».
- Con un LLM real ([ADR-006](adr-006-ejecucion-de-prompts-simulada.md)), las transcripciones ya salen enmascaradas hacia el proveedor.

## Ampliaciones

- **FE012 (2026-10-12):** el **origen de datos** (`sintetico` o `real`) es una sección más (`fuentes`), global, auditada, en memoria y con `sintetico` por defecto. El ANI, el DNIS y el `externalTag` **no se enmascaran** en este desarrollo (se muestran, se buscan y se filtran); el texto de los turnos y las frases de los temas sí. Con datos reales se pueden contrastar los formatos de PII que se escapan: queda como hipótesis a validar con conversaciones de más días.
- **FE013 (2026-10-12):** «Modelos de IA» ya no es una lista mock: proveedores Gemini (por defecto, `gemini-3.5-flash-lite`), OpenAI, Anthropic y Simulado, con el estado de las claves del servicio de LLM y «Probar» ([ADR-009](adr-009-servicio-llm-con-proveedores-intercambiables.md)). Las claves nunca están en la configuración. **Taxonomía:** borrar un main topic comprueba también las conversaciones reales de PostgreSQL, sea cual sea el origen activo (`409` con el recuento de cada origen; `503` si la base no responde), porque un flujo puede haberlo escrito en ellas. Los prompts que salen hacia un proveedor externo usan el texto enmascarado de esta decisión.
- **FE014 (2026-10-13):** el cumplimiento de un check tiene un cuarto estado, **pendiente**, además de cumple, no cumple y no aplica (`app/config/compliance.py`). Orden de evaluación: un check que no aplica al canal es «no aplica»; si no, manda el **resultado guardado** en el análisis (el sintético o el que escribe un flujo con LLM, que puede rellenar cualquier check activo, también los personalizados); sin él, un check base queda pendiente y uno personalizado se evalúa por frases. Una conversación cuenta para el KPI de cumplimiento y para el filtro «cumple» si algún check que le aplica tiene resultado. La caché del cumplimiento efectivo se invalida también cuando cambia la conversación (una recarga de las reales), no solo la configuración. Un check creado después de ejecutar un flujo queda pendiente en las conversaciones reales hasta otra ejecución.

## Fuentes

- [Spec FE005](../../features/FE005-configuracion-de-la-plataforma/spec.md)
- [Plan y evidencia de FE005](../../features/FE005-configuracion-de-la-plataforma/plan.md)
- [Store de configuración](../../backend/app/config/store.py)
- [Enmascarado](../../backend/app/privacy/masking.py)
- [Cumplimiento efectivo](../../backend/app/config/compliance.py)
- [Spec FE014](../../features/FE014-analisis-completo-con-llm/spec.md)
- [Gobierno del vault](../Governance.md)

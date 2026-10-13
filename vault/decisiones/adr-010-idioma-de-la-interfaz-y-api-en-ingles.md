---
title: "ADR-010 — Idioma de la interfaz como ajuste de la plataforma y API solo en inglés"
type: adr
status: active
owners: [equipo-del-proyecto]
tags: [adr, i18n, idioma, frontend, api, openapi, fe016]
created: 2026-10-13
updated: 2026-10-13
---

# ADR-010 — Idioma de la interfaz como ajuste de la plataforma y API solo en inglés

## Contexto

La interfaz estaba escrita en español, con unas 6.400 líneas de textos fijos en el código y sin capa de traducción ([FE005](../../features/FE005-configuracion-de-la-plataforma/spec.md) dejó «traducir la UI» fuera de alcance y solo ofrecía `es-ES`). La persona usuaria pidió en la [spec de FE016](../../features/FE016-idioma-ingles-de-la-interfaz/spec.md):

- poder usar la interfaz en inglés;
- que el idioma se elija **solo en el menú de opciones** (Configuración), sin selectores en el login ni en el panel principal;
- que el cambio afecte **solo a menús y textos fijos**, no al contenido (conversaciones, resúmenes, main topic, palabras clave);
- que los mensajes de las rutas, las APIs y sus errores estén **solo en inglés**, sea cual sea el idioma configurado.

## Decisión

Hechos que quedan como decisión vigente:

- **El idioma es un ajuste de la plataforma:** el campo `language` de Configuración → General (`es-ES` o `en-US`; «Idioma de la interfaz»). `GET /api/config/public` lo da sin sesión, así que el login ya sale en ese idioma. No hay selector personal, ni en el navegador, ni en la barra lateral, ni en el login.
- **Capa i18n propia, sin dependencias nuevas** (`frontend/src/i18n/`):
  - diccionarios planos por área, `es/<área>.ts` y `en/<área>.ts`; `es` define las claves y `en` debe cumplirlas (error de compilación) con los mismos parámetros (test de paridad);
  - `t(clave, {param})` con `{param}` y plurales `clave_one`/`clave_other` cuando se pasa `count`; `tOr(clave, respaldo)` para etiquetas de catálogo;
  - `I18nProvider` lee el idioma público, fija `<html lang>` y el idioma de `Intl` (`lib/format.ts`: números, porcentajes, fechas y duraciones); la zona horaria sigue siendo la de la configuración.
- **Qué se traduce y qué no:** se traducen los menús y los textos fijos de toda la interfaz. **No** se traducen los datos: transcripciones, resúmenes, main topics, palabras clave, temas secundarios, entidades, nombres de colas, agentes, flujos, roles, checks y taxonomía, ni los textos de las plantillas de prompt.
- **Catálogos del backend:** operadores, campos, valores fijos, KPIs, opciones de flujos, permisos y estados llegan con etiquetas en español; el front las traduce **por clave** (`exp.field.<clave>`, `kpi.<código>.label`, `flows.cat.<grupo>.<valor>`, `usr.permission.<permiso>`…) y, si la clave no existe, muestra la etiqueta del backend.
- **La API habla solo inglés:** `detail` de errores HTTP, errores de validación por campo, incidencias de validación de flujos, motivos por campo, mensajes de las ejecuciones y del log de las descargas, errores de los servicios de ingesta y de LLM, textos de auditoría nuevos y todo el contrato OpenAPI. La API **no lee `Accept-Language`** ni el idioma configurado. Las etiquetas de catálogo y los datos no son mensajes.
- **Comprobaciones automáticas:** paridad de claves y parámetros entre `es` y `en`; un test que falla si `frontend/src` contiene texto de interfaz en español escrito a mano; y `backend/tests/test_api_messages_english.py`, que falla si un mensaje de error, de estado o de log del código, o una descripción del OpenAPI exportado, está en español, o si el mismo error cambia con el idioma configurado o con `Accept-Language`.

## Alternativas

- **Librería de i18n (i18next, react-intl):** descartada; con dos idiomas y plurales sencillos no compensa la dependencia ni su tamaño ([ADR-002](adr-002-stack-vite-fastapi-mock.md) prefiere pocas dependencias).
- **Idioma personal guardado en el navegador, con selector en la barra lateral y el login:** se implementó en la primera fase y se retiró por decisión de la persona usuaria (2026-10-13): queda un único ajuste.
- **La API traduce según `Accept-Language`:** descartada por la persona usuaria; la API es solo inglés.
- **Traducir también el contenido:** fuera de alcance; los datos son de negocio.

## Consecuencias

- Hipótesis aceptada como límite: con la interfaz en español, los mensajes de error que vienen de la API (por ejemplo, un error de validación bajo un campo de Configuración) se muestran en inglés.
- Los roles sin permiso para editar la configuración no pueden cambiar el idioma: usan el de la plataforma.
- El intérprete de lenguaje natural del explorador y la búsqueda semántica trabajan con frases en español (las conversaciones lo están); en inglés la interfaz lo indica en la etiqueta y el ejemplo.
- El texto del Output «informe» de un flujo y las entradas de auditoría ya guardadas conservan el español con el que se generaron.
- Los datos en español dentro de una interfaz inglesa (transcripciones, resúmenes, palabras clave) no llevan `lang="es"`: un lector de pantalla los leerá con la voz del idioma de la página (WCAG 3.1.2). Queda como mejora futura.
- Los diccionarios `es` y `en` se cargan juntos en la carga inicial: unos 135 kB (40 kB comprimidos). Cargar `en` bajo demanda ahorraría la mitad a costa de un estado de carga; no compensa con dos idiomas.
- Añadir un idioma es: un diccionario por área con las mismas claves, su código en `frontend/src/i18n/languages.ts` y en `LANGUAGES` del backend (`backend/app/config/model.py`); los tests de paridad guían el resto.
- Con `INGESTION_TOKEN` configurado y sin el servicio de ingesta, guardar el idioma responde `503` ([ADR-008](adr-008-postgresql-y-servicio-de-ingesta.md)): para probarlo en local sin base, arrancar con la variable de entorno `INGESTION_TOKEN` vacía.

## Fuentes

- [Spec FE016](../../features/FE016-idioma-ingles-de-la-interfaz/spec.md) y [plan](../../features/FE016-idioma-ingles-de-la-interfaz/plan.md)
- [Capa i18n del front](../../frontend/src/i18n/I18nProvider.tsx)
- [Test de paridad](../../frontend/src/i18n/dictionaries.test.ts) y [test de textos escritos a mano](../../frontend/src/i18n/noHardcodedSpanish.test.ts)
- [Test de mensajes de la API en inglés](../../backend/tests/test_api_messages_english.py)
- [ADR-007 — Configuración global](adr-007-configuracion-global-y-enmascarado.md)

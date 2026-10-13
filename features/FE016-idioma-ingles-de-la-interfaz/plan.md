# FE016 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md). Siguiente paso: `/build`, una tarea cada vez y en orden. Cada tarea deja `./scripts/ci.sh` en verde y la interfaz usable (lo no migrado sigue en español).

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| [Arquitectura](../../vault/arquitectura/arquitectura-de-la-plataforma.md) (l. 105), [ADR-007](../../vault/decisiones/adr-007-configuracion-global-y-enmascarado.md), [estado operativo](../../vault/operaciones/estado-operativo.md) (l. 34) | `active`; `GET /api/config/public` ya devuelve `language` sin sesión. | No hace falta endpoint nuevo: el idioma global llega por `usePublicConfig` (`frontend/src/config/api.ts`). |
| [ADR-009](../../vault/decisiones/adr-009-servicio-llm-con-proveedores-intercambiables.md) | El ADR-009 ya existe (servicio LLM). | La spec decía «ADR-009» para i18n: es **ADR-010**; corregido en la spec. |
| [Patrones de interfaz](../../vault/ingenieria/patrones-de-interfaz.md), [contrato API](../../vault/arquitectura/contrato-api-front-back.md) | `active`. | Se actualizan en T9 (convención «sin texto de UI fuera de los diccionarios»; `Accept-Language`). |
| `backend/app/config/model.py` (`LANGUAGES = {"es-ES": …}`), `routers/config.py` l. 58, `openapi/schemas.py` l. 581 | El idioma válido sale de `LANGUAGES`. | T1: añadir `en-US`. El valor persistido `es-ES` (FE015) sigue siendo válido. |
| `frontend/src/lib/format.ts` (`LOCALE = 'es-ES'`, formateadores creados al cargar el módulo), `downloads/labels.ts` l. 44 | Configuración regional fija. | T2: `setDisplayLocale()` (como `setDisplayTimeZone`) y formateadores en caché por locale. `AppLayout` ya remonta el contenido con `key` al cambiar la zona; se añade el idioma a esa `key`. |
| `layout/AppLayout.tsx`, `layout/navigation.ts` | Barra lateral con `label` y `description` fijos. | T2: el selector va junto al botón «Cerrar sesión»; `NAV_ITEMS` pasa a guardar claves. |
| `frontend/src/test/utils.tsx` | Utilidad común de render para los tests. | T2: envuelve con el proveedor i18n en `es` por defecto, de modo que los tests actuales no cambian (criterio 10). |
| Tamaño por carpeta (líneas, sin tests) | dashboards 723 · conversations 1010 · explorer 899 · search 414 · flows 2194 · downloads 766 · config 1352 · users 385 · pages/layout/components/auth ~520 | Reparto de T2–T7. |
| `backend/app` con ~67 `HTTPException`/`detail` y ~45 etiquetas | Textos en español. | Etiquetas de catálogo: por clave en el front (T4). Errores: `Accept-Language` en T8. |

## Decisiones de diseño

- **Diccionarios por área** en `frontend/src/i18n/` (`es/<area>.ts`, `en/<area>.ts`), objetos planos `clave → texto` con `{param}`. `es` define el tipo de claves; `en` debe cumplirlo (error de compilación). Así cada tarea añade su área sin tocar las demás.
- **Orden de resolución:** `localStorage` (`speech-analytics.language`, válido y presente en `languages`) → idioma global de `/api/config/public` → `es-ES`.
- **Plural:** `t(clave, { count })` con sufijos `_one`/`_other` solo donde haga falta.
- **Fuera de React** (etiquetas en `.ts`, p. ej. `conversations/labels.ts`): funciones que reciben `t` o devuelven la clave; no hay `t` global mutable salvo en `format.ts`, que ya es estado de módulo.

## Tareas

### T1 — Backend: `en-US` disponible
- **Qué:** `LANGUAGES` con `en-US` («English (United States)»); mensaje de validación y esquema OpenAPI/ejemplos con ambos idiomas.
- **Hecho cuando:** test de backend: `PUT /api/config/general` acepta `en-US` y lo devuelve en `/api/config` y `/api/config/public`; un idioma inválido da el error de validación existente; `languages` lista los dos. `./scripts/ci.sh` en verde.
- **Criterios de la spec:** 1, 13 (parte de `en-US`).
- **Depende de:** —

### T2 — Núcleo i18n, selector y esqueleto de la app
- **Qué:** `frontend/src/i18n/` (proveedor, `useI18n()`, `t`, detección, `localStorage` con try/catch, `<html lang>`); selector en la barra lateral con «Usar el idioma de la plataforma»; `format.ts` y `downloads/labels.ts` con locale activo; `AppLayout` remonta con el idioma; utilidad de tests con `es`. Migrar `layout/`, `pages/` (login, 403, 404), `auth/`, `components/` (~520 líneas). Test de paridad de claves y test de «sin español a mano» sobre las rutas migradas.
- **Hecho cuando:** tests de front de los criterios 2–6, 8 (login y navegación), 9 (`format.ts` con `es` y `en`) y 10 (toda la suite existente pasa sin tocar aserciones). Comprobado en navegador: login y navegación en `en`.
- **Criterios de la spec:** 2, 3, 4, 5, 6, 7, 9, 10.
- **Depende de:** T1.

### T3 — Dashboards y conversaciones
- **Qué:** `dashboards/` y `conversations/` (KPIs, gráficos, filtros, estados, badges, `labels.ts`, detalle, panel de análisis).
- **Hecho cuando:** test de render en `en` de dashboards, listado y detalle sin textos fijos en español; añadidas a la lista del test 7; suite en `es` intacta.
- **Criterios de la spec:** 7, 8, 9, 10.
- **Depende de:** T2.

### T4 — Explorador y búsqueda, con catálogo por clave
- **Qué:** `explorer/` y `search/`; operadores, campos y valores del catálogo del backend traducidos por clave con fallback a la etiqueta del backend.
- **Hecho cuando:** test en `en` de explorador y búsqueda; test con una clave de catálogo desconocida que muestra la etiqueta del backend.
- **Criterios de la spec:** 7, 8, 10, 11.
- **Depende de:** T2.

### T5 — Flujos de insights
- **Qué:** `flows/` (listado, editor, lienzo, nodos, panel de salida, ejecución, plantillas, categorías de nodos).
- **Hecho cuando:** test en `en` del listado y del editor de flujos; los nombres de flujo guardados por el usuario no se traducen.
- **Criterios de la spec:** 7, 8, 10.
- **Depende de:** T2.

### T6 — Descargas de Genesys y usuarios
- **Qué:** `downloads/` y `users/`, incluidos los mensajes de `users/errors.ts`.
- **Hecho cuando:** test en `en` de flujos de descarga, historial/ejecución y usuarios/roles; duraciones con locale activo.
- **Criterios de la spec:** 7, 8, 9, 10.
- **Depende de:** T2.

### T7 — Configuración
- **Qué:** `config/` (todas las pestañas, tarjeta de Genesys, auditoría, visor OpenAPI propio). «General» ofrece el idioma global con las dos opciones.
- **Hecho cuando:** test en `en` de cada pestaña; cambiar el idioma global en General se refleja en el login sin sesión (criterio 2); el contenido de Swagger UI no se traduce.
- **Criterios de la spec:** 2, 7, 8, 10.
- **Depende de:** T2.

### T8 — Mensajes del backend con `Accept-Language`
- **Qué:** el cliente HTTP (`frontend/src/api/client.ts`) envía `Accept-Language`; catálogo de mensajes en el backend (`app/i18n.py`) para los `detail` y errores de validación de configuración; lo no catalogado sigue en español; OpenAPI documenta la cabecera.
- **Hecho cuando:** tests de backend: un mensaje catalogado sale en `en` con `Accept-Language: en-US`, en `es` sin cabecera o con `es-ES`, y uno no catalogado sale en español; test de front: el cliente envía el idioma activo.
- **Atención:** `frontend/src/components/dataErrors.ts` reconoce el `503` de datos reales comparando el texto en español del mensaje; al traducir los mensajes debe pasar a reconocerlo por otra señal (código de error o `status` + ruta) o dejaría de mostrarse el aviso con `Accept-Language: en-US`. Hoy está excluido del test de «sin español a mano».
- **Criterios de la spec:** 12, 13.
- **Depende de:** T2. (Pendiente de confirmar con la persona usuaria; si prefiere dejarlos en español, se mueve a fuera de alcance.)

### T9 — Conocimiento y cierre
- **Qué:** `/vault capture`: ADR-010 (capa i18n propia y preferencia personal en el navegador), arquitectura y patrones de interfaz (convención de diccionarios y cómo añadir un idioma), contrato API (`Accept-Language`, `en-US`), estado operativo (idiomas disponibles) y entrega; el test de «sin español a mano» pasa a cubrir **todo** `frontend/src`; `VERIFY.md` con recorrido manual en navegador.
- **Hecho cuando:** `./scripts/ci.sh` y `python scripts/audit_vault.py` con código 0; índices del vault actualizados; criterio 15 comprobado en navegador (login, dashboards, detalle de conversación, configuración) en `es` y `en`.
- **Criterios de la spec:** 7, 14, 15.
- **Depende de:** T3–T8.

## Orden y paralelismo

`T1 → T2 → {T3, T4, T5, T6, T7, T8} → T9`. Tras T2 las seis tareas intermedias son independientes (cada una toca su carpeta y su archivo de diccionario); se recomienda el orden T3 → T4 → T7 → T5 → T6 → T8 por visibilidad.

## Conocimiento afectado (resumen)

| Entrada | Acción | Tarea |
|---|---|---|
| `vault/decisiones/adr-010-…` | Crear | T9 |
| `vault/ingenieria/patrones-de-interfaz.md` | Actualizar | T9 |
| `vault/arquitectura/arquitectura-de-la-plataforma.md` | Actualizar | T9 |
| `vault/arquitectura/contrato-api-front-back.md` | Actualizar | T9 |
| `vault/operaciones/estado-operativo.md` | Actualizar | T9 |
| `vault/entregas/` | Crear al hacer ship | T9 |

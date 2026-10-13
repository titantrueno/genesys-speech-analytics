# FE016 — Idioma inglés de la interfaz

> Estado: **spec pendiente de aprobación**. Amplía FE005 (que dejó «traducción de la UI a otros idiomas» fuera de alcance, `features/FE005-configuracion-de-la-plataforma/spec.md`).

## Objetivo

Permitir usar la interfaz (menús y textos fijos) en inglés además de en español, eligiéndolo en Configuración → General.

## Decisiones (ya tomadas con la persona usuaria)

| Pregunta | Decisión |
|---|---|
| ¿Cómo se elige? | **Solo** en el campo `language` de Configuración → General (hoy solo `es-ES`; se añade `en-US`, «English (United States)»). Es un ajuste de la plataforma: no hay selector en el login ni en el panel principal, ni elección personal por navegador (decisión de la persona usuaria, 2026-10-13). |
| ¿Qué se traduce? | Los menús y textos fijos de toda la interfaz del frontend (~6.400 líneas con textos en español, sin capa i18n). **No** se traduce el contenido: transcripciones, resúmenes, main topic, palabras clave y demás datos se muestran como llegan, en cualquier idioma de la interfaz. |
| ¿Cómo? | Capa i18n propia, sin dependencias nuevas: diccionarios `es` y `en` tipados, función `t(clave, params)` y proveedor React. |
| ¿Fechas y números? | Siguen el idioma activo (hoy fijos a `es-ES` en `frontend/src/lib/format.ts` y `frontend/src/downloads/labels.ts`). La zona horaria sigue siendo la de la configuración. |
| ¿Cómo se entrega? | Por fases (ver Alcance). |

## Criterios de aceptación

1. `GET /api/config/public` y `GET /api/config` aceptan `language: "en-US"`; `PUT` con un idioma fuera de `LANGUAGES` sigue devolviendo error de validación (test de backend). `LANGUAGES` expone `es-ES` y `en-US`.
2. La interfaz usa el idioma de la plataforma, incluido el login (sin sesión) (test de front con `/api/config/public` mockeado a `en-US`); un valor no soportado vuelve a español.
3. Guardar «English (United States)» en Configuración → General cambia los menús sin recargar; el login y el panel principal **no** tienen selector de idioma (test de front).
4. El atributo `<html lang>` refleja el idioma activo.
5. El texto de las conversaciones (transcripción, resumen, main topic, palabras clave) y demás datos no cambia con el idioma de la interfaz (test de front en las pantallas de datos, a partir de T3).
6. Los diccionarios `es` y `en` tienen exactamente las mismas claves y los mismos parámetros por clave (test que falla si falta, sobra o difiere alguna).
7. Ningún componente de las pantallas migradas contiene texto de UI en español escrito a mano: un test o regla de lint lo detecta sobre las rutas migradas (lista de pantallas migradas en el test, ampliable por fase).
8. Con `en`, cada pantalla migrada (login, navegación, dashboards, conversaciones, explorador, búsqueda, flujos, descargas, configuración, usuarios) no muestra textos fijos en español: test de render por pantalla que comprueba cabeceras y botones principales en inglés.
9. Fechas, horas, números, porcentajes y duraciones se formatean con la configuración regional del idioma activo (p. ej. `1.234,5` en `es`, `1,234.5` en `en`) y siguen respetando la zona horaria configurada (tests de `format.ts`).
10. Con el idioma `es` el comportamiento y los textos actuales no cambian: la suite de tests existente pasa sin modificar sus aserciones de texto.
11. Las etiquetas de catálogo que llegan del backend (operadores, campos y valores de consulta, estados) se muestran traducidas por clave en `en`; una clave sin traducción muestra la etiqueta del backend (test con clave desconocida).
12. El frontend envía `Accept-Language` con el idioma activo; los mensajes de error y validación del backend que están catalogados se devuelven en ese idioma y los no catalogados siguen en español (tests de backend por mensaje catalogado y por fallback).
13. La documentación OpenAPI refleja `en-US` y `Accept-Language` (extiende FE010).
14. `./scripts/ci.sh` termina con código 0 y `python scripts/audit_vault.py` también.
15. Verificación manual en navegador: cambiar entre `es` y `en` en login, dashboards, detalle de conversación y configuración.

## Conocimiento afectado

- Consultado: `vault/Home.md`; `vault/arquitectura/arquitectura-de-la-plataforma.md` (configuración pública con idioma, l. 105); `vault/decisiones/adr-007-configuracion-global-y-enmascarado.md` (config pública sin sesión); `vault/operaciones/estado-operativo.md` (l. 34); `features/FE005-configuracion-de-la-plataforma/spec.md` (l. 30 y 87: solo `es-ES`, traducción fuera de alcance); `features/FE015-persistencia-flujos-y-preferencias/spec.md` (el idioma global se persiste).
- Vacío: el vault no recoge ninguna convención de i18n.
- A actualizar: arquitectura (capa i18n del frontend), estado operativo (idiomas disponibles), `vault/ingenieria/` (convención: ningún texto de UI fuera de los diccionarios; cómo añadir un idioma).
- A crear: ADR-010 «Capa i18n propia; el idioma es un ajuste de la plataforma».

## Alcance

Fases, cada una entregable y verificable por separado:

1. **Infraestructura:** `en-US` en el backend, proveedor i18n, `t()`, idioma de la plataforma (o `es`), `<html lang>`, `format.ts` y `downloads/labels.ts` con la configuración regional activa, test de paridad de claves. Migración de login, navegación, cabecera y páginas de error.
2. **Dashboards y conversaciones** (incluye etiquetas de KPI, gráficos, estados y badges).
3. **Explorador y búsqueda** (incluye catálogo de operadores/campos del backend por clave).
4. **Flujos y descargas.**
5. **Configuración y usuarios** (incluye la tarjeta de Genesys y el visor OpenAPI propio, no el contenido de Swagger UI).
6. **Mensajes del backend** con `Accept-Language` y cierre (regla de lint, vault, ADR).

## Fuera de alcance

- Idiomas distintos de español e inglés (la capa los admite; añadirlos será otra feature).
- Idioma por persona o por navegador y selectores de idioma fuera de Configuración → General.
- Cambiar el idioma desde un rol sin `config:edit`: ese rol usa el idioma de la plataforma.
- Traducir datos de usuario o de negocio: transcripciones, resúmenes, main topics y palabras clave, nombres de flujos, taxonomía, checks, KPIs personalizados y el nombre de la plataforma.
- Traducir las salidas del LLM; el idioma de los análisis no cambia.
- Detectar el idioma del navegador (`navigator.language`).
- Textos de los logs, la auditoría almacenada y los documentos de `vault/`, `features/` y `README.md`.
- Pluralización avanzada y formatos ICU: solo sustitución de parámetros y dos formas (singular/plural) donde haga falta.
- Idiomas de derecha a izquierda.

## Riesgos / asunciones

- **Tamaño:** ~6.400 líneas de UI; es el riesgo principal. Mitigación: fases con criterios 7 y 8 por pantalla migrada; mientras una pantalla no esté migrada seguirá en español con `en` activo (aceptable solo entre fases, no en la entrega final).
- **Tests existentes** dependen de textos en español: se asume que `es` se conserva literal (criterio 10); migrar a claves exige que `es` reproduzca exactamente los textos actuales.
- **Mensajes del backend:** asumo que la fase 6 puede limitarse a los mensajes catalogados (los ~67 `detail`/`HTTPException` y mensajes de validación de configuración). Si la persona usuaria prefiere dejarlos en español, se mueve a fuera de alcance. **Por confirmar.**
- **Ajuste único:** todas las personas usuarias ven el mismo idioma; quien necesite otro depende de que un administrador lo cambie. Aceptado.
- **Texto mixto:** las etiquetas de usuario (taxonomía, checks) seguirán en español dentro de una interfaz inglesa; aceptado.
- Se asume que `language` persistido como `es-ES` (FE015) sigue siendo válido tras añadir `en-US`.

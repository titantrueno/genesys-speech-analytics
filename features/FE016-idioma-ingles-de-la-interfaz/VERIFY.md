# FE016 — Verificación

> Fase `/test`, 2026-10-13. Spec: [spec.md](spec.md). Plan: [plan.md](plan.md). Siguiente paso: `/review`.

## Evidencia

| Comprobación | Comando | Resultado |
|---|---|---|
| Gate completo | `./scripts/ci.sh` | Código **0** («CI local: OK») |
| Backend (sin PostgreSQL) | `pytest -m "not pg"`, con el dataset por defecto y con `DATA_SEED=7` | 1.159 passed, dos pasadas |
| Backend (PostgreSQL) | `REQUIRE_PG=1 pytest -m pg` | 192 passed |
| Frontend | `npm test`, `npm run lint`, `npm run build` | 571 tests en 45 archivos, lint y build correctos |
| OpenAPI | `scripts/export_openapi.py --check` y `openapi-spec-validator` | Al día y válido |
| Vault | `python scripts/audit_vault.py` | Código **0**: «57 archivos revisados, 0 errores» |
| Dependencias | `npm audit --audit-level=high`, `pip-audit` | Sin vulnerabilidades altas |

## Criterios de aceptación → evidencia

| # | Criterio | Dónde se comprueba |
|---|---|---|
| 1 | `en-US` válido, idioma inválido rechazado | `backend/tests/test_config_api.py` (`test_english_is_an_available_language_and_is_exposed_publicly`, `test_invalid_general_returns_one_error_per_field` con `fr-FR`) |
| 2 | Idioma de la plataforma, también sin sesión; valor no soportado → español | `frontend/src/i18n/Language.test.tsx` (login con `en-US`, `fr-FR`, sin configuración) |
| 3 | Guardar English en Configuración cambia los menús; sin selector en login ni panel | `Language.test.tsx` (`guardar English…`, `no hay selector…`, `volver a español…`) |
| 4 | `<html lang>` refleja el idioma | `Language.test.tsx` (en ambos sentidos) |
| 5 | Los datos no cambian | `i18n/EnglishScreens.test.tsx` (dashboards, listado, detalle, búsqueda), `flows/FlowsEnglish.test.tsx`, `config/ConfigEnglish.test.tsx`, `users/UsersEnglish.test.tsx`, `downloads/DownloadsEnglish.test.tsx` |
| 6 | Paridad de claves y parámetros | `i18n/dictionaries.test.ts` (y error de compilación si `en` no cumple las claves de `es`) |
| 7 | Sin español escrito a mano | `i18n/noHardcodedSpanish.test.ts`: ahora recorre **todo** `frontend/src` (120 archivos) salvo diccionarios, códigos de idioma y ayudantes de test |
| 8 | Cada pantalla en inglés | Los cinco archivos `*English.test.tsx` anteriores: login y navegación, dashboards, conversaciones, explorador, búsqueda, flujos, descargas, usuarios y las ocho pestañas de Configuración |
| 9 | Formatos por idioma y zona horaria | `i18n/format.test.ts` (nuevo), `Language.test.tsx` |
| 10 | `es` sin cambios | La suite previa (446 tests al empezar T3) pasa sin tocar ninguna aserción de texto; las únicas aserciones que cambiaron son las de mensajes de la API (T8) y la etiqueta «Idioma de la interfaz» (T7) |
| 11 | Catálogo por clave con respaldo | `EnglishScreens.test.tsx` (campo y operador desconocidos del explorador) |
| 12 | API solo en inglés | `backend/tests/test_api_messages_english.py` (análisis estático, mismo error con `es-ES`, `en-US` y `Accept-Language: es`) |
| 13 | OpenAPI en inglés | `test_api_messages_english.py` (descripciones del `openapi.yaml`, sin `Accept-Language`) y `test_openapi.py` (al día) |
| 14 | Gate y auditoría con código 0 | Tabla de evidencia |
| 15 | Verificación manual en navegador | Ver abajo |

## Verificación manual en navegador (criterio 15)

Entorno: `./scripts/dev.sh --no-db` con puertos propios (18000, 18001, 18002, 15173) y la variable `INGESTION_TOKEN` vacía, para que la configuración viva en memoria. Plataforma en `en-US` desde la API.

- Login (sesión nueva): campos y botón en inglés, sin selector (T2).
- Dashboards, listado y detalle de una conversación (T3): menús, KPIs, filtros, análisis y panel de Genesys en inglés; transcripción, resumen, main topic, palabras clave, checks y agentes tal cual.
- Explorador y búsqueda (T4), flujos de insights con una plantilla (T5), usuarios y roles (T6) y Configuración, General y KPIs (T7): en inglés.
- Las descargas de Genesys (T6) no se vieron en el navegador (sin servicio de ingesta); las cubren los tests de `downloads/`.
- Se paró cada servidor por PID; el proceso del puerto 8002 de la persona usuaria no se tocó.

## Grounding (fuentes oficiales)

- `Intl.PluralRules.select` devuelve una de `zero`, `one`, `two`, `few`, `many`, `other`, y `select(0)` en inglés da `"other"` ([MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/PluralRules/select)). La página no afirma que el inglés use solo `one` y `other`; esa asunción se comprobó con un test en tiempo de ejecución (`dictionaries.test.ts`: 0 → «conversations», 1 → «conversation», 2 → «conversations»).
- El atributo `lang` debe ser una etiqueta BCP 47 y una subetiqueta primaria sola (`en`, `es`) es válida; sin `lang` en un elemento, hereda del ancestro y en `<html>` declara el idioma de la página ([MDN · lang](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/lang)). Por eso `I18nProvider` pone `es` o `en`.
- `ast`: `col_offset` y `end_col_offset` son **desplazamientos en bytes UTF-8**, y cortar un `str` con ellos falla en líneas con tildes ([documentación de Python](https://docs.python.org/3/library/ast.html)). El script que sustituyó los textos del OpenAPI trabaja sobre bytes. Que los literales adyacentes sean un único `Constant` no lo afirma la página; se comprobó con el recuento (194 y 101 textos alineados con sus traducciones, validado por los fragmentos entre comillas invertidas).

## Rutina de duda

| Afirmación | Asunción | Duda | Evidencia |
|---|---|---|---|
| «Los tests detectan que se rompa el comportamiento» | Que un test en verde prueba algo | ¿Fallarían si se rompiera? | **Mutaciones** (cada una revertida): parámetro distinto en `en` → falla la paridad; español escrito a mano → falla el escáner; `<html lang>` sin actualizar → fallan 3 tests; `tOr` sin respaldo → falla; porcentaje sin seguir el idioma → falla; se ignora el idioma de la plataforma → fallan 4; mensaje de error en español en la API → falla; `en-US` retirado de `LANGUAGES` → falla; OpenAPI exportado con español → fallan 2 |
| «`es` no cambia» | Que traducir por claves reproduce el texto | Un texto con una tilde o una coma distinta pasaría desapercibido | La suite en español pasa sin modificar aserciones de texto (criterio 10); STOP |
| «La API solo habla inglés» | Que mis búsquedas cubren todos los mensajes | Una primera búsqueda por palabras se dejó «Credenciales incorrectas» | El test recorre el AST (excepciones, `detail=`, `message=`, `log`, listas de avisos); STOP con los 295 textos del OpenAPI alineados |
| «El gate es fiable» | Que un fallo es un fallo | Falló 3 veces con timeouts dispersos | Cada vez pasó sin tocar código tras esperar unos segundos; con 10 s de espera pasó a la primera. Anotado en el estado operativo; no es un fallo de FE016 |

## Bugs encontrados al verificar

| Bug | Causa raíz | Regresión |
|---|---|---|
| El primer gate de T8 fallaba en `test_flow_fields_pg` aunque el test aislado pasaba | Un mensaje `no tiene transcripción` en una aserción de un test `pg` que no corre sin PostgreSQL | `tests/test_flow_fields_pg.py` actualizado; `test_api_messages_english.py` cubre el código fuente de los mensajes |
| `ingestion/main.py` seguía devolviendo `"database": "no disponible"` | La traducción de `ingestion/api.py` no alcanzó al `health` de `main.py` | `tests/test_ingestion_service.py` espera `unavailable` |
| El test de «sin español a mano» no cubría `api/`, `lib/` ni rutas raíz | Lista de carpetas migradas ampliada fase a fase | Ahora recorre todo `frontend/src` |

## Casos límite añadidos en `/test`

- Volver a español desde Configuración restablece menús y `<html lang>` (`Language.test.tsx`).
- Plurales reales con 0, 1 y varios, en los dos idiomas (`dictionaries.test.ts`).
- Fechas en inglés respetando la zona horaria configurada (`format.test.ts`).

## Límites declarados

- Las descargas de Genesys no se probaron en el navegador.
- El texto del Output «informe» de un flujo sigue en español (se trató como contenido).
- Los mensajes de la API se ven en inglés con la interfaz en español (decisión de la persona usuaria).

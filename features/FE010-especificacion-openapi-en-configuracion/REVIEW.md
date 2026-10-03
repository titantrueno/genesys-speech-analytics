# FE010 — Revisión

> Fase `/review`. Fecha: 2026-10-03. Artefactos: [spec](spec.md) · [plan](plan.md) · [verificación](VERIFY.md). Siguiente paso: `/ship`.

## Resultado

**Aprobado.** No hay hallazgos critical ni major abiertos.

- **Resueltos en `/test`:** un minor de corrección (búsqueda, R3) y otro de mantenibilidad (versión fijada, R7).
- **Resueltos en esta revisión:** un minor de seguridad (R1) y un nit de corrección (R2), con sus tests en rojo antes del arreglo.
- **Aceptados de forma justificada:** cuatro minor y cuatro nit.

## Tamaño del cambio

El diff desde `c05d1af` (sin `package-lock.json`) ocupa 24 ficheros y unas 1.040 líneas. De ellas, unas 400 son de código y tests del front; el resto, spec, plan, verificación y vault. El backend no cambia. Supera las ~100 líneas recomendadas, pero se entregó en commits atómicos: spec y plan, T1–T6, `/test` y esta revisión. Cada tarea tiene su rojo a verde y sus mutaciones en el [plan](plan.md#progreso). `VERIFY.md` incluye la auditoría del vault en verde (código 0).

## Hallazgos

| # | Eje | Severidad | Hallazgo | Decisión |
|---|---|---|---|---|
| R1 | Seguridad | minor | `authInterceptor` añadía el token de la sesión a **cualquier** petición de Swagger. La [documentación](https://github.com/swagger-api/swagger-ui/blob/master/docs/usage/configuration.md) dice que el interceptor también ve las definiciones remotas (`$ref` externos) y OAuth. Hoy la especificación es propia y no tiene referencias externas, pero el token podía salir a otro origen (OWASP A01/A07) | **Resuelto**: solo se añade si la petición va al origen de la API (el de `VITE_API_URL` o el de la página). Test `solo envía el token a la API de la app, nunca a otro origen` (rojo antes del arreglo; la mutación que quita la comprobación lo rompe). Chrome en mismo origen (`:5173` → proxy) y en otro origen (`:5180` → `:8010`): `200` con token en los dos |
| R2 | Corrección | nit | Una cabecera `authorization` en minúsculas no se reconocía como «puesta con Authorize» y se añadía otra | **Resuelto**: comprobación sin distinguir mayúsculas; test `respeta la cabecera puesta con «Authorize» aunque cambie de mayúsculas` (rojo antes) |
| R3 | Corrección | minor | Buscar como lo pinta Swagger (`GET /api/users`) o con palabras de campos distintos no encontraba nada | **Resuelto en `/test`**: todas las palabras, en cualquier campo; tests y mutación (lección 33) |
| R4 | Seguridad | minor | El fragmento `curl` de «Try it out» muestra el token en claro | **Aceptado** (riesgo aceptado en la spec): es el token del propio usuario, ya visible en `sessionStorage`; autenticación mock ([ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md)). No se guarda en `localStorage` ni en la URL (test y Chrome) |
| R5 | Seguridad | — | Las descripciones de la especificación se pintan como Markdown | **Correcto**: la especificación sale del propio backend, y Swagger UI la sanea con DOMPurify (`sanitize(` en el bundle; `dompurify` 3.4.16 instalado). `queryConfigEnabled` sigue en `false`, así que la URL no puede cargar otra especificación (`?url=`) |
| R6 | Seguridad | — | «Try it out» permite escribir desde la UI | **Correcto**: cada llamada pasa por `require_permission`. `supervisor` recibe `403` al escribir (Chrome), y los recorridos `401`/`403` de `test_auth.py` cubren todas las rutas `/api`. `/openapi.json` ya era público; no se exponen rutas nuevas |
| R7 | Mantenibilidad | minor | El filtro depende de que `swagger-ui-react` recargue la prop `spec`, algo que su README niega | **Resuelto en `/test`**: versión fijada a `5.33.1`. Comprobado en el código instalado y en Chrome; plan B documentado (`key`). [ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md), lección 32 |
| R8 | Corrección | minor | Un `401` en «Try it out» (sesión caducada) no cierra la sesión de la app | **Aceptado**: fuera de alcance en la spec («integrar las respuestas de Probar con el estado de la app»). La app cierra la sesión en su siguiente petición propia |
| R9 | Seguridad | minor | `swagger-ui-react` arrastra `@scarf/scarf`, cuyo `postinstall` envía telemetría | **Aceptado**: npm lo bloquea hoy con `allowScripts`, y Swagger UI no lo necesita. Documentado en ADR-002 para que nadie lo apruebe por inercia |
| R10 | Simplicidad | nit | `persistAuthorization={false}` y `tryItOutEnabled={false}` coinciden con los valores por defecto | **Aceptado**: son explícitos a propósito. El criterio 13 los exige y un test los fija; así no dependen de un cambio de valores por defecto |
| R11 | Simplicidad | nit | `SpecLoading` vive en su propio fichero de 4 líneas | **Aceptado**: lo usan el `Suspense` de `ConfigPage` y `ApiTab`. Si estuviera en `ApiTab`, el *fallback* necesitaría el chunk que está esperando, y si estuviera en `ConfigPage`, el chunk diferido importaría la página |
| R12 | Corrección | nit | La pestaña «API» solo se pinta cuando `GET /api/config` ha cargado, porque comparte la guarda de la página | **Aceptado**: requiere el mismo permiso (`config:view`), y si la configuración falla, la página ya muestra su error. El criterio 4 (fallo de la especificación) se cumple |
| R13 | Rendimiento | nit | En desarrollo, `/openapi.json` se pide dos veces | **Aceptado**: es el doble montaje de `StrictMode`, solo en desarrollo. Después, `staleTime: Infinity` evita más peticiones |
| R14 | Rendimiento | — | Coste de la pestaña | **Correcto**: Swagger UI va en un chunk diferido (1,3 MB; 363 kB gzip) y la carga inicial no cambia (474,9 kB frente a 475,9 kB antes de FE010). Filtrar con la especificación real tarda de 13 a 178 ms hasta el repintado (Chrome; `useDeferredValue` + `useMemo`) |
| R15 | Adherencia a la spec | — | 17 de 17 criterios con evidencia (matriz en VERIFY). Se respeta el fuera de alcance: sin descarga, sin vista propia de esquemas, sin permiso nuevo y `/docs` sigue público | **Correcto**. Precisiones documentadas: la búsqueda incluye el dominio (criterio 8, ejemplo `usuarios`) y exige todas las palabras |
| R16 | Conocimiento | — | Contrato de la API (consumo y regla de origen del token), arquitectura (ocho pestañas), ADR-002 (dependencia, avisos, versión fijada, telemetría), lecciones 32–33, nota en la spec FE005 y READMEs del front y del back; auditoría del vault con código 0 | **Correcto** |

## Revisión por ejes

- **Corrección:**
  - ver R2, R3, R8 y R12;
  - 22 de 22 mutaciones del front detectadas (21 de `/test` y la de R1);
  - ningún test depende de Swagger en jsdom: el doble global (`test/swaggerStub.ts`) expone las props reales y la conducta se comprueba en Chrome.
- **Adherencia a la spec:** ver R15.
- **Simplicidad:**
  - ver R10 y R11;
  - sin abstracciones nuevas: la pestaña reutiliza `Tabs`, `useTabParam`, `ConfigField` e `input`;
  - el filtro es una función pura;
  - `useAudit(null)` evita una marca por pestaña.
- **Seguridad:** ver R1, R4, R5, R6 y R9. No hay secretos nuevos ni rutas nuevas; `npm audit` y `pip-audit`, sin vulnerabilidades.
- **Rendimiento:** ver R13 y R14.
- **Conocimiento:** ver R16.

## Evidencia de esta revisión

| Comando o prueba | Resultado |
|---|---|
| `cd frontend && npm test` | **329 passed** (2 tests nuevos de R1 y R2) |
| `./scripts/ci.sh` | Código 0 |
| `python3 scripts/audit_vault.py` | Código 0 |
| Chrome, mismo origen (`:5173`, proxy a un `:8000` ya en marcha; solo `GET`) | Filtrado en 19–94 ms; «Try it out» `GET /api/config` → `200` con token |
| Chrome, otro origen (`:5180` → `:8010`) | Filtrado en 13–178 ms; «Try it out» `GET /api/config` → `http://localhost:8010/api/config` `200` con token |

# FE010 — Verificación

> Fase `/test`. Fecha: 2026-10-03. Artefactos: [spec](spec.md) · [plan](plan.md). Siguiente paso: `/review`.

## Resultado

**Verde.** Los 17 criterios de aceptación tienen evidencia automatizada, en Chrome o en ambos. La verificación encontró un fallo real de usabilidad en la búsqueda y un comportamiento de la librería que la documentación no garantiza. Los dos están resueltos (ver «Bugs encontrados» y «Registro de duda»):

- buscar una operación tal como la muestra Swagger (`GET /api/users`) no devolvía nada;
- el filtro depende de que `swagger-ui-react` recargue la prop `spec`, cosa que su README niega; se fija la versión exacta.

## Evidencia

| Comando o prueba | Resultado |
|---|---|
| `cd frontend && npm test` | **327 passed** (28 ficheros). De FE010: 21 en `config/openapi/spec.test.ts` y 17 en `config/ApiTab.test.tsx`; `ConfigPage.test.tsx` adaptado a ocho pestañas |
| `cd backend && .venv/bin/pytest` | **728 passed**, y 728 con la segunda combinación del dataset (`ci.sh`). FE010 no toca el backend |
| `npm run lint` / `npm run build` | Código 0 / código 0. Swagger UI va en `ApiTab-*.js` (1.309 kB; 363 kB gzip) y `ApiTab-*.css` (184 kB). Vite avisa del tamaño del chunk; se acepta (ADR-002) |
| Carga inicial frente a `c05d1af` (antes de FE010) | 475,9 → 474,9 kB; gzip 141,8 → 141,1 kB. El código de Swagger no está ni en la entrada ni en las precargas (análisis con sourcemaps en el [plan](plan.md#t5--hecha-2026-10-03)) |
| Especificación embebida en `dist/` | 0 apariciones de marcadores propios (`Referencia ampliada`, `Sonda de salud`, `bancohorizonte`, `X-Auth-Version`, `/api/config/compliance-checks`) |
| `python3 scripts/audit_vault.py` | **Código 0**: 46 archivos, 0 errores |
| `npm audit` / `pip-audit` | 0 vulnerabilidades |
| `./scripts/ci.sh` | **Código 0** («CI local: OK») |
| `npm ci` limpio | Sin `--legacy-peer-deps` ni `--force`; dos avisos `ERESOLVE` aceptados (ADR-002) |
| Mutaciones (front) | **21 de 21 detectadas**: 10 de `spec.ts` (T2), 1 más de la búsqueda por palabras (`every` → `some`, 5 tests en rojo), 4 de la pestaña (T3), 3 de la búsqueda (T4) y 3 de «Probar» (T5) |
| Chrome, mismo origen (desarrollo y `vite preview`) | Ver «Recorrido en Chrome» |
| Chrome, otro origen (`VITE_API_URL=http://localhost:8010`, `CORS_ORIGINS=http://localhost:5180`, proxy apuntando a un puerto muerto) | `/openapi.json` pedido a `:8010`; 58 operaciones; «Try it out» `GET /api/config` → `http://localhost:8010/api/config` `200` con `Authorization`. Ninguna petición cae en el origen de la app |

### Recorrido en Chrome

Chrome headless (Playwright sobre el Chrome instalado), con la API real en `:8000` y la web en `:5173` (desarrollo) y `:4173` (`vite preview`). El detalle de cada paso está en el [plan, T6](plan.md#t6--hecha-2026-10-03).

1. **`admin`:**
   - abre «API» desde la lista de pestañas: 58 operaciones;
   - busca `connectors` y filtra por el dominio `config`: quedan 2;
   - «Try it out» `GET /api/config` → `200`, con el token;
   - «Try it out» `POST …/connectors/{id}/sync` → `200`, y la auditoría de `fuentes` suma una entrada `1AU` de «Admin Demo» sobre «Genesys Cloud · chat».
2. **`supervisor`:**
   - `?tab=api` muestra 58 operaciones;
   - `GET /api/config` → `200`;
   - `PUT /api/config/general` → `403`, que Swagger muestra en su tabla de respuestas.
3. **`analista`:** el menú no tiene Configuración, y `/configuracion?tab=api` muestra «Sin acceso» sin pedir `/openapi.json`.
4. **Aislamiento:**
   - recorrer dashboards y otras pestañas no pide nada de Swagger (0 peticiones);
   - desplegar una operación no cambia la URL;
   - `localStorage` queda vacío;
   - las capturas de Conversaciones antes y después de abrir «API» son idénticas. En General difieren 2 píxeles de iconos del menú, pero la misma diferencia aparece sin abrir «API» (4 de 4 pares), así que es ruido de hover y navegación.
5. **Búsqueda tras el arreglo** (especificación real):

   | Búsqueda | Operaciones |
   |---|---|
   | `GET /api/users` | 2 (`/api/users` y `/api/users/audit`) |
   | `borrar roles` | 1 |
   | `usuarios` | 8 |
   | `delete` | 5 |
   | `config:edit` | 11 |
6. **Consola:**
   - en producción, limpia con los tres roles (salvo el `403` de red esperado);
   - en desarrollo, «Try it out» provoca el aviso «Using UNSAFE_componentWillReceiveProps in strict mode», que viene de componentes de clase de Swagger UI. Es solo de `StrictMode` en desarrollo.

## Matriz de trazabilidad

| Criterio | Evidencia |
|---|---|
| 1. Octava pestaña «API» con `?tab=api` | `ApiTab.test.tsx`: `es la última pestaña…`, `al recargar con ?tab=api…`; `ConfigPage.test.tsx` (ocho pestañas y flechas); Chrome |
| 2. Acceso con `config:view` | `ApiTab.test.tsx`: `la ve supervisor`, `la ve un rol personalizado con config:view`, `analista/viewer no ve Configuración ni pide la especificación`; Chrome (`analista`) |
| 3. Sin auditoría | `no muestra ni pide el registro de auditoría` (mutaciones «auditoría visible» y «pedida con `null`» detectadas); Chrome (0 peticiones a `/api/config/audit`) |
| 4. Estados de carga y error | `muestra el estado de carga…`, `si falla la descarga avisa sin romper las demás pestañas` (mutación «sin estado de error» detectada) |
| 5. Fuente única, sin copia en el front | `ApiTab.test.tsx` (pide `/openapi.json`); `dist/` sin marcadores de la especificación; `tests/test_openapi.py` garantiza YAML = `app.openapi()` |
| 6. Título, versión y todas las operaciones por dominio | `pinta todas las operaciones…` (9 de 9 con el doble; mutación «especificación recortada» detectada); Chrome: 58 de 58, «versión 0.6.0» |
| 7. Detalle de cada operación | Chrome (descripción con el permiso, parámetros, respuestas, «Try it out»); los modelos se ven en la pestaña «Schema» de cada cuerpo, ya que la sección global está oculta (registro de duda) |
| 8. Búsqueda por ruta, método, resumen o descripción, sin mayúsculas ni tildes | `spec.test.ts`: 14 tests de `filterSpec` (ejemplos de la spec, «método ruta», varias palabras, caracteres especiales, sin dominios, tildes); `ApiTab.test.tsx`: `la búsqueda filtra…`; Chrome con la especificación real |
| 9. Filtro por dominio combinable; aviso sin coincidencias | `el selector de dominio…`, `sin coincidencias muestra un aviso…`; Chrome |
| 10. Token de la sesión sin «Authorize» | `spec.test.ts` (`authInterceptor`, 4 tests); `las llamadas llevan el token…`; Chrome en mismo origen y en otro origen |
| 11. Permisos del backend | Chrome: `supervisor` `PUT` → `403`; `admin` `GET` → `200`. Los recorridos `401`/`403` de `test_auth.py` siguen cubriendo todas las rutas `/api` |
| 12. Aviso y auditoría de lo hecho con «Probar» | `avisa de que «Probar» hace llamadas reales…`; Chrome (entrada `1AU` tras la sincronización) |
| 13. Token no persistido | `configura Swagger UI sin persistir…` (mutación detectada); `tras cerrar sesión ya no añade token`; Chrome (`localStorage` vacío) |
| 14. Carga diferida | Build (chunk propio; carga inicial sin cambios); Chrome (0 peticiones de Swagger antes de abrir la pestaña) |
| 15. Sin efectos en el resto de la app | `deepLinking: false` (test de props); Chrome (URL sin cambios; capturas); `swagger-ui.css` solo tiene un selector fuera de `.swagger-ui` (`html.dark-mode`, que no se usa) |
| 16. `ci.sh` en verde; instalación sin flags | `./scripts/ci.sh` código 0; `npm ci` sin flags |
| 17. Recorrido con tres roles, sin errores de consola | Recorrido en Chrome (arriba), con consola limpia en producción |

## Fundamentación

| Decisión | Fuente |
|---|---|
| `persistAuthorization: false`, `deepLinking: false`, `tryItOutEnabled: false`, `defaultModelsExpandDepth: -1` («set to -1 completely hide the models») | [Swagger UI — Configuration](https://github.com/swagger-api/swagger-ui/blob/master/docs/usage/configuration.md). Los valores por defecto se contrastaron en el bundle instalado (`swagger-ui-es-bundle-core.js` 5.33.1): `persistAuthorization:!1`, `deepLinking:!1`, `tryItOutEnabled:!1`, `defaultModelsExpandDepth:1`. Se pasan explícitos para no depender de ellos |
| `requestInterceptor` para el token («intercept remote definition, "Try it out", and OAuth 2.0 requests»; debe devolver la petición) | [Swagger UI — Configuration](https://github.com/swagger-api/swagger-ui/blob/master/docs/usage/configuration.md); `authInterceptor` devuelve la petición (test) |
| La URL de la app no puede reconfigurar Swagger (`?url=…`) | `queryConfigEnabled` vale `false` por defecto ([Configuration](https://github.com/swagger-api/swagger-ui/blob/master/docs/usage/configuration.md)) y la pestaña no lo activa |
| Pasar la especificación como objeto (`spec`) en lugar de `url` | [Configuration](https://github.com/swagger-api/swagger-ui/blob/master/docs/usage/configuration.md): «When used, the `url` parameter will not be parsed». Así el front controla carga, error y filtro |
| Qué props aplica `swagger-ui-react` y cuándo | [README de swagger-ui-react](https://github.com/swagger-api/swagger-ui/blob/master/flavors/swagger-ui-react/README.md) **y el código instalado** (`node_modules/swagger-ui-react/index.mjs`): todas las props se leen al montar; después solo se reaplican `spec` y `url`. Ver el registro de duda: el README y el código no coinciden |
| `vite preview` hereda el proxy | [Vite — Preview Options](https://vite.dev/config/preview-options): `preview.proxy`, «Default: `server.proxy`»; además, comprobado con `vite preview` |
| `React.lazy` + `Suspense` para el chunk diferido; `useDeferredValue` en la búsqueda | Patrón ya usado en `router.tsx` y en `users/UsersTab.tsx`; [React — lazy](https://react.dev/reference/react/lazy) y [React — useDeferredValue](https://react.dev/reference/react/useDeferredValue) |
| Licencia de la dependencia | `npm view swagger-ui-react license` → `Apache-2.0` ([LICENSE](https://github.com/swagger-api/swagger-ui/blob/master/LICENSE)) |

## Registro de duda

- **CLAIM:** al buscar o filtrar, Swagger UI muestra la especificación filtrada.
  **Asunción:** `swagger-ui-react` reaplica la prop `spec` cuando cambia.
  **Duda:** el README dice: «This prop is currently only applied once, on mount».
  **Reconciliación:** el código de la 5.33.1 instalada tiene un `useEffect` sobre `[system, spec]` que llama a `specActions.updateSpec(JSON.stringify(spec))`, y Chrome confirma el repintado (58 → 8 → 5 → 58). Como el comportamiento no está documentado, se fija `swagger-ui-react` a `5.33.1` exacto. Actualizarlo exige repetir la comprobación en Chrome ([ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md), [lección 32](../../vault/aprendizaje/lecciones-construccion-plataforma.md)). Plan B si deja de funcionar: `key` derivada del filtro para remontar.
  **STOP.**
- **CLAIM:** tras cerrar sesión, «Probar» ya no envía el token (criterio 13).
  **Asunción:** el interceptor se evalúa en cada petición.
  **Duda:** `swagger-ui-react` lee `requestInterceptor` solo al montar, aunque el README lo da por dinámico.
  **Reconciliación:** se monta una sola vez con una función estable de módulo (`authInterceptor`) que lee `tokenStorage` en cada llamada, no un token capturado. Además, cerrar sesión desmonta la página.
  **STOP.**
- **CLAIM:** la búsqueda encuentra lo que el usuario espera.
  **Asunción:** los ejemplos del criterio 8 (palabras sueltas) son representativos.
  **Duda:** ¿qué pasa si el usuario copia lo que ve en pantalla, «GET /api/users»?
  **Reconciliación:** no encontraba nada (bug 1). Ahora exige todas las palabras en cualquier campo.
  **STOP.**
- **CLAIM:** ocultar la sección «Schemas» no incumple el criterio 7 («los modelos referenciados»).
  **Duda:** ¿se pierden los modelos?
  **Reconciliación:** cada cuerpo y respuesta conserva su pestaña «Schema» con el modelo expandible (Chrome). La sección global era la que provocaba el error de orden de hooks con React 19, y una vista propia de esquemas ya estaba fuera de alcance.
  **STOP.**
- **CLAIM:** «Probar» llama a la misma API que la app en cualquier despliegue.
  **Asunción:** sin `servers`, Swagger usa el origen de la página; con `VITE_API_URL`, `withServer` la declara.
  **Duda:** en otro origen, ¿CORS deja pasar `/openapi.json` (fuera de `/api`) y las llamadas con `Authorization`?
  **Reconciliación:** `CORSMiddleware` envuelve toda la app, no solo `/api`. Probado en Chrome con el proxy apuntando a un puerto muerto: todo va a `:8010` y responde `200`.
  **STOP.**
- **CLAIM:** la pestaña no expone nada nuevo.
  **Asunción:** `/openapi.json` ya era público, y «Probar» pasa por `require_permission`.
  **Duda:** el fragmento `curl` de Swagger muestra el token en claro.
  **Reconciliación:** es el token del propio usuario, ya visible en `sessionStorage`. Es un riesgo aceptado en la spec ([ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md): autenticación mock). No se guarda en `localStorage` ni en la URL.
  **STOP.**
- **CLAIM:** la carga inicial no crece.
  **Duda:** el chunk de entrada pasó de 314 a 415 kB.
  **Reconciliación:** los sourcemaps muestran que Rollup movió `react-router` de un chunk compartido a la entrada. La suma de entrada y precargas es la misma (475,9 → 474,9 kB) y no incluye Swagger.
  **STOP.**

## Bugs encontrados

| Bug | Causa raíz | Regresión |
|---|---|---|
| Buscar una operación como la pinta Swagger (`GET /api/users`, `delete /api/roles`) o con palabras de campos distintos (`borrar roles`) no devolvía nada | `filterSpec` buscaba el texto entero, como una sola subcadena, en «ruta método resumen…». El orden era el contrario al de pantalla, y las palabras de campos distintos no podían coincidir | `encuentra una operación escrita como la muestra Swagger` y `con varias palabras exige todas…`: rojo antes del arreglo y verde después. La mutación `every` → `some` rompe 5 tests. [Lección 33](../../vault/aprendizaje/lecciones-construccion-plataforma.md) |

## Deuda encontrada (fuera de alcance)

- Los candados de Swagger se ven abiertos porque no se usa «Authorize», aunque el token se envía. El aviso de la pestaña lo explica («con tu sesión»).
- Un `401` en «Probar» (sesión caducada) se muestra en Swagger, pero no cierra la sesión de la app hasta su siguiente petición propia (fuera de alcance en la spec).
- En desarrollo, `StrictMode` muestra el aviso `UNSAFE_componentWillReceiveProps` de Swagger UI al usar «Try it out».

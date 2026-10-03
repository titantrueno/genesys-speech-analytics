# FE010 — Plan

> Fase `/plan`. Spec: [spec.md](spec.md), aprobada el 2026-10-03. Siguiente paso: `/build`, en orden.

## Contraste con el vault y el código

| Entrada o código | Estado | Impacto |
|---|---|---|
| `backend/app/main.py` | Sirve `/openapi.json`, `/docs` y `/redoc` sin sesión, fuera de `/api`; el esquema se construye una vez (`build_openapi`) | Sin cambios en el backend |
| `backend/openapi.yaml` y `tests/test_openapi.py` | El YAML se compara con `app.openapi()`; no hay `servers`, las rutas llevan `/api` | La especificación servida es la canónica (criterio 5) |
| `tests/test_auth.py` | Los recorridos de `401`/`403` solo cubren rutas que empiezan por `/api` | Servir la especificación fuera de `/api` no los toca |
| `frontend/vite.config.ts` | El proxy (y `vite preview`, que lo hereda) solo reenvía `/api` | T1: añadir `/openapi.json` |
| `frontend/src/api/client.ts` | `API_URL` (`VITE_API_URL` o `''`) y `tokenStorage` (sesión en `sessionStorage`) | Se reutilizan para la URL de la especificación y el token de «Probar» |
| `frontend/src/config/ConfigPage.tsx` | `TABS` con `render`; siempre pinta `AuditLog` y llama a `useAudit(current.code)` | T3: marca por pestaña para omitir la auditoría |
| `frontend/src/config/types.ts` | `SectionCode` se usa también en la auditoría y en los KPIs | La pestaña usa un tipo propio (`ConfigTabCode = SectionCode \| 'api'`) para no ensuciar `SectionCode` |
| npm `swagger-ui-react@5.33.1` | Peer deps `react >=16.8.0 <20`; ~7,5 MB desempaquetado | T1 confirma la instalación sin flags y el render con React 19 |
| [Contrato de la API](../../vault/arquitectura/contrato-api-front-back.md), [arquitectura](../../vault/arquitectura/arquitectura-de-la-plataforma.md), [ADR-002](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md), [ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md), [FE005](../FE005-configuracion-de-la-plataforma/spec.md) | Ver «Conocimiento afectado» de la spec | T6 |

## Decisiones de diseño

- **Cómo llega la especificación:** el proxy de Vite reenvía también `/openapi.json`, y el front la pide en `${API_URL}/openapi.json`. Con `VITE_API_URL` va directa a la API (CORS ya cubre todas las rutas). Se descarta una ruta nueva bajo `/api`: duplicaría la especificación y la obligaría a figurar en ella misma y en `PUBLIC_ROUTES`.
- **El front descarga la especificación, no Swagger UI:** una consulta de React Query (`useOpenApiSpec`) da los estados de carga y error (criterio 4), y Swagger UI recibe el objeto por la prop `spec`.
- **Búsqueda y filtro sobre la especificación, no dentro de Swagger:** controles propios (campo de texto y selector de dominio) y una función pura `filterSpec(spec, { text, tag })` que poda `paths` y `tags` antes de pasarla a Swagger UI. Normaliza mayúsculas y tildes y busca en ruta, método, `summary` y `description` (donde está el permiso). Es testeable sin Swagger y evita depender de la API de plugins (`fn.opsFilter`).
- **Servidor de «Probar»:** como la especificación no declara `servers`, `withServer(spec, API_URL)` añade `servers: [{ url: API_URL }]` solo si `API_URL` no está vacío. Sin él, Swagger usa el origen de la app y el proxy.
- **Token:** `requestInterceptor` lee `tokenStorage.get()` en cada petición y pone `Authorization: Bearer …`. Así, tras cerrar sesión, la siguiente llamada ya no lleva token. Configuración fija: `persistAuthorization: false`, `deepLinking: false` y `tryItOutEnabled: false` (el usuario pulsa «Try it out» a propósito).
- **Carga diferida:** `ApiTab` se importa con `React.lazy` desde `ConfigPage`; `ApiTab` importa `swagger-ui-react` y su CSS, así que ambos van en un chunk propio.
- **Aislamiento de estilos:** la CSS de Swagger se carga solo con la pestaña. Las reglas globales que contenga (T1 lo comprueba) se neutralizan o se acotan a `.swagger-ui` en `ApiTab`.
- **Tests:** en Vitest, `swagger-ui-react` se sustituye con `vi.mock` por un doble que pinta las operaciones de la prop `spec` y expone el `requestInterceptor`, para no cargar Swagger en jsdom. Swagger real se comprueba en Chrome.

## Tareas

| Id | Título | Depende de | Criterios de la spec |
|---|---|---|---|
| T1 | Dependencia, proxy y comprobación de compatibilidad | — | 5, 14 (parcial), 16 |
| T2 | Módulo `openapi` del front: descarga, filtro, servidor e interceptor | T1 | 5, 8, 9, 10, 13 |
| T3 | Pestaña «API» en Configuración (carga diferida, estados, sin auditoría) | T2 | 1, 2, 3, 4, 6, 7 |
| T4 | Búsqueda y filtro por dominio en la pestaña | T3 | 8, 9 |
| T5 | «Probar» con la sesión, aviso y aislamiento de estilos | T3 | 10, 11, 12, 13, 14, 15 |
| T6 | Conocimiento, documentación, gate y recorrido en Chrome | T1–T5 | 16, 17 y conocimiento afectado |

### T1 — Dependencia, proxy y compatibilidad

- **Qué:** `npm install swagger-ui-react` (y `@types` si los necesita); `/openapi.json` en el proxy de `vite.config.ts`; nota en `frontend/README.md`. Revisar `swagger-ui-react/swagger-ui.css` en busca de selectores globales (`html`, `body`, `*`, etiquetas sueltas) y anotarlos para T5.
- **Hecho cuando:** la instalación termina sin `--legacy-peer-deps` ni `--force` y sin avisos de peer deps; con la API y `npm run dev` arrancados, `curl localhost:5173/openapi.json` devuelve la especificación con 58 operaciones; un componente provisional con Swagger UI y la especificación real se pinta en Chrome sin errores de consola (se retira antes de cerrar la tarea). La lista de reglas globales queda en la sección Progreso.

### T2 — Módulo `openapi`

- **Qué:** `frontend/src/config/openapi/`: `useOpenApiSpec()` (React Query, `${API_URL}/openapi.json`, sin token), `filterSpec`, `countOperations`, `withServer` y `authInterceptor`.
- **Hecho cuando:** hay tests unitarios de:
  - `filterSpec` con los ejemplos del criterio 8 (`usuarios`, `delete`, `config:edit`), tildes y mayúsculas, combinación con `tag` y ninguna coincidencia;
  - `countOperations` antes y después de filtrar;
  - `withServer` con y sin `API_URL`;
  - `authInterceptor` con sesión (añade la cabecera) y sin ella (no la añade).

  Una mutación de cada función rompe al menos un test.

### T3 — Pestaña «API»

- **Qué:** `ApiTab` cargado con `lazy` + `Suspense`; entrada `api` en `TABS` con una marca que omite `AuditLog` y desactiva `useAudit`; tipo `ConfigTabCode`; textos «Cargando especificación…» y error con `role="alert"`; título y versión de la API.
- **Hecho cuando:** hay tests de front con el doble de Swagger que cubren:
  - la pestaña existe para `admin` y `supervisor` y persiste con `?tab=api`;
  - con un rol personalizado con `config:view` aparece, y sin él no hay Configuración;
  - con la pestaña abierta no se pide `/api/config/audit`;
  - los estados pendiente y fallido de `/openapi.json`;
  - el número de operaciones pintadas coincide con el de una especificación de ejemplo.

  Las demás pestañas y sus tests no cambian.

### T4 — Búsqueda y filtro

- **Qué:** campo de búsqueda y selector de dominio (con «Todos los dominios») encima del visor, conectados a `filterSpec`; mensaje «Ninguna operación coincide con la búsqueda» cuando no queda ninguna.
- **Hecho cuando:** tests de front: escribir `delete` deja solo operaciones `DELETE`; elegir un dominio y escribir texto aplica ambos; una búsqueda sin coincidencias muestra el mensaje y no pinta el visor.

### T5 — «Probar», aviso y aislamiento

- **Qué:** props de Swagger (`requestInterceptor`, `persistAuthorization: false`, `deepLinking: false`, `spec` con `withServer`); aviso visible sobre llamadas reales; neutralización de las reglas globales detectadas en T1.
- **Hecho cuando:**
  - un test con el doble comprueba las props, que el interceptor añade el token de la sesión y que tras `tokenStorage.clear()` deja de añadirlo, y que el aviso está en la pestaña;
  - `npm run build` deja Swagger UI y su CSS en un chunk que no importa el de entrada (comprobado en `dist/` y anotado en Progreso);
  - en Chrome, abrir la pestaña no cambia la URL al desplegar operaciones, y los dashboards, el listado y otra pestaña de Configuración se ven igual antes y después de abrirla.

### T6 — Conocimiento, gate y recorrido

- **Qué:** actualizar el contrato de la API, la arquitectura, ADR-002 (dependencia de Swagger UI y su carga diferida) y la nota de pestañas de FE005; README del front. ADR-003 solo se cita (sin cambios en permisos). Recorrido del criterio 17 en Chrome.
- **Hecho cuando:**
  - `./scripts/ci.sh` termina con código 0;
  - `python scripts/audit_vault.py` termina con código 0 y cada entrada cambiada lleva `updated: 2026-10-03`;
  - el recorrido con `admin`, `supervisor` y `analista` está anotado en `VERIFY.md` con el resultado de cada paso, incluido el `403` de `supervisor` y la entrada `1AU` creada desde «Probar»;
  - `grep -l "openapi: 3.1" dist/assets/*` no encuentra la especificación embebida en el bundle.

## Riesgos del plan

- **React 19 en tiempo de ejecución (T1):** el rango de peer deps no garantiza que funcione. Si falla, plan B: `swagger-ui` (sin React) montado en un `div` con `useEffect`, con las mismas props. T2 no depende de la elección.
- **`spec` actualizado en caliente (T4):** si `swagger-ui-react` no repinta al cambiar la prop `spec`, se fuerza el remontaje con `key` derivada del filtro. Se pierden las operaciones desplegadas al filtrar, y se acepta.
- **Tailwind preflight frente a Swagger (T5):** el reset de Tailwind puede deformar Swagger UI. Se corrige con estilos acotados a `.swagger-ui` dentro de la pestaña.
- **Tamaño del build (T5):** el chunk de Swagger superará el aviso de 500 kB de Vite. Se acepta por ir diferido. Si el aviso rompe `npm run build`, se ajusta `chunkSizeWarningLimit` solo para ese chunk, de forma justificada.

## Progreso

### T1 — hecha (2026-10-03)

- `swagger-ui-react@5.33.1` y `@types/swagger-ui-react@5.18.0` instalados; `npm ci` limpio termina sin `--legacy-peer-deps` ni `--force` (criterio 16).
- **Desviación:** el «hecho cuando» pedía cero avisos de peer deps, y `npm ci` emite dos `ERESOLVE overriding peer dependency`. Vienen de dependencias transitivas de Swagger UI que declaran React ≤18: `react-debounce-input@3.3.0` y `react-inspector@6.0.2`. npm las resuelve con React 19 sin flags y Swagger funciona (ver abajo). Se aceptan y no se fuerzan con `overrides`.
- Los scripts de instalación de las dependencias nuevas (entre ellos `@scarf/scarf`, telemetría de Swagger) no se ejecutan: los bloquea `allowScripts`. No hacen falta para el render.
- Proxy: `curl localhost:5173/openapi.json` → OpenAPI `3.1.0`, versión `0.6.0`, 58 operaciones.
- **CSS:** `swagger-ui.css` solo tiene un selector fuera de `.swagger-ui`, `html.dark-mode`, que no aplica porque la app no pone esa clase. No hay reglas globales que neutralizar en T5; queda por comprobar el efecto inverso (el preflight de Tailwind sobre Swagger).
- **Chrome** (página provisional, ya retirada, con `playwright-core` en el scratchpad):
  - Swagger pinta las 58 operaciones, el título, `0.6.0` y «OAS 3.1»;
  - desplegar una operación no cambia la URL.
- **Hallazgo:** la sección «Schemas» de Swagger (componente `models`) provoca en React 19 el aviso «React has detected a change in the order of Hooks». Con `defaultModelsExpandDepth: -1` (sección oculta) desaparece, y la consola queda limpia.
  - **Decisión para T5:** ocultar esa sección. Los modelos referenciados siguen viéndose en la pestaña «Schema» de cada cuerpo y respuesta (criterio 7), y una sección propia de esquemas ya estaba fuera de alcance.

### T2 — hecha (2026-10-03)

- `src/config/openapi/spec.ts`: `listOperations`, `countOperations`, `filterSpec`, `withServer` y `authInterceptor`. `src/config/openapi/api.ts`: `useOpenApiSpec` (sin token, `staleTime: Infinity`; sus estados se prueban en T3).
- **Precisión sobre el criterio 8:** la búsqueda incluye también el dominio (nombre y descripción del `tag`). Con la especificación real:
  - `usuarios` devuelve exactamente las 8 operaciones del dominio `users` (`/api/users*` y `/api/roles*`), porque varios resúmenes dicen «usuario» en singular;
  - `delete` devuelve los 5 `DELETE`;
  - `config:edit` devuelve sus 11 operaciones.
- **Tests:** 17 en `spec.test.ts`; 13 fallaban con el esqueleto sin lógica. Mutaciones detectadas (10 de 10):
  - quitar la normalización de tildes;
  - ignorar el dominio;
  - no buscar en el dominio;
  - no podar rutas vacías;
  - no podar dominios;
  - contar `parameters` como operación;
  - no quitar la barra final del servidor;
  - declarar siempre el servidor;
  - pisar la cabecera puesta con «Authorize»;
  - inventar un token sin sesión.

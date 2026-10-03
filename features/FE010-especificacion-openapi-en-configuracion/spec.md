# FE010 — Especificación OpenAPI en Configuración

> Estado: **aprobada** el 2026-10-03. Depende de FE005 (sección Configuración) y FE006 (permisos por rol), y del OpenAPI 3.1 completo de la API (commit `c05d1af`).

## Objetivo

Consultar y probar la especificación OpenAPI de la API desde la propia plataforma, en una pestaña nueva de Configuración, sin salir de la app ni abrir `/docs` aparte.

## Decisiones de la entrevista (2026-10-03)

- **Visor:** Swagger UI embebido en la pestaña (no un visor propio ni un iframe a `/docs`).
- **Acceso:** el mismo que el resto de Configuración (`config:view`); no se crea un permiso nuevo.
- **Funciones:** búsqueda y filtro de operaciones, y «Probar» (*Try it out*) con la sesión actual.
- **Descartado en esta feature:** descarga del YAML/JSON y una sección propia de esquemas (ver Fuera de alcance).

## Criterios de aceptación

### Pestaña

1. **Nueva pestaña:** Configuración (`/configuracion`) muestra una octava pestaña **«API»** después de «Modelos de IA». Su código es `api` y vive en la URL (`?tab=api`): recargar la página mantiene la pestaña (test de front).
2. **Acceso:** con los roles por defecto, `admin` y `supervisor` ven la pestaña; `analista` y `viewer` no ven Configuración, como hasta ahora (test por rol). Un rol personalizado con `config:view` la ve; sin él, no.
3. **Sin auditoría ni formulario:** la pestaña «API» no muestra el registro de auditoría ni pide `GET /api/config/audit` (test: ninguna petición a la auditoría con la pestaña abierta).
4. **Estados:** muestra «Cargando especificación…» mientras se descarga y un mensaje de error (`role="alert"`) si la descarga falla, sin romper las demás pestañas (tests con la petición pendiente y fallida).

### Contenido

5. **Fuente única:** la pestaña carga en tiempo de ejecución la especificación que sirve el backend arrancado (la misma que `backend/openapi.yaml`, ya garantizada por `tests/test_openapi.py`). No hay una copia del YAML en el front (test: el bundle no contiene el YAML; la pestaña hace una petición a la especificación).
6. **Completa:** muestra el título y la versión de la API (`info.version`) y todas las operaciones, agrupadas por dominio (`tags`). El número de operaciones que se pueden desplegar coincide con el de la especificación servida (test de front con una especificación de ejemplo; comprobación manual con la real: 58 operaciones).
7. **Detalle de cada operación:** al desplegarla se ven su descripción (incluido el permiso exigido), parámetros, cuerpo, respuestas y errores tal como están en la especificación, y los modelos referenciados.

### Búsqueda y filtro

8. **Búsqueda:** un campo de búsqueda filtra las operaciones por ruta, método, resumen o descripción, sin distinguir mayúsculas ni tildes. Ejemplos de test: `usuarios` → operaciones de `/api/users*`; `delete` → solo operaciones `DELETE`; `config:edit` → solo operaciones que lo exigen.
9. **Filtro por dominio:** un selector limita la vista a un dominio (`tag`); combinado con la búsqueda, se aplican ambos. Sin coincidencias se muestra «Ninguna operación coincide con la búsqueda» (test).

### Probar llamadas

10. **Sesión actual:** «Try it out» envía las peticiones a la misma API que usa la app con la cabecera `Authorization: Bearer <token>` de la sesión actual, sin que el usuario tenga que pulsar «Authorize» ni pegar el token (test: el interceptor añade la cabecera leída de la sesión).
11. **Permisos del backend:** las llamadas no saltan ningún permiso. Con `supervisor`, `PUT /api/config/general` responde `403` y Swagger muestra esa respuesta; con `admin`, `GET /api/config` responde `200` (comprobación en el recorrido de Chrome).
12. **Efectos reales y avisados:** la pestaña muestra un aviso visible de que «Probar» ejecuta llamadas reales contra la API en marcha y modifica su estado. Un cambio hecho con `admin` desde «Probar» queda en la auditoría `1AU` igual que uno hecho desde la UI (comprobación en Chrome).
13. **Token no persistido:** Swagger UI no guarda el token en `localStorage` ni lo pone en la URL (`persistAuthorization` desactivado; test de configuración). Al cerrar sesión, una llamada nueva desde la pestaña ya no lleva token.

### Rendimiento y aislamiento

14. **Carga diferida:** el código y la hoja de estilos de Swagger UI se descargan solo al abrir la pestaña «API», no al entrar en la app ni en otras pestañas de Configuración (comprobación sobre la salida de `npm run build`: Swagger UI va en un chunk propio que no importa el chunk de entrada; y en la pestaña Red de Chrome).
15. **Sin efectos en el resto de la app:** tras abrir la pestaña «API», el resto de secciones conservan su aspecto (recorrido de Chrome sobre dashboards, listado y otra pestaña de Configuración) y la URL de la app no cambia por la navegación interna de Swagger (sin *deep linking* en el hash).

### Calidad

16. `./scripts/ci.sh` termina con código 0. La dependencia nueva se instala sin `--legacy-peer-deps` ni `--force` con React 19.
17. Recorrido en Chrome contra la API real: con `admin`, abrir la pestaña, buscar, filtrar por dominio, desplegar una operación y probar `GET /api/config` y una escritura que aparezca en la auditoría; con `supervisor`, ver la pestaña y recibir `403` al probar una escritura; con `analista`, no ver Configuración. Sin errores de consola atribuibles a la feature.

## Conocimiento afectado

- [Contrato de la API entre front y back](../../vault/arquitectura/contrato-api-front-back.md): hoy dice que la especificación se sirve en `/openapi.json`, `/docs` y `/redoc` sin sesión; añadir que la consume la pestaña «API» de Configuración y desde qué módulo del front.
- [Arquitectura de la plataforma](../../vault/arquitectura/arquitectura-de-la-plataforma.md): añadir la pestaña «API» a la descripción de Configuración.
- [ADR-002 — Stack Vite, FastAPI y mock](../../vault/decisiones/adr-002-stack-vite-fastapi-mock.md): registrar la dependencia de Swagger UI en el front (o un ADR nuevo si `/plan` concluye que la decisión lo merece).
- [ADR-003 — Autenticación mock con permisos por rol](../../vault/decisiones/adr-003-auth-mock-por-roles.md): la pestaña reutiliza `config:view` y las llamadas de prueba siguen pasando por `require_permission`; no cambia la tabla de permisos.
- [FE005 — Configuración de la plataforma](../FE005-configuracion-de-la-plataforma/spec.md): la sección pasa de siete a ocho pestañas.
- [Registro de identificadores](../../vault/ingenieria/registro-de-identificadores.md): consultado; la feature no crea entidades ni prefijos nuevos.

## Alcance

- Pestaña «API» en Configuración con Swagger UI embebido, cargado de forma diferida.
- Carga de la especificación servida por el backend y, si hace falta, el ajuste mínimo para que el front la alcance (proxy de Vite o ruta bajo `/api`), a decidir en `/plan`.
- Búsqueda por texto y filtro por dominio.
- «Try it out» con el token de la sesión actual inyectado automáticamente.
- Tests de front, recorrido en Chrome y actualización del vault.

## Fuera de alcance

- Descargar la especificación en YAML o JSON desde la pestaña.
- Una sección propia de esquemas o un visor diseñado a medida.
- Cambiar el contenido de la especificación, las rutas o sus permisos (salvo la ruta para servirla al front, si `/plan` la necesita).
- Proteger con sesión `/openapi.json`, `/docs` o `/redoc`, que siguen públicos.
- Un permiso nuevo para ver la especificación.
- Integrar las respuestas de «Probar» con el estado de la app (por ejemplo, invalidar la caché de `GET /api/config` o cerrar la sesión ante un `401`): la app refleja esos cambios al recargar o en su siguiente petición.
- Modo oscuro o rediseño visual de Swagger UI más allá de encajarlo en la pestaña.

## Riesgos y asunciones

- **Hecho:** el backend ya sirve la especificación en `/openapi.json`, `/docs` y `/redoc` sin sesión, y sus rutas llevan el prefijo `/api` sin `servers` declarados ([contrato](../../vault/arquitectura/contrato-api-front-back.md)).
- **Riesgo:** el proxy de Vite solo reenvía `/api`, así que `/openapi.json` no llega al front en desarrollo. Hay que elegir en `/plan` entre ampliar el proxy (y su equivalente con `VITE_API_URL`) o servir la especificación bajo `/api` sin romper el test que exige `401` en toda ruta no pública.
- **Riesgo:** `swagger-ui-react` es pesado (del orden de 1 MB) y puede declarar dependencias peer incompatibles con React 19. Se mitiga con la carga diferida (criterio 14); si no es compatible, se valora montar `swagger-ui` (sin React) en un contenedor. Hay que comprobarlo antes de `/build`.
- **Riesgo:** la hoja de estilos de Swagger UI incluye reglas globales que podrían alterar la app (criterio 15). Se mitiga acotándola al contenedor si hace falta.
- **Riesgo:** «Probar» con `admin` modifica el estado real en memoria (usuarios, roles, configuración) y puede dejar la demo en un estado inesperado. Se acepta con el aviso del criterio 12; el estado se recupera reiniciando el backend.
- **Riesgo aceptado:** el fragmento `curl` que muestra Swagger tras probar incluye el token de la sesión actual en claro. Es el token del propio usuario, de una autenticación mock ([ADR-003](../../vault/decisiones/adr-003-auth-mock-por-roles.md)).
- **Asunción:** Swagger UI renderiza OpenAPI 3.1 sin errores de validación con la especificación actual (se verifica en el recorrido de Chrome).
- **Asunción:** el filtro nativo de Swagger UI solo busca por `tag`; la búsqueda por ruta, método y descripción (criterio 8) requiere un plugin propio de filtrado.
- **Hipótesis:** la pestaña «API» encaja en el patrón de `TABS` de `ConfigPage` con un ajuste para omitir la auditoría y la dependencia de `GET /api/config`. Hay que comprobarlo en `/plan`.

# Frontend · Speech & Text Analytics

SPA con Vite, React 19, TypeScript, Tailwind CSS 4, React Router, TanStack Query y Recharts.

## Arranque

```bash
npm install
npm run dev        # http://localhost:5173
```

En desarrollo (y con `vite preview`), Vite reenvía `/api` y `/openapi.json` (pestaña «API» de Configuración) a `http://localhost:8000` (configurable con `API_PROXY_TARGET`). Para apuntar a otra API sin proxy, define `VITE_API_URL` (ver `.env.example`) y añade el origen del front a `CORS_ORIGINS` en el backend.

## Scripts

| Comando | Uso |
|---|---|
| `npm test` | Tests de componente (Vitest + Testing Library). |
| `npm run lint` | oxlint. |
| `npm run build` | Comprobación de tipos y build de producción. |

## Estructura

```text
src/
  api/            # cliente HTTP, hooks de TanStack Query
  auth/           # contexto de sesión, guards de ruta, permisos (se recargan si cambia X-Auth-Version)
  layout/         # layout con navegación por permisos
  dashboards/     # dashboards, filtros en URL, drill-down, gráficos
  conversations/  # listado, detalle tipo chat (abre en ?turn=N), panel de análisis, useRowNavigation
  explorer/       # explorador de queries asistidas (constructor, lenguaje natural, consultas guardadas)
  search/         # búsqueda semántica, resultados por fragmento y conversaciones similares
  flows/          # flujos de insights: listado, editor con React Flow, paneles por nodo, ejecución e historial
  downloads/      # flujos de descarga de Genesys (FE011): formulario, ejecución con log en vivo, historial y conector
  config/         # configuración: ocho pestañas, errores por campo, confirmación en fila y registro de cambios;
                  #   openapi/ y tabs/ApiTab.tsx: especificación de la API con Swagger UI (diferido; en tests, test/swaggerStub.ts)
  users/          # usuarios y roles: listado con filtros, alta y edición, roles y matriz de permisos
  components/     # piezas compartidas (pestañas en la URL, selector múltiple)
  lib/            # formato (todas las fechas, en la zona horaria de la plataforma) y resaltado
  pages/          # login, sin acceso, no encontrado
  router.tsx      # rutas (dashboard, flujos, configuración y usuarios se cargan en diferido)
```

Convenciones: filtros en la URL; drill-down con el filtro del numerador de cada KPI (`dashboards/drilldown.ts`); filas de tabla y tarjetas de resultado navegables con `useRowNavigation`, según `vault/ingenieria/patrones-de-interfaz.md`; paleta de gráficos validada (`--series-*` en `index.css`).

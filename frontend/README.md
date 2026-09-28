# Frontend · Speech & Text Analytics

SPA con Vite, React 19, TypeScript, Tailwind CSS 4, React Router, TanStack Query y Recharts.

## Arranque

```bash
npm install
npm run dev        # http://localhost:5173
```

En desarrollo, Vite reenvía `/api` a `http://localhost:8000` (configurable con `API_PROXY_TARGET`). Para apuntar a otra API sin proxy, define `VITE_API_URL` (ver `.env.example`) y añade el origen del front a `CORS_ORIGINS` en el backend.

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
  auth/           # contexto de sesión, guards de ruta, permisos
  layout/         # layout con navegación por permisos
  dashboards/     # dashboards, filtros en URL, drill-down, gráficos
  conversations/  # listado, detalle tipo chat (abre en ?turn=N), panel de análisis, useRowNavigation
  explorer/       # explorador de queries asistidas (constructor, lenguaje natural, consultas guardadas)
  search/         # búsqueda semántica, resultados por fragmento y conversaciones similares
  flows/          # flujos de insights: listado, editor con React Flow, paneles por nodo, ejecución e historial
  lib/            # formato y resaltado
  pages/          # login, sin acceso, próximamente
  router.tsx      # rutas (dashboard y flujos se cargan en diferido)
```

Convenciones: filtros en la URL; drill-down con el filtro del numerador de cada KPI (`dashboards/drilldown.ts`); filas de tabla y tarjetas de resultado navegables con `useRowNavigation`, según `vault/ingenieria/patrones-de-interfaz.md`; paleta de gráficos validada (`--series-*` en `index.css`).

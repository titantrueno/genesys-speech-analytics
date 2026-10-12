import { createBrowserRouter, createMemoryRouter, Outlet, type RouteObject } from 'react-router'
import { RequireAuth, RequirePermission } from './auth/guards'
import { AppLayout } from './layout/AppLayout'
import { NAV_ITEMS, type NavItem } from './layout/navigation'
import { HomeRedirect } from './pages/HomeRedirect'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { DashboardsIndex } from './dashboards/DashboardsIndex'
import { LoadingScreen } from './layout/LoadingScreen'
import { ConversationsPage } from './conversations/ConversationsPage'
import { ConversationDetailPage } from './conversations/ConversationDetailPage'
import { ExplorerPage } from './explorer/ExplorerPage'
import { SearchPage } from './search/SearchPage'
import { FlowsPage } from './flows/FlowsPage'

export type AppRouter = ReturnType<typeof createBrowserRouter>

const SECTION_ROUTES: Record<string, RouteObject[]> = {
  '/dashboards': [
    { index: true, element: <DashboardsIndex /> },
    {
      path: ':dashboardId',
      HydrateFallback: LoadingScreen,
      lazy: async () => ({ Component: (await import('./dashboards/DashboardsPage')).DashboardsPage }),
    },
  ],
  '/conversaciones': [
    { index: true, element: <ConversationsPage /> },
    { path: ':conversationId', element: <ConversationDetailPage /> },
  ],
  '/explorador': [
    { index: true, element: <ExplorerPage /> },
  ],
  '/busqueda': [
    { index: true, element: <SearchPage /> },
  ],
  '/configuracion': [
    {
      index: true,
      HydrateFallback: LoadingScreen,
      lazy: async () => ({ Component: (await import('./config/ConfigPage')).ConfigPage }),
    },
  ],
  '/usuarios': [
    {
      index: true,
      HydrateFallback: LoadingScreen,
      lazy: async () => ({ Component: (await import('./users/UsersPage')).UsersPage }),
    },
  ],
  '/flujos': [
    { index: true, element: <FlowsPage /> },
    {
      // React Flow solo se descarga al abrir un flujo.
      path: ':flowId',
      HydrateFallback: LoadingScreen,
      lazy: async () => ({ Component: (await import('./flows/FlowEditorPage')).FlowEditorPage }),
    },
    {
      // Flujos de descarga de Genesys (FE011): formulario, sin React Flow.
      path: 'descargas/:flowId',
      HydrateFallback: LoadingScreen,
      lazy: async () => ({ Component: (await import('./downloads/DownloadFlowPage')).DownloadFlowPage }),
    },
    {
      path: ':flowId/ejecuciones',
      HydrateFallback: LoadingScreen,
      lazy: async () => ({ Component: (await import('./flows/RunPage')).RunsPage }),
    },
    {
      path: ':flowId/ejecuciones/:runId',
      HydrateFallback: LoadingScreen,
      lazy: async () => ({ Component: (await import('./flows/RunPage')).RunPage }),
    },
  ],
}

function sectionRoute(item: NavItem): RouteObject {
  return {
    path: item.path.slice(1),
    element: (
      <RequirePermission permission={item.permission}>
        <Outlet />
      </RequirePermission>
    ),
    children: SECTION_ROUTES[item.path],
  }
}

export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <RequireAuth><AppLayout /></RequireAuth>,
    children: [
      { index: true, element: <HomeRedirect /> },
      ...NAV_ITEMS.map(sectionRoute),
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export function createAppRouter(options?: { initialEntries: string[] }): AppRouter {
  return options ? createMemoryRouter(routes, options) : createBrowserRouter(routes)
}

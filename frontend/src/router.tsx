import { createBrowserRouter, createMemoryRouter, Outlet, type RouteObject } from 'react-router'
import { RequireAuth, RequirePermission } from './auth/guards'
import { AppLayout } from './layout/AppLayout'
import { NAV_ITEMS, type NavItem } from './layout/navigation'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { HomeRedirect } from './pages/HomeRedirect'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { DashboardsIndex, DashboardsPage } from './dashboards/DashboardsPage'

export type AppRouter = ReturnType<typeof createBrowserRouter>

const SECTION_ROUTES: Record<string, RouteObject[]> = {
  '/dashboards': [
    { index: true, element: <DashboardsIndex /> },
    { path: ':dashboardId', element: <DashboardsPage /> },
  ],
}

function sectionRoute(item: NavItem): RouteObject {
  return {
    path: item.path.slice(1),
    element: (
      <RequirePermission permission={item.permission}>
        {SECTION_ROUTES[item.path] ? <Outlet /> : <ComingSoonPage item={item} />}
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

import type { ReactElement } from 'react'
import { createBrowserRouter, createMemoryRouter, type RouteObject } from 'react-router'
import { RequireAuth, RequirePermission } from './auth/guards'
import { AppLayout } from './layout/AppLayout'
import { NAV_ITEMS, type NavItem } from './layout/navigation'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { HomeRedirect } from './pages/HomeRedirect'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'

export type AppRouter = ReturnType<typeof createBrowserRouter>

const SECTION_PAGES: Record<string, ReactElement> = {}

function sectionRoute(item: NavItem): RouteObject {
  return {
    path: item.path.slice(1),
    element: (
      <RequirePermission permission={item.permission}>
        {SECTION_PAGES[item.path] ?? <ComingSoonPage item={item} />}
      </RequirePermission>
    ),
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

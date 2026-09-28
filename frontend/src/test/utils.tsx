import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { AppProviders } from '../App'
import { createAppRouter } from '../router'
import type { Permission, User } from '../auth/types'

export const ALL_PERMISSIONS: Permission[] = [
  'dashboards:view', 'conversations:view', 'explorer:use', 'search:use',
  'flows:view', 'flows:edit', 'config:view', 'config:edit', 'users:admin',
]

export const USERS: Record<'admin' | 'viewer' | 'analista' | 'lector', User> = {
  admin: { id: '1US-00000001-0000-5000-8000-000000000001', name: 'Admin Demo', email: 'admin@bancohorizonte.demo', role: 'admin', permissions: ALL_PERMISSIONS },
  viewer: { id: '1US-00000002-0000-5000-8000-000000000002', name: 'Viewer Demo', email: 'viewer@bancohorizonte.demo', role: 'viewer', permissions: ['dashboards:view', 'conversations:view'] },
  analista: {
    id: '1US-00000003-0000-5000-8000-000000000003', name: 'Analista Demo', email: 'analista@bancohorizonte.demo', role: 'analista',
    permissions: ['dashboards:view', 'conversations:view', 'explorer:use', 'search:use', 'flows:view', 'flows:edit'],
  },
  // Rol que solo puede ver flujos (FE004); con los roles por defecto no existe, FE006 permitirá crearlo.
  lector: {
    id: '1US-00000004-0000-5000-8000-000000000004', name: 'Lectora Demo', email: 'lectora@bancohorizonte.demo', role: 'lector_flujos',
    permissions: ['flows:view'],
  },
}

type Reply = { status: number; body?: unknown }
type Handler = (init: RequestInit & { url: string }) => Reply | Promise<Reply>

export function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input)
    const key = `${init.method ?? 'GET'} ${new URL(url, 'http://localhost').pathname}`
    const handler = routes[key]
    if (!handler) return new Response(JSON.stringify({ detail: `sin mock: ${key}` }), { status: 404 })
    const { status, body } = await handler({ ...init, url })
    return new Response(body === undefined ? null : JSON.stringify(body), {
      status, headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function signedInAs(user: User, extraRoutes: Record<string, Handler> = {}) {
  sessionStorage.setItem('sta.token', `token-${user.id}`)
  return mockApi({ 'GET /api/auth/me': () => ({ status: 200, body: user }), ...extraRoutes })
}

export function renderApp(path: string) {
  const router = createAppRouter({ initialEntries: [path] })
  return { router, ...render(<AppProviders router={router} />) }
}

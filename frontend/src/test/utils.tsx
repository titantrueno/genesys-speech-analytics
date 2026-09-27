import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { AppProviders } from '../App'
import { createAppRouter } from '../router'
import type { Permission, User } from '../auth/types'

export const ALL_PERMISSIONS: Permission[] = [
  'dashboards:view', 'conversations:view', 'explorer:use', 'search:use',
  'flows:view', 'flows:edit', 'config:view', 'config:edit', 'users:admin',
]

export const USERS: Record<'admin' | 'viewer' | 'analista', User> = {
  admin: { id: 'u-admin', name: 'Admin Demo', email: 'admin@bancohorizonte.demo', role: 'admin', permissions: ALL_PERMISSIONS },
  viewer: { id: 'u-viewer', name: 'Viewer Demo', email: 'viewer@bancohorizonte.demo', role: 'viewer', permissions: ['dashboards:view', 'conversations:view'] },
  analista: {
    id: 'u-analista', name: 'Analista Demo', email: 'analista@bancohorizonte.demo', role: 'analista',
    permissions: ['dashboards:view', 'conversations:view', 'explorer:use', 'search:use', 'flows:view', 'flows:edit'],
  },
}

type Handler = (init: RequestInit & { url: string }) => { status: number; body?: unknown }

export function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input)
    const key = `${init.method ?? 'GET'} ${new URL(url, 'http://localhost').pathname}`
    const handler = routes[key]
    if (!handler) return new Response(JSON.stringify({ detail: `sin mock: ${key}` }), { status: 404 })
    const { status, body } = handler({ ...init, url })
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

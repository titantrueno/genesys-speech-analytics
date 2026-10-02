import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from './types'

const VERSION = 'X-Auth-Version'

/** La analista navega; entre medias, un administrador le retira la búsqueda semántica (FE006, criterio 6). */
function setup(options: { changeVersion: boolean }) {
  let version = '7'
  let me: User = USERS.analista
  const reply = (body: unknown) => ({ status: 200, body, headers: { [VERSION]: version } })
  const fetchMock = signedInAs(USERS.analista, {
    'GET /api/auth/me': () => reply(me),
    'GET /api/conversations': () => reply({ items: [], total: 0, page: 1, page_size: 25 }),
  })
  const revoke = () => {
    me = { ...USERS.analista, permissions: USERS.analista.permissions.filter((p) => p !== 'search:use') }
    if (options.changeVersion) version = '8'
  }
  const meCalls = () => fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/api/auth/me')).length
  return { revoke, meCalls, ...renderApp('/busqueda') }
}

const navLabels = () => within(screen.getByRole('navigation', { name: /principal/i })).getAllByRole('link').map((l) => l.textContent)

describe('Permisos actualizados en la siguiente petición', () => {
  it('si cambia la versión de usuarios y roles, recarga el usuario: el menú pierde la sección y la página muestra "Sin acceso"', async () => {
    const { revoke, router } = setup({ changeVersion: true })
    await waitFor(() => expect(navLabels()).toContain('Búsqueda semántica'))
    revoke()
    await router.navigate('/conversaciones')
    await waitFor(() => expect(navLabels()).not.toContain('Búsqueda semántica'))
    await router.navigate('/busqueda')
    expect(await screen.findByRole('heading', { name: /sin acceso/i })).toBeInTheDocument()
  })

  it('sin cambio de versión no vuelve a pedir el usuario', async () => {
    const { revoke, router, meCalls } = setup({ changeVersion: false })
    await waitFor(() => expect(navLabels()).toContain('Búsqueda semántica'))
    revoke()
    await router.navigate('/conversaciones')
    await screen.findByRole('heading', { name: 'Conversaciones' })
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(meCalls()).toBe(1)
    expect(navLabels()).toContain('Búsqueda semántica')
  })

  it('la barra lateral muestra el nombre del rol, también de uno personalizado', async () => {
    signedInAs(USERS.lector)
    renderApp('/flujos')
    expect(await screen.findByText('Lector de flujos')).toBeInTheDocument()
  })
})

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp, signedInAs, USERS } from './test/utils'

const SECTIONS = ['Dashboards', 'Conversaciones', 'Explorador', 'Búsqueda semántica', 'Flujos de insights', 'Configuración', 'Usuarios y roles']

async function fillLogin(email: string, password: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText(/email/i), email)
  await user.type(screen.getByLabelText(/contraseña/i), password)
  await user.click(screen.getByRole('button', { name: /entrar/i }))
}

describe('login', () => {
  it('con credenciales válidas guarda el token y entra en la primera sección permitida', async () => {
    const fetchMock = mockApi({
      'POST /api/auth/login': () => ({ status: 200, body: { access_token: 'tok-123', token_type: 'bearer', user: USERS.analista } }),
    })
    const { router } = renderApp('/login')
    await fillLogin('analista@bancohorizonte.demo', 'demo')

    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboards'))
    expect(await screen.findByText('Analista Demo')).toBeInTheDocument()
    expect(sessionStorage.getItem('sta.token')).toBe('tok-123')
    const [, init] = fetchMock.mock.calls[0]
    expect(JSON.parse(String(init?.body))).toEqual({ email: 'analista@bancohorizonte.demo', password: 'demo' })
  })

  it('con credenciales inválidas muestra el error y no navega', async () => {
    mockApi({ 'POST /api/auth/login': () => ({ status: 401, body: { detail: 'Credenciales incorrectas' } }) })
    const { router } = renderApp('/login')
    await fillLogin('admin@bancohorizonte.demo', 'mala')

    expect(await screen.findByRole('alert')).toHaveTextContent(/credenciales incorrectas/i)
    expect(router.state.location.pathname).toBe('/login')
    expect(sessionStorage.getItem('sta.token')).toBeNull()
  })
})

describe('rutas protegidas', () => {
  it('sin sesión redirige al login y tras entrar vuelve a la ruta pedida', async () => {
    mockApi({
      'POST /api/auth/login': () => ({ status: 200, body: { access_token: 'tok', token_type: 'bearer', user: USERS.viewer } }),
    })
    const { router } = renderApp('/conversaciones')
    expect(await screen.findByRole('button', { name: /entrar/i })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')

    await fillLogin('viewer@bancohorizonte.demo', 'demo')
    await waitFor(() => expect(router.state.location.pathname).toBe('/conversaciones'))
  })

  it('restaura la sesión guardada y envía el token Bearer', async () => {
    const fetchMock = signedInAs(USERS.admin)
    renderApp('/dashboards')
    expect(await screen.findByText('Admin Demo')).toBeInTheDocument()
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers)
    expect(headers.get('Authorization')).toBe('Bearer token-u-admin')
  })

  it('un token rechazado por la API cierra la sesión y vuelve al login', async () => {
    sessionStorage.setItem('sta.token', 'caducado')
    mockApi({ 'GET /api/auth/me': () => ({ status: 401, body: { detail: 'Token caducado' } }) })
    const { router } = renderApp('/dashboards')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(sessionStorage.getItem('sta.token')).toBeNull()
  })

  it('cerrar sesión borra el token y vuelve al login', async () => {
    signedInAs(USERS.viewer)
    const { router } = renderApp('/dashboards')
    await userEvent.setup().click(await screen.findByRole('button', { name: /cerrar sesión/i }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(sessionStorage.getItem('sta.token')).toBeNull()
  })
})

describe('navegación por permisos', () => {
  it('admin ve las siete secciones', async () => {
    signedInAs(USERS.admin)
    renderApp('/dashboards')
    const nav = await screen.findByRole('navigation', { name: /principal/i })
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual(SECTIONS)
  })

  it('viewer no ve Configuración ni Usuarios y roles', async () => {
    signedInAs(USERS.viewer)
    renderApp('/dashboards')
    const nav = await screen.findByRole('navigation', { name: /principal/i })
    const labels = within(nav).getAllByRole('link').map((l) => l.textContent)
    expect(labels).toEqual(['Dashboards', 'Conversaciones'])
    expect(labels).not.toContain('Configuración')
    expect(labels).not.toContain('Usuarios y roles')
  })

  it('una sección sin permiso a la que se accede por URL muestra "Sin acceso"', async () => {
    signedInAs(USERS.viewer)
    renderApp('/configuracion')
    expect(await screen.findByRole('heading', { name: /sin acceso/i })).toBeInTheDocument()
  })

  it('una sección aún no implementada muestra "Próximamente"', async () => {
    signedInAs(USERS.admin)
    renderApp('/flujos')
    expect(await screen.findByRole('heading', { name: 'Flujos de insights' })).toBeInTheDocument()
    expect(screen.getByText(/próximamente/i)).toBeInTheDocument()
  })

  it('la raíz lleva a la primera sección permitida', async () => {
    signedInAs(USERS.viewer)
    const { router } = renderApp('/')
    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboards'))
  })
})

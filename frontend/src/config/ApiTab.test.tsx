import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { User } from '../auth/types'
import { platformConfig } from '../test/configFixtures'
import { openApiDoc } from '../test/openapiFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

function setup(options: { user?: User; path?: string; specStatus?: number; specGate?: Promise<void> } = {}) {
  const fetchMock = signedInAs(options.user ?? USERS.admin, {
    'GET /api/config': () => ({ status: 200, body: platformConfig() }),
    'GET /api/config/audit': () => ({ status: 200, body: { items: [] } }),
    'GET /openapi.json': async () => {
      await options.specGate
      return options.specStatus ? { status: options.specStatus } : { status: 200, body: openApiDoc() }
    },
  })
  const requested = (path: string) => fetchMock.mock.calls.some(([input]) => new URL(String(input), 'http://localhost').pathname === path)
  return { ...renderApp(options.path ?? '/configuracion?tab=api'), requested }
}

const SOLO_CONFIG: User = {
  id: '1US-00000006-0000-5000-8000-000000000006', name: 'Auditora Demo', email: 'auditora@bancohorizonte.demo',
  role: 'auditoria', role_name: 'Auditoría', permissions: ['config:view'],
}

describe('Configuración: pestaña «API»', () => {
  it('es la última pestaña y se abre desde la lista con su código en la URL', async () => {
    const { router } = setup({ path: '/configuracion' })
    const tabs = within(await screen.findByRole('tablist', { name: /secciones/i })).getAllByRole('tab')
    expect(tabs.at(-1)).toHaveTextContent('API')
    await userEvent.click(screen.getByRole('tab', { name: 'API' }))
    expect(router.state.location.search).toBe('?tab=api')
    expect(await screen.findByRole('list', { name: 'Visor OpenAPI' })).toBeInTheDocument()
  })

  it('al recargar con ?tab=api se mantiene la pestaña', async () => {
    setup()
    expect(await screen.findByRole('tab', { name: 'API' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByRole('list', { name: 'Visor OpenAPI' })).toBeInTheDocument()
  })

  it.each([
    ['supervisor', USERS.supervisor],
    ['un rol personalizado con config:view', SOLO_CONFIG],
  ])('la ve %s', async (_, user) => {
    setup({ user })
    expect(await screen.findByRole('tab', { name: 'API' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByRole('list', { name: 'Visor OpenAPI' })).toBeInTheDocument()
  })

  it.each([
    ['analista', USERS.analista],
    ['viewer', USERS.viewer],
  ])('%s no ve Configuración ni pide la especificación', async (_, user) => {
    const { requested } = setup({ user })
    expect(await screen.findByRole('heading', { name: 'Sin acceso' })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'API' })).not.toBeInTheDocument()
    expect(requested('/openapi.json')).toBe(false)
  })

  it('pinta todas las operaciones de la especificación servida, con título, versión y total', async () => {
    setup()
    const viewer = await screen.findByRole('list', { name: 'Visor OpenAPI' })
    expect(within(viewer).getAllByRole('listitem')).toHaveLength(9)
    const panel = screen.getByRole('tabpanel')
    expect(panel).toHaveTextContent('Speech & Text Analytics API')
    expect(panel).toHaveTextContent('versión 0.6.0')
    expect(panel).toHaveTextContent('9 operaciones')
  })

  it('no muestra ni pide el registro de auditoría', async () => {
    const { requested } = setup()
    await screen.findByRole('list', { name: 'Visor OpenAPI' })
    expect(requested('/openapi.json')).toBe(true)
    expect(requested('/api/config/audit')).toBe(false)
    expect(screen.queryByRole('heading', { name: /registro de cambios/i })).not.toBeInTheDocument()
  })

  it('muestra el estado de carga mientras llega la especificación', async () => {
    let release = () => {}
    setup({ specGate: new Promise<void>((resolve) => { release = resolve }) })
    expect(await screen.findByText('Cargando especificación…')).toBeInTheDocument()
    release()
    expect(await screen.findByRole('list', { name: 'Visor OpenAPI' })).toBeInTheDocument()
    expect(screen.queryByText('Cargando especificación…')).not.toBeInTheDocument()
  })

  it('si falla la descarga avisa sin romper las demás pestañas', async () => {
    setup({ specStatus: 500 })
    expect(await screen.findByRole('alert')).toHaveTextContent('No se ha podido cargar la especificación de la API.')
    expect(screen.queryByRole('list', { name: 'Visor OpenAPI' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'General' }))
    expect(await screen.findByLabelText('Nombre de la plataforma')).toHaveValue('Speech & Text Analytics')
  })
})

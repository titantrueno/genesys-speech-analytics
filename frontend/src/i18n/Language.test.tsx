import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { platformConfig } from '../test/configFixtures'
import { formatDateTime, formatKpi } from '../lib/format'
import { mockApi, renderApp, signedInAs, USERS } from '../test/utils'

const GENERAL = { platform_name: 'Speech & Text Analytics', timezone: 'UTC', language: 'es-ES' }
const publicConfig = (language: string) => ({ 'GET /api/config/public': () => ({ status: 200, body: { ...GENERAL, language } }) })

describe('Idioma de la interfaz (FE016)', () => {
  it('sin configuración usa español', async () => {
    mockApi({})
    renderApp('/login')
    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('es')
  })

  it('el idioma de la plataforma se aplica también al login, sin sesión', async () => {
    mockApi(publicConfig('en-US'))
    renderApp('/login')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })

  it('un idioma no soportado vuelve a español', async () => {
    mockApi(publicConfig('fr-FR'))
    renderApp('/login')
    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('no hay selector de idioma en el login ni en el panel principal', async () => {
    signedInAs(USERS.admin, publicConfig('es-ES'))
    renderApp('/dashboards')
    await screen.findByRole('navigation', { name: 'Principal' })
    expect(screen.queryByRole('combobox', { name: /idioma|language/i })).not.toBeInTheDocument()
    sessionStorage.clear()
    mockApi(publicConfig('es-ES'))
    renderApp('/login')
    await screen.findByRole('button', { name: 'Entrar' })
    expect(screen.queryByRole('combobox', { name: /idioma|language/i })).not.toBeInTheDocument()
  })

  it('guardar English en Configuración › General cambia los menús sin recargar', async () => {
    let general = { ...GENERAL }
    const config = () => ({ ...platformConfig(), general })
    signedInAs(USERS.admin, {
      'GET /api/config/public': () => ({ status: 200, body: general }),
      'GET /api/config': () => ({ status: 200, body: config() }),
      'GET /api/config/audit': () => ({ status: 200, body: { items: [] } }),
      'PUT /api/config/general': (init) => {
        general = JSON.parse(String(init.body))
        return { status: 200, body: config() }
      },
    })
    const user = userEvent.setup()
    renderApp('/configuracion')
    const panel = await screen.findByRole('tabpanel')
    await user.selectOptions(await within(panel).findByLabelText('Idioma por defecto'), 'en-US')
    await user.click(within(panel).getByRole('button', { name: 'Guardar' }))

    const nav = await screen.findByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: 'Semantic search' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })

  it('las páginas de error se traducen', async () => {
    signedInAs(USERS.viewer, publicConfig('en-US'))
    renderApp('/configuracion')
    expect(await screen.findByRole('heading', { name: 'No access' })).toBeInTheDocument()
  })

  it('fechas y números siguen el idioma activo', async () => {
    mockApi(publicConfig('en-US'))
    renderApp('/login')
    await screen.findByRole('button', { name: 'Sign in' })
    expect(formatKpi(1234.5, '%')).toBe('1,234.5%')
    expect(formatKpi(1234, 'conversaciones')).toBe('1,234')
    expect(formatDateTime('2026-09-27T10:30:00Z')).toMatch(/Sep 27/)
  })

  it('con español, fechas y números no cambian', async () => {
    mockApi({})
    renderApp('/login')
    await screen.findByRole('button', { name: 'Entrar' })
    expect(formatKpi(1234.5, '%')).toBe('1.234,5 %')
    expect(formatKpi(12345, 'conversaciones')).toBe('12.345')
    expect(formatDateTime('2026-09-27T10:30:00Z')).toMatch(/27 sept/)
  })
})

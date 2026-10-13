import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { formatDateTime, formatKpi } from '../lib/format'
import { renderApp, signedInAs, mockApi, USERS } from '../test/utils'

const GENERAL = { platform_name: 'Speech & Text Analytics', timezone: 'UTC', language: 'es-ES' }
const publicConfig = (language: string) => ({ 'GET /api/config/public': () => ({ status: 200, body: { ...GENERAL, language } }) })

describe('Idioma de la interfaz (FE016)', () => {
  it('sin elección personal ni configuración usa español', async () => {
    mockApi({})
    renderApp('/login')
    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('es')
  })

  it('el idioma global de la plataforma se aplica también al login, sin sesión', async () => {
    mockApi(publicConfig('en-US'))
    renderApp('/login')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })

  it('un idioma global no soportado vuelve a español', async () => {
    mockApi(publicConfig('fr-FR'))
    renderApp('/login')
    expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('el selector cambia toda la interfaz sin recargar y se conserva al recargar', async () => {
    signedInAs(USERS.admin, publicConfig('es-ES'))
    const user = userEvent.setup()
    const first = renderApp('/dashboards')
    const select = await screen.findByRole('combobox', { name: 'Idioma' })
    await user.selectOptions(select, 'en-US')
    const nav = await screen.findByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('link', { name: 'Semantic search' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
    expect(localStorage.getItem('sta.language')).toBe('en-US')
    first.unmount()

    renderApp('/dashboards')
    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
  })

  it('la elección personal prevalece sobre el idioma global', async () => {
    localStorage.setItem('sta.language', 'en-US')
    mockApi(publicConfig('es-ES'))
    renderApp('/login')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('«Idioma de la plataforma» borra la elección personal', async () => {
    localStorage.setItem('sta.language', 'en-US')
    signedInAs(USERS.admin, publicConfig('es-ES'))
    const user = userEvent.setup()
    renderApp('/dashboards')
    const select = await screen.findByRole('combobox', { name: 'Language' })
    await user.selectOptions(select, '')
    expect(await screen.findByRole('navigation', { name: 'Principal' })).toBeInTheDocument()
    expect(localStorage.getItem('sta.language')).toBeNull()
  })

  it('un valor guardado no soportado se ignora', async () => {
    localStorage.setItem('sta.language', 'klingon')
    mockApi(publicConfig('en-US'))
    renderApp('/login')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('si localStorage falla, la interfaz sigue con el idioma global', async () => {
    const original = Storage.prototype.getItem
    Storage.prototype.getItem = function (key: string) {
      if (key === 'sta.language') throw new Error('bloqueado')
      return original.call(this, key)
    }
    try {
      mockApi(publicConfig('en-US'))
      renderApp('/login')
      expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    } finally {
      Storage.prototype.getItem = original
    }
  })

  it('el selector de la pantalla de login permite elegir inglés antes de entrar', async () => {
    mockApi(publicConfig('es-ES'))
    const user = userEvent.setup()
    renderApp('/login')
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Idioma' }), 'en-US')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument())
  })

  it('las páginas de error se traducen', async () => {
    localStorage.setItem('sta.language', 'en-US')
    signedInAs(USERS.viewer)
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

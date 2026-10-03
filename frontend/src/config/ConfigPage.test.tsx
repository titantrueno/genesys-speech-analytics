import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { auditEntry, CONNECTORS, platformConfig } from '../test/configFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from '../auth/types'
import type { AuditEntry, Connector, PlatformConfig } from './types'

type Call = { method: string; path: string; body?: unknown }
type Reply = { status: number; body?: unknown }

function setup(options: {
  user?: User; path?: string; config?: PlatformConfig; configStatus?: number; configGate?: Promise<void>
  audit?: AuditEntry[]; reply?: Partial<Record<string, (body: unknown) => Reply>>
} = {}) {
  let config = options.config ?? platformConfig()
  let connectors: Connector[] = [...CONNECTORS]
  const calls: Call[] = []
  const write = (method: string, path: string, apply: (body: never) => void) => (init: RequestInit) => {
    const body = init.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const custom = options.reply?.[`${method} ${path}`]
    if (custom) return custom(body)
    apply(body as never)
    return { status: 200, body: config }
  }
  signedInAs(options.user ?? USERS.admin, {
    'GET /api/config': async () => {
      await options.configGate
      return options.configStatus ? { status: options.configStatus } : { status: 200, body: config }
    },
    'GET /api/config/connectors': () => ({ status: 200, body: { items: connectors } }),
    'GET /api/config/audit': (init) => {
      const section = new URL(init.url, 'http://localhost').searchParams.get('section')
      return { status: 200, body: { items: (options.audit ?? []).filter((e) => e.section === section) } }
    },
    'PUT /api/config/general': write('PUT', '/api/config/general', (body) => { config = { ...config, general: body } }),
    'PUT /api/config/privacy': write('PUT', '/api/config/privacy', (body) => { config = { ...config, privacy: body } }),
    'PUT /api/config/ai': write('PUT', '/api/config/ai', (body: { provider: string; model: string }) => {
      config = { ...config, ai: { ...body, simulated: true } }
    }),
    [`POST /api/config/connectors/${CONNECTORS[1].id}/sync`]: (init) => {
      calls.push({ method: 'POST', path: `sync ${CONNECTORS[1].id}` })
      void init
      const synced = { ...connectors[1], last_sync: '2026-09-28T09:15:00+00:00' }
      connectors = [connectors[0], synced]
      return { status: 200, body: synced }
    },
  })
  return { ...renderApp(options.path ?? '/configuracion'), calls }
}

async function openTab(name: RegExp | string) {
  await userEvent.click(await screen.findByRole('tab', { name }))
  return screen.getByRole('tabpanel')
}

describe('Configuración: estructura y pestañas', () => {
  it('muestra las ocho pestañas y abre General por defecto', async () => {
    setup()
    expect(await screen.findByRole('heading', { name: 'Configuración' })).toBeInTheDocument()
    const tabs = within(await screen.findByRole('tablist', { name: /secciones/i })).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual([
      'General', 'Fuentes de datos', 'Taxonomía', 'KPIs y objetivos', 'Cumplimiento', 'Privacidad', 'Modelos de IA', 'API',
    ])
    expect(screen.getByRole('tab', { name: 'General' })).toHaveAttribute('aria-selected', 'true')
    expect(within(screen.getByRole('tabpanel')).getByLabelText('Nombre de la plataforma')).toHaveValue('Speech & Text Analytics')
  })

  it('la pestaña activa vive en la URL', async () => {
    const { router } = setup({ path: '/configuracion?tab=modelos' })
    expect(await screen.findByRole('tab', { name: 'Modelos de IA' })).toHaveAttribute('aria-selected', 'true')
    await openTab('Privacidad')
    expect(router.state.location.search).toBe('?tab=privacidad')
  })

  it('las flechas recorren las pestañas en ciclo y solo la activa es tabulable', async () => {
    setup()
    const general = await screen.findByRole('tab', { name: 'General' })
    expect(screen.getAllByRole('tab').filter((t) => t.tabIndex === 0)).toEqual([general])
    general.focus()
    await userEvent.keyboard('{ArrowLeft}')
    expect(screen.getByRole('tab', { name: 'API' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'API' })).toHaveFocus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'General' })).toHaveAttribute('aria-selected', 'true')
  })

  it('muestra el estado de carga y el de error', async () => {
    let release = () => {}
    setup({ configGate: new Promise<void>((resolve) => { release = resolve }) })
    expect(await screen.findByRole('status')).toHaveTextContent(/cargando/i)
    release()
    expect(await screen.findByRole('tab', { name: 'General' })).toBeInTheDocument()
  })

  it('un error al cargar se indica', async () => {
    setup({ configStatus: 500 })
    expect(await screen.findByRole('alert')).toHaveTextContent(/no se ha podido cargar la configuración/i)
  })
})

describe('Configuración: General', () => {
  it('guarda los cambios y lo confirma', async () => {
    const { calls } = setup()
    const panel = await openTab('General')
    const name = within(panel).getByLabelText('Nombre de la plataforma')
    await userEvent.clear(name)
    await userEvent.type(name, 'Analítica Horizonte')
    await userEvent.selectOptions(within(panel).getByLabelText('Zona horaria'), 'Asia/Tokyo')
    await userEvent.click(within(panel).getByRole('button', { name: 'Guardar' }))
    expect(await within(panel).findByRole('status')).toHaveTextContent(/cambios guardados/i)
    expect(calls).toEqual([{ method: 'PUT', path: '/api/config/general',
      body: { platform_name: 'Analítica Horizonte', timezone: 'Asia/Tokyo', language: 'es-ES' } }])
  })

  it('un 422 muestra el error junto a cada campo y conserva lo escrito', async () => {
    setup({ reply: { 'PUT /api/config/general': () => ({ status: 422, body: { detail: [
      { loc: ['body', 'platform_name'], msg: 'Máximo 60 caracteres', type: 'string_too_long' },
      { loc: ['body', 'timezone'], msg: 'Zona horaria desconocida', type: 'value_error' },
    ] } }) } })
    const panel = await openTab('General')
    const name = within(panel).getByLabelText('Nombre de la plataforma')
    await userEvent.clear(name)
    await userEvent.type(name, 'Un nombre larguísimo')
    await userEvent.click(within(panel).getByRole('button', { name: 'Guardar' }))
    expect(await within(panel).findByText('Máximo 60 caracteres')).toBeInTheDocument()
    expect(name).toHaveAccessibleDescription(/^Máximo 60 caracteres/)
    expect(name).toHaveAttribute('aria-invalid', 'true')
    expect(name).toHaveValue('Un nombre larguísimo')
    expect(within(panel).getByLabelText('Zona horaria')).toHaveAccessibleDescription(/zona horaria desconocida/i)
  })

  it('no se puede guardar sin cambios', async () => {
    setup()
    const panel = await openTab('General')
    expect(within(panel).getByRole('button', { name: 'Guardar' })).toBeDisabled()
  })
})

describe('Configuración: Fuentes de datos', () => {
  it('lista los conectores y sincroniza uno', async () => {
    const { calls } = setup()
    const panel = await openTab('Fuentes de datos')
    const rows = await within(panel).findAllByRole('row')
    expect(rows).toHaveLength(3)
    expect(rows[1]).toHaveTextContent('Genesys Cloud · voz transcrita')
    expect(rows[1]).toHaveTextContent('Conectado')
    expect(rows[1]).toHaveTextContent('642')
    await userEvent.click(within(rows[2]).getByRole('button', { name: /sincronizar/i }))
    await waitFor(() => expect(within(panel).getAllByRole('row')[2]).toHaveTextContent('28 sept'))
    expect(calls).toEqual([{ method: 'POST', path: `sync ${CONNECTORS[1].id}` }])
    expect(within(panel).getByText(/conectores simulados/i)).toBeInTheDocument()
  })
})

describe('Configuración: Privacidad y Modelos de IA', () => {
  it('desactiva el enmascarado y explica lo que sigue enmascarado siempre', async () => {
    const { calls } = setup()
    const panel = await openTab('Privacidad')
    const toggle = within(panel).getByRole('checkbox', { name: /enmascarar datos personales/i })
    expect(toggle).toBeChecked()
    expect(panel).toHaveTextContent(/búsqueda semántica y los prompts de los flujos usan siempre el texto enmascarado/i)
    await userEvent.click(toggle)
    await userEvent.click(within(panel).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toEqual([{ method: 'PUT', path: '/api/config/privacy', body: { pii_masking: false } }]))
  })

  it('elige el modelo por defecto e indica que la ejecución es simulada', async () => {
    const { calls } = setup()
    const panel = await openTab('Modelos de IA')
    expect(panel).toHaveTextContent(/ejecución es simulada/i)
    expect(within(panel).getByLabelText('Proveedor')).toHaveValue('simulado')
    await userEvent.selectOptions(within(panel).getByLabelText('Modelo por defecto'), 'mock-preciso')
    await userEvent.click(within(panel).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toEqual([
      { method: 'PUT', path: '/api/config/ai', body: { provider: 'simulado', model: 'mock-preciso' } },
    ]))
  })
})

describe('Configuración: auditoría y solo lectura', () => {
  it('cada pestaña muestra su registro de cambios', async () => {
    setup({ audit: [auditEntry(1), auditEntry(2, { section: 'privacidad', element: 'Enmascarado de PII',
      before: { pii_masking: true }, after: { pii_masking: false } })] })
    const general = await openTab('General')
    const log = await within(general).findByRole('region', { name: /registro de cambios/i })
    expect(log).toHaveTextContent('Admin Demo')
    expect(log).toHaveTextContent('27 sept')
    expect(log).toHaveTextContent('Speech & Text Analytics')
    expect(log).toHaveTextContent('Analítica Horizonte')
    expect(log).not.toHaveTextContent('Enmascarado')
    const privacy = await openTab('Privacidad')
    expect(await within(privacy).findByRole('region', { name: /registro de cambios/i })).toHaveTextContent('Enmascarado de PII')
  })

  it('sin cambios, el registro lo indica', async () => {
    setup()
    const panel = await openTab('Modelos de IA')
    expect(await within(panel).findByText(/sin cambios registrados/i)).toBeInTheDocument()
  })

  it('una supervisora ve la configuración en solo lectura', async () => {
    setup({ user: USERS.supervisor })
    expect(await screen.findByText(/solo lectura/i)).toBeInTheDocument()
    let panel = await openTab('General')
    expect(within(panel).getByLabelText('Nombre de la plataforma')).toBeDisabled()
    expect(within(panel).queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument()
    panel = await openTab('Fuentes de datos')
    await within(panel).findAllByRole('row')
    expect(within(panel).queryByRole('button', { name: /sincronizar/i })).not.toBeInTheDocument()
    panel = await openTab('Privacidad')
    expect(within(panel).getByRole('checkbox')).toBeDisabled()
  })
})

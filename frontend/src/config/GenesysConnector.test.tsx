import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CONNECTORS, platformConfig } from '../test/configFixtures'
import { fakeId } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from '../auth/types'
import type { GenesysConnector, GenesysTest } from '../downloads/types'

const AVAILABLE: GenesysConnector = {
  service: 'disponible', region: 'eu-west-1', credentials_configured: true, database: 'ok', last_test: null,
  last_download: { run_id: fakeId('1RN', 1), flow_id: fakeId('1FL', 1), status: 'completada_con_avisos',
    finished_at: '2026-10-12T11:32:14+00:00' },
  conversations: { total: 13, by_channel: { voz: 7, chat: 6 }, by_quality: { completa: 9, parcial: 2, sin_transcripcion: 2 } },
}
const DOWN: GenesysConnector = { service: 'no_disponible', region: null, credentials_configured: null, database: null,
  last_test: null, last_download: null, conversations: null }
const OK: GenesysTest = { ok: true, at: '2026-10-12T11:51:25+00:00', organization: 'SGTO', region: 'eu-west-1',
  message: 'Conexión correcta con Genesys Cloud' }

function setup(options: { user?: User; status?: GenesysConnector; test?: { status: number; body: unknown } } = {}) {
  let status = options.status ?? AVAILABLE
  signedInAs(options.user ?? USERS.admin, {
    'GET /api/config': () => ({ status: 200, body: platformConfig() }),
    'GET /api/config/connectors': () => ({ status: 200, body: { items: CONNECTORS } }),
    'GET /api/config/audit': () => ({ status: 200, body: { items: [] } }),
    'GET /api/config/connectors/genesys': () => ({ status: 200, body: status }),
    'POST /api/config/connectors/genesys/test': () => {
      const reply = options.test ?? { status: 200, body: OK }
      if (reply.status === 200) status = { ...status, last_test: reply.body as GenesysTest }
      return reply
    },
  })
  return renderApp('/configuracion?tab=fuentes')
}

async function card() {
  return screen.findByRole('region', { name: 'Genesys Cloud · datos reales' })
}

describe('Configuración: conector de Genesys Cloud', () => {
  it('muestra la región, la última descarga y las conversaciones por canal y calidad', async () => {
    setup()
    const genesys = await card()
    await within(genesys).findByText('Disponible')
    expect(genesys).toHaveTextContent('eu-west-1')
    expect(genesys).toHaveTextContent('Configuradas')
    expect(genesys).toHaveTextContent('12 oct, 11:32')
    expect(genesys).toHaveTextContent('Con avisos')
    expect(genesys).toHaveTextContent('13')
    expect(genesys).toHaveTextContent('Voz 7 · Chat 6')
    expect(genesys).toHaveTextContent('Completa 9 · Parcial 2 · Sin transcripción 2')
    expect(genesys).toHaveTextContent('Sin probar')
  })

  it('«Probar conexión» muestra la organización y la deja como última prueba', async () => {
    setup()
    const genesys = await card()
    await userEvent.click(await within(genesys).findByRole('button', { name: 'Probar conexión' }))
    expect(await within(genesys).findByRole('status')).toHaveTextContent('Conexión correcta con Genesys Cloud: SGTO (eu-west-1)')
    await waitFor(() => expect(genesys).toHaveTextContent('Correcta'))
  })

  it('unas credenciales no válidas se explican sin romper la pestaña', async () => {
    setup({ test: { status: 200, body: { ...OK, ok: false, organization: null, message: 'Credenciales de Genesys no válidas' } } })
    const genesys = await card()
    await userEvent.click(await within(genesys).findByRole('button', { name: 'Probar conexión' }))
    expect(await within(genesys).findByRole('alert')).toHaveTextContent('Credenciales de Genesys no válidas')
  })

  it('si el servicio de ingesta no responde, lo dice y la prueba también', async () => {
    setup({ status: DOWN, test: { status: 503, body: { detail: 'El servicio de ingesta no está disponible' } } })
    const genesys = await card()
    expect(await within(genesys).findByText(/el servicio de ingesta no responde/i)).toBeInTheDocument()
    await userEvent.click(within(genesys).getByRole('button', { name: 'Probar conexión' }))
    expect(await within(genesys).findByRole('alert')).toHaveTextContent('El servicio de ingesta no está disponible')
  })

  it('con config:view se ve el estado, pero no se puede probar', async () => {
    setup({ user: USERS.supervisor })
    const genesys = await card()
    await within(genesys).findByText('Disponible')
    expect(within(genesys).queryByRole('button', { name: 'Probar conexión' })).not.toBeInTheDocument()
  })
})

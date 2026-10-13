import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import { CONNECTORS, platformConfig } from '../test/configFixtures'
import { fakeId } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from '../auth/types'
import type { DataOrigin } from './types'
import { DataUnavailable } from '../components/DataUnavailable'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

const GENESYS = {
  service: 'disponible', region: 'eu-west-1', credentials_configured: true, database: 'ok', last_test: null,
  last_download: { run_id: fakeId('1RN', 1), flow_id: fakeId('1FL', 1), status: 'completada', finished_at: '2026-10-12T11:32:14+00:00' },
  conversations: { total: 10, by_channel: { voz: 4, chat: 6 }, by_quality: { completa: 8, parcial: 1, sin_transcripcion: 1 } },
}

function setup(options: { user?: User; origin?: DataOrigin; failSwitch?: boolean } = {}) {
  let origin: DataOrigin = options.origin ?? 'sintetico'
  const writes: unknown[] = []
  signedInAs(options.user ?? USERS.admin, {
    'GET /api/config': () => ({ status: 200, body: platformConfig({ sources: { origin } }) }),
    'PUT /api/config/sources': (init) => {
      writes.push(JSON.parse(String(init.body)))
      if (options.failSwitch) return { status: 422, body: { detail: [{ loc: ['body', 'origin'], msg: 'Valor no válido', type: 'literal_error' }] } }
      origin = (writes.at(-1) as { origin: DataOrigin }).origin
      return { status: 200, body: platformConfig({ sources: { origin } }) }
    },
    'GET /api/config/connectors': () => ({ status: 200, body: { items: CONNECTORS } }),
    'GET /api/config/connectors/genesys': () => ({ status: 200, body: GENESYS }),
    'GET /api/config/audit': () => ({ status: 200, body: { items: [] } }),
  })
  return { writes, ...renderApp('/configuracion?tab=fuentes') }
}

const card = () => screen.findByRole('region', { name: 'Origen de datos' })

describe('Configuración: origen de datos (FE012)', () => {
  it('muestra el origen activo y los dos orígenes disponibles', async () => {
    setup()
    const origin = await card()
    expect(within(origin).getByRole('radio', { name: /Sintético/ })).toBeChecked()
    expect(within(origin).getByRole('radio', { name: /Real \(Genesys Cloud\)/ })).not.toBeChecked()
    // Desde FE015 el origen se guarda: el texto no debe decir que se pierde al reiniciar.
    expect(origin).toHaveTextContent('Se conserva al reiniciar la API')
    expect(origin).not.toHaveTextContent('Se pierde al reiniciar')
  })

  it('cambiar el origen pide confirmación y no guarda hasta confirmar', async () => {
    const { writes } = setup()
    const origin = await card()
    await userEvent.click(within(origin).getByRole('radio', { name: /Real \(Genesys Cloud\)/ }))
    expect(within(origin).getByRole('alertdialog')).toHaveTextContent('Todas las secciones pasarán a trabajar con las conversaciones reales')
    expect(writes).toEqual([])
    await userEvent.click(within(origin).getByRole('button', { name: 'Cancelar' }))
    expect(within(origin).queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(within(origin).getByRole('radio', { name: /Sintético/ })).toBeChecked()
    expect(writes).toEqual([])
  })

  it('al confirmar guarda el origen y el estado del conector de Genesys sustituye a los conectores simulados', async () => {
    const { writes } = setup()
    const origin = await card()
    expect(await screen.findByText('Genesys Cloud · voz transcrita')).toBeInTheDocument()
    await userEvent.click(within(origin).getByRole('radio', { name: /Real \(Genesys Cloud\)/ }))
    await userEvent.click(within(origin).getByRole('button', { name: 'Confirmar cambio' }))
    await waitFor(() => expect(writes).toEqual([{ origin: 'real' }]))
    await waitFor(() => expect(within(origin).getByRole('radio', { name: /Real \(Genesys Cloud\)/ })).toBeChecked())
    expect(screen.queryByText('Genesys Cloud · voz transcrita')).not.toBeInTheDocument()
    expect(await screen.findByRole('region', { name: 'Genesys Cloud · datos reales' })).toBeInTheDocument()
  })

  it('con el origen real se puede volver a sintético', async () => {
    const { writes } = setup({ origin: 'real' })
    const origin = await card()
    expect(within(origin).getByRole('radio', { name: /Real \(Genesys Cloud\)/ })).toBeChecked()
    await userEvent.click(within(origin).getByRole('radio', { name: /Sintético/ }))
    await userEvent.click(within(origin).getByRole('button', { name: 'Confirmar cambio' }))
    await waitFor(() => expect(writes).toEqual([{ origin: 'sintetico' }]))
    expect(await screen.findByText('Genesys Cloud · voz transcrita')).toBeInTheDocument()
  })

  it('con config:view el origen se ve en solo lectura', async () => {
    setup({ user: USERS.supervisor, origin: 'real' })
    const origin = await card()
    expect(within(origin).getByRole('radio', { name: /Real \(Genesys Cloud\)/ })).toBeChecked()
    for (const radio of within(origin).getAllByRole('radio')) expect(radio).toBeDisabled()
  })

  it('un rechazo del servidor se muestra y deja el origen como estaba', async () => {
    setup({ failSwitch: true })
    const origin = await card()
    await userEvent.click(within(origin).getByRole('radio', { name: /Real \(Genesys Cloud\)/ }))
    await userEvent.click(within(origin).getByRole('button', { name: 'Confirmar cambio' }))
    expect(await within(origin).findByRole('alert')).toHaveTextContent('No se ha podido cambiar el origen de datos')
    await userEvent.click(within(origin).getByRole('button', { name: 'Cancelar' }))
    expect(within(origin).getByRole('radio', { name: /Sintético/ })).toBeChecked()
  })
})

describe('Aviso de datos no disponibles (503)', () => {
  it('explica que los datos reales no responden y ofrece volver a Configuración', () => {
    render(<MemoryRouter><DataUnavailable error={new ApiError(503, 'Real data is not available')} /></MemoryRouter>)
    expect(screen.getByRole('alert')).toHaveTextContent('Real data is not available')
    expect(screen.getByRole('link', { name: /Configuración/ })).toHaveAttribute('href', '/configuracion?tab=fuentes')
  })

  it('con cualquier otro error no se muestra', () => {
    const { container } = render(<MemoryRouter><DataUnavailable error={new ApiError(500, 'Error 500')} /></MemoryRouter>)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('Aviso de datos no disponibles en la aplicación', () => {
  it('el aviso aparece sobre la sección y la navegación sigue funcionando', async () => {
    signedInAs(USERS.admin, {
      'GET /api/conversations': () => ({ status: 503, body: { detail: 'Real data is not available' } }),
      'GET /api/catalog': () => ({ status: 503, body: { detail: 'Real data is not available' } }),
      'GET /api/config': () => ({ status: 200, body: platformConfig({ sources: { origin: 'real' } }) }),
      'GET /api/config/connectors': () => ({ status: 200, body: { items: CONNECTORS } }),
      'GET /api/config/connectors/genesys': () => ({ status: 200, body: GENESYS }),
      'GET /api/config/audit': () => ({ status: 200, body: { items: [] } }),
    })
    renderApp('/conversaciones')
    const alerts = await screen.findAllByRole('alert')
    expect(alerts.some((alert) => alert.textContent?.includes('Real data is not available'))).toBe(true)
    await userEvent.click(screen.getAllByRole('link', { name: /Configuración/ })[0])
    expect(await screen.findByRole('heading', { name: 'Configuración' })).toBeInTheDocument()
  })
})

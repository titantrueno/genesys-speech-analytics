import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { metricsRoutes } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

function requests(fetchMock: ReturnType<typeof signedInAs>, path: string) {
  return fetchMock.mock.calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((url) => url.pathname === path)
}

function lastRequest(fetchMock: ReturnType<typeof signedInAs>, path: string) {
  const all = requests(fetchMock, path)
  return all[all.length - 1]
}

async function openDashboard(path = '/dashboards') {
  const fetchMock = signedInAs(USERS.analista, metricsRoutes)
  const result = renderApp(path)
  await screen.findByRole('heading', { level: 1, name: 'Dashboards' })
  return { fetchMock, ...result }
}

describe('dashboards', () => {
  it('abre Visión general por defecto con sus KPIs y widgets', async () => {
    const { router } = await openDashboard()
    await waitFor(() => expect(router.state.location.pathname).toBe('/dashboards/vision-general'))

    const volume = await screen.findByRole('group', { name: 'Volumen' })
    expect(within(volume).getByText('1.319')).toBeInTheDocument()
    expect(within(volume).getByText(/-3,7\s?%/)).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'Tasa de resolución' })).getByText('65,5 %')).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'Duración media (AHT)' })).getByText('3:52 min')).toBeInTheDocument()

    for (const title of ['Volumen de conversaciones', 'Distribución por main topic', 'Volumen por canal', 'KPIs por main topic']) {
      expect(screen.getByRole('heading', { level: 2, name: title })).toBeInTheDocument()
    }
    const table = await screen.findByRole('table', { name: 'KPIs por main topic' })
    expect(within(table).getByText('Cargo no reconocido')).toBeInTheDocument()
    expect(within(table).getByText('Incidencia en cajero')).toBeInTheDocument()
  })

  it('marca si la variación mejora o empeora según el sentido del KPI', async () => {
    await openDashboard()
    const escalation = await screen.findByRole('group', { name: 'Tasa de escalado' })
    expect(within(escalation).getByText('Empeora')).toBeInTheDocument()
    const resolution = screen.getByRole('group', { name: 'Tasa de resolución' })
    expect(within(resolution).getByText('Mejora')).toBeInTheDocument()
  })

  it('el índice de sentimiento muestra la variación absoluta, no un porcentaje', async () => {
    await openDashboard('/dashboards/experiencia-de-cliente')
    const sentiment = await screen.findByRole('group', { name: 'Sentimiento medio' })
    expect(within(sentiment).getByText('+0,04')).toBeInTheDocument()
    expect(within(sentiment).queryByText(/%/)).toBeNull()
  })

  it('muestra la distribución por main topic ordenada con su volumen', async () => {
    await openDashboard()
    const list = await screen.findByRole('list', { name: 'Distribución por main topic' })
    const rows = within(list).getAllByRole('listitem')
    expect(rows.map((r) => within(r).getByText(/^[A-Z]/).textContent)).toEqual(['Cargo no reconocido', 'Acceso a banca digital', 'Incidencia en cajero'])
    expect(within(rows[0]).getByText('660')).toBeInTheDocument()
  })

  it.each([
    ['Calidad y cumplimiento', '/dashboards/calidad-y-cumplimiento',
      ['Cumplimiento por check', 'Evolución del cumplimiento', 'Cumplimiento por cola', 'Rendimiento por agente'], 'Cumplimiento'],
    ['Experiencia de cliente', '/dashboards/experiencia-de-cliente',
      ['Evolución del CSAT predicho', 'CSAT predicho por main topic', 'Sentimiento medio por cola'], 'CSAT predicho'],
  ])('el dashboard %s muestra sus widgets', async (tab, path, titles, kpi) => {
    const { router } = await openDashboard()
    await userEvent.setup().click(await screen.findByRole('link', { name: tab }))
    await waitFor(() => expect(router.state.location.pathname).toBe(path))
    for (const title of titles) expect(await screen.findByRole('heading', { level: 2, name: title })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: kpi })).toBeInTheDocument()
  })

  it('cumplimiento por check lista cada check con su porcentaje', async () => {
    await openDashboard('/dashboards/calidad-y-cumplimiento')
    const list = await screen.findByRole('list', { name: 'Cumplimiento por check' })
    expect(within(list).getByText('Verificación de identidad del cliente')).toBeInTheDocument()
    expect(within(list).getByText('88,3 %')).toBeInTheDocument()
  })
})

describe('filtros globales', () => {
  it('cambiar el canal actualiza la URL y vuelve a pedir todos los widgets', async () => {
    const { router, fetchMock } = await openDashboard()
    await screen.findByRole('group', { name: 'Volumen' })
    await userEvent.setup().selectOptions(screen.getByLabelText('Canal'), 'chat')

    await waitFor(() => expect(router.state.location.search).toContain('channel=chat'))
    await waitFor(() => {
      for (const path of ['/api/metrics/summary', '/api/metrics/timeseries', '/api/metrics/breakdown']) {
        expect(lastRequest(fetchMock, path).searchParams.get('channel')).toBe('chat')
      }
    })
  })

  it('filtrar por main topic con el selector múltiple', async () => {
    const { router, fetchMock } = await openDashboard()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /main topic/i }))
    await user.click(await screen.findByRole('checkbox', { name: 'Incidencia en cajero' }))
    await user.click(screen.getByRole('checkbox', { name: 'Cargo no reconocido' }))

    await waitFor(() => expect(router.state.location.search).toContain('main_topic=cajeros'))
    await waitFor(() => expect(lastRequest(fetchMock, '/api/metrics/summary').searchParams.getAll('main_topic'))
      .toEqual(['cajeros', 'cargo_no_reconocido']))
  })

  it('al montar con filtros en la URL los restaura en los controles y en las peticiones', async () => {
    const { fetchMock } = await openDashboard('/dashboards/vision-general?from=2026-09-01&to=2026-09-20&channel=voz&queue=Tarjetas')
    await screen.findByRole('group', { name: 'Volumen' })
    expect(screen.getByLabelText('Canal')).toHaveValue('voz')
    expect(screen.getByLabelText('Desde')).toHaveValue('2026-09-01')
    expect(screen.getByLabelText('Hasta')).toHaveValue('2026-09-20')
    expect(screen.getByRole('button', { name: /cola/i })).toHaveTextContent('Tarjetas')
    const summary = lastRequest(fetchMock, '/api/metrics/summary').searchParams
    expect(summary.get('from')).toBe('2026-09-01')
    expect(summary.get('to')).toBe('2026-09-20')
    expect(summary.getAll('queue')).toEqual(['Tarjetas'])
  })

  it('el preset de periodo fija un rango de N días en la URL', async () => {
    const { router } = await openDashboard()
    await userEvent.setup().selectOptions(await screen.findByLabelText('Periodo'), '7')
    await waitFor(() => expect(router.state.location.search).toContain('from='))
    const params = new URLSearchParams(router.state.location.search)
    const days = (Date.parse(params.get('to')!) - Date.parse(params.get('from')!)) / 86_400_000
    expect(days).toBe(6)
  })

  it('limpiar filtros vuelve al periodo por defecto', async () => {
    const { router } = await openDashboard('/dashboards/vision-general?channel=chat&main_topic=cajeros')
    await userEvent.setup().click(await screen.findByRole('button', { name: /limpiar filtros/i }))
    await waitFor(() => expect(router.state.location.search).toBe(''))
  })

  it('la granularidad día/semana cambia la serie temporal y se guarda en la URL', async () => {
    const { router, fetchMock } = await openDashboard()
    const card = (await screen.findByRole('heading', { level: 2, name: 'Volumen de conversaciones' })).closest('section')!
    await userEvent.setup().click(within(card).getByRole('button', { name: 'Semana' }))
    await waitFor(() => expect(router.state.location.search).toContain('granularity=week'))
    await waitFor(() => expect(lastRequest(fetchMock, '/api/metrics/timeseries').searchParams.get('granularity')).toBe('week'))
    expect(within(card).getByRole('button', { name: 'Semana' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('cada gráfico ofrece su vista de tabla', async () => {
    await openDashboard()
    const card = (await screen.findByRole('heading', { level: 2, name: 'Volumen de conversaciones' })).closest('section')!
    await userEvent.setup().click(within(card).getByRole('button', { name: 'Ver tabla' }))
    const table = await within(card).findByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(4)
    expect(within(table).getByText('18')).toBeInTheDocument()
  })
})

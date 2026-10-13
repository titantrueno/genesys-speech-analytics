import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { breakdownFixture, metricsRoutes, summaryFixture, timeseriesFixture } from '../test/fixtures'
import { realCatalog } from '../test/realFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

const ANALYSIS = ['resolution_rate', 'escalation_rate', 'fcr_rate', 'csat_avg', 'effort_avg', 'compliance_rate', 'churn_high_pct']
const PENDING_TEXT = 'Sin datos · pendiente de análisis'

const realSummary = {
  ...summaryFixture,
  kpis: summaryFixture.kpis.map((kpi) => ANALYSIS.includes(kpi.code)
    ? { ...kpi, value: null, previous: null, delta: null, delta_pct: null, pending: true, based_on: null }
    : { ...kpi, pending: false, based_on: kpi.code === 'sentiment_avg' ? 7 : kpi.code === 'aht_s' ? 4 : null }),
  compliance_by_check: summaryFixture.compliance_by_check.map((c) => ({ ...c, value: null, applicable: 0 })),
}

function realRoutes() {
  return {
    ...metricsRoutes,
    'GET /api/catalog': () => ({ status: 200, body: realCatalog }),
    'GET /api/metrics/summary': () => ({ status: 200, body: realSummary }),
    'GET /api/metrics/timeseries': ({ url }: { url: string }) => {
      const kpi = new URL(url, 'http://localhost').searchParams.get('kpi') ?? ''
      const body = timeseriesFixture(url)
      return { status: 200, body: ANALYSIS.includes(kpi)
        ? { ...body, pending: true, points: body.points.map((p) => ({ ...p, value: null })) } : { ...body, pending: false } }
    },
    'GET /api/metrics/breakdown': ({ url }: { url: string }) => {
      const body = breakdownFixture(url)
      const analysis = (kpis: Record<string, number | null>) => Object.fromEntries(
        Object.entries(kpis).map(([code, value]) => [code, ANALYSIS.includes(code) ? null : value]))
      if (body.dimension === 'main_topic') return { status: 200, body: { ...body, pending: true, items: [] } }
      return { status: 200, body: { ...body, pending: true, items: body.items.map((i) => ({ ...i, kpis: analysis(i.kpis) })) } }
    },
  }
}

const card = (title: string) => screen.getByRole('heading', { level: 2, name: title }).closest('section') as HTMLElement

async function open(path: string) {
  signedInAs(USERS.analista, realRoutes())
  renderApp(path)
  await screen.findByRole('heading', { level: 1, name: 'Dashboards' })
}

describe('dashboards con conversaciones reales', () => {
  it('los KPIs que dependen del análisis dicen «Sin datos · pendiente de análisis», no 0 ni un error', async () => {
    await open('/dashboards/vision-general')
    for (const label of ['Tasa de resolución', 'Tasa de escalado', 'Resolución en primer contacto (FCR)', 'CSAT predicho']) {
      const tile = await screen.findByRole('group', { name: label })
      expect(tile).toHaveTextContent(PENDING_TEXT)
      expect(tile).not.toHaveTextContent('0,0')
    }
  })

  it('volumen y AHT se calculan; el sentimiento indica sobre cuántas conversaciones', async () => {
    await open('/dashboards/vision-general')
    const volume = await screen.findByRole('group', { name: 'Volumen' })
    expect(within(volume).getByText('1.319')).toBeInTheDocument()
    expect(volume).not.toHaveTextContent(PENDING_TEXT)
    expect(await screen.findByRole('group', { name: 'Duración media (AHT)' })).toHaveTextContent('Calculado sobre 4 conversaciones')
    expect(await screen.findByRole('group', { name: 'Sentimiento medio' })).toHaveTextContent('Calculado sobre 7 conversaciones')
  })

  it('un KPI pendiente sigue llevando al listado (drill-down)', async () => {
    await open('/dashboards/vision-general')
    const tile = await screen.findByRole('group', { name: 'Tasa de resolución' })
    expect(within(tile).getByRole('link')).toHaveAttribute('href', expect.stringContaining('/conversaciones'))
  })

  it('las series y desgloses que dependen del análisis lo dicen, y los de volumen se pintan', async () => {
    await open('/dashboards/vision-general')
    await screen.findByRole('heading', { level: 2, name: 'Distribución por main topic' })
    expect(await within(card('Distribución por main topic')).findByText(PENDING_TEXT)).toBeInTheDocument()
    expect(within(card('KPIs por main topic')).getByText(PENDING_TEXT)).toBeInTheDocument()
    const queue = card('Volumen por cola')
    expect(await within(queue).findByRole('list', { name: 'Volumen por cola' })).toBeInTheDocument()
    expect(queue).not.toHaveTextContent(PENDING_TEXT)
  })

  it('en Calidad y cumplimiento, cumplimiento y su evolución quedan pendientes y la tabla por agente marca sus columnas', async () => {
    await open('/dashboards/calidad-y-cumplimiento')
    await screen.findByRole('heading', { level: 2, name: 'Cumplimiento por check' })
    expect(await within(card('Cumplimiento por check')).findByText(PENDING_TEXT)).toBeInTheDocument()
    expect(await within(card('Evolución del cumplimiento')).findByText(PENDING_TEXT)).toBeInTheDocument()
    const agents = await screen.findByRole('table', { name: 'Rendimiento por agente' })
    expect(within(agents).getAllByText('Pendiente de análisis').length).toBeGreaterThan(0)
  })
})

describe('dashboards con el análisis a medias (FE014)', () => {
  // Hallazgo del recorrido de T8: el desglose por main topic decía «pendiente» con los main topics ya escritos.
  function partialRoutes() {
    const routes = realRoutes()
    return {
      ...routes,
      'GET /api/metrics/breakdown': ({ url }: { url: string }) => {
        const body = breakdownFixture(url)
        const pendingKpis = ANALYSIS.filter((code) => code !== 'csat_avg')
        const items = body.items.map((i) => ({ ...i, kpis: Object.fromEntries(
          Object.entries(i.kpis).map(([code, value]) => [code, pendingKpis.includes(code) ? null : value])) }))
        return { status: 200, body: { ...body, pending: body.dimension !== 'main_topic', pending_kpis: pendingKpis, items } }
      },
    }
  }

  it('el desglose por main topic se pinta y cada KPI dice si sigue pendiente', async () => {
    signedInAs(USERS.analista, partialRoutes())
    renderApp('/dashboards/vision-general')
    await screen.findByRole('heading', { level: 2, name: 'Distribución por main topic' })
    const topics = card('Distribución por main topic')
    expect(await within(topics).findByRole('list', { name: 'Distribución por main topic' })).toBeInTheDocument()
    expect(topics).not.toHaveTextContent(PENDING_TEXT)
    const table = card('KPIs por main topic')
    expect(table).toHaveTextContent('Pendiente de análisis')  // los KPIs sin datos
    expect(within(table).queryAllByText('Pendiente de análisis').length).toBeLessThan(
      within(table).getAllByRole('row').length * ANALYSIS.length)
  })
})

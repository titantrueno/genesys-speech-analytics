import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { conversationDetailFixture, conversationItem, DETAIL_ID, detailRoutes, metricsRoutes } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

const english = { 'GET /api/config/public': () => ({ status: 200, body: { platform_name: 'Speech & Text Analytics', timezone: 'UTC', language: 'en-US' } }) }

describe('Pantallas de datos con la interfaz en inglés (FE016, T3)', () => {
  it('dashboards: menús, filtros, KPIs y widgets en inglés; los nombres de datos no cambian', async () => {
    signedInAs(USERS.analista, { ...metricsRoutes, ...english })
    renderApp('/dashboards')
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboards' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Quality and compliance' })).toBeInTheDocument()

    const filters = screen.getByRole('search', { name: 'Filters' })
    for (const label of ['Period', 'From', 'To', 'Channel']) expect(within(filters).getByText(label)).toBeInTheDocument()
    expect(within(filters).getByRole('option', { name: 'Last 30 days' })).toBeInTheDocument()

    const resolution = await screen.findByRole('group', { name: 'Resolution rate' })
    expect(within(resolution).getByText('65.5%')).toBeInTheDocument()
    expect(within(resolution).getByText('Improving')).toBeInTheDocument()
    expect(within(resolution).getByText('vs previous period')).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'Volume' })).getByText('1,319')).toBeInTheDocument()

    for (const title of ['Conversation volume', 'Distribution by main topic', 'Volume by channel', 'KPIs by main topic']) {
      expect(screen.getByRole('heading', { level: 2, name: title })).toBeInTheDocument()
    }
    expect(screen.getAllByRole('button', { name: 'View table' }).length).toBeGreaterThan(0)
    // Main topics y colas son datos de la plataforma: no se traducen.
    const table = await screen.findByRole('table', { name: 'KPIs by main topic' })
    expect(within(table).getByText('Cargo no reconocido')).toBeInTheDocument()
  })

  it('listado de conversaciones: cabeceras y etiquetas en inglés; main topic y summary sin traducir', async () => {
    signedInAs(USERS.analista, { ...detailRoutes, ...english })
    renderApp('/conversaciones?resolution=escalada')
    expect(await screen.findByRole('heading', { level: 1, name: 'Conversations' })).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Conversations' })
    for (const column of ['Date', 'Channel', 'Queue', 'Agent', 'Duration', 'Sentiment', 'Resolution']) {
      expect(within(table).getByRole('columnheader', { name: new RegExp(column) })).toBeInTheDocument()
    }
    expect(within(table).getAllByText('Voice').length).toBeGreaterThan(0)
    expect(within(table).getAllByText('Escalated').length).toBeGreaterThan(0)
    expect(screen.getByRole('list', { name: 'Active filters' })).toHaveTextContent('Resolution: Escalated')
    // Datos: tal cual llegan.
    const first = conversationItem(0)
    expect(within(table).getAllByText(first.main_topic_label).length).toBeGreaterThan(0)
    expect(within(table).getAllByText(/La clienta llama porque no reconoce un cargo/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument()
  })

  it('detalle: textos fijos en inglés; transcripción, resumen, main topic, palabras clave y temas sin traducir', async () => {
    signedInAs(USERS.viewer, { ...detailRoutes, ...english })
    renderApp(`/conversaciones/${DETAIL_ID}`)
    await screen.findByRole('heading', { level: 1, name: `Conversation ${DETAIL_ID}` })
    expect(screen.getByRole('link', { name: /Back to the list/ })).toBeInTheDocument()

    const header = screen.getByRole('region', { name: 'Conversation summary' })
    const { analysis } = conversationDetailFixture
    expect(within(header).getByText(conversationDetailFixture.main_topic_label)).toBeInTheDocument()
    expect(within(header).getByText(analysis.summary, { exact: false })).toBeInTheDocument()

    const chat = screen.getByRole('list', { name: 'Transcript' })
    // El resaltado de palabras clave parte el texto en varios nodos: se compara el texto completo.
    for (const turn of conversationDetailFixture.turns) expect(chat.textContent).toContain(turn.text)
    expect(within(chat).getByText('Virtual assistant')).toBeInTheDocument()
    expect(within(chat).getAllByText('Customer', { selector: 'p' })).toHaveLength(3)
    expect(within(chat).getAllByText('Sentiment: negative').length).toBeGreaterThan(0)

    const panel = screen.getByRole('complementary', { name: 'Analysis' })
    for (const label of ['Resolution', 'Predicted CSAT', 'Customer effort', 'Churn risk', 'Overall sentiment']) {
      expect(within(panel).getByText(label)).toBeInTheDocument()
    }
    expect(within(panel).getByText('Unresolved')).toBeInTheDocument()
    expect(within(panel).getByText('High')).toBeInTheDocument()
    expect(within(panel).getByText('1.3 / 5')).toBeInTheDocument()
    expect(await within(panel).findByText('Not met')).toBeInTheDocument()
    expect(within(panel).getByText('Not applicable')).toBeInTheDocument()
    for (const heading of ['Result', 'Sentiment over time', 'Compliance', 'Secondary topics', 'Entities', 'Keywords']) {
      expect(within(panel).getByRole('heading', { name: heading })).toBeInTheDocument()
    }
    expect(within(panel).getByText('Amount')).toBeInTheDocument()
    for (const datum of [...analysis.keywords, ...analysis.secondary_topics, '366,12 €', 'TiendaYa Online', 'Verificación de identidad del cliente']) {
      expect(await within(panel).findByText(datum)).toBeInTheDocument()
    }
  })
})

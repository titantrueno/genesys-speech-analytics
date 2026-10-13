import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { conversationItem, DETAIL_ID, detailRoutes, fakeId } from '../test/fixtures'
import { loaded, setupEditor } from '../test/flowEditor'
import { CATALOG, CHAINED, FLOW_ID, flowFixture, nodeId } from '../test/flowFixtures'
import { mockReactFlow } from '../test/reactFlow'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { ConversationListItem } from '../api/conversations'
import type { FlowGraph, FlowSummary, NodeState, Run, RunOutput } from './types'

beforeAll(mockReactFlow)

const english = { 'GET /api/config/public': () => ({ status: 200, body: { platform_name: 'Speech & Text Analytics', timezone: 'UTC', language: 'en-US' } }) }
const AUTHOR = { id: fakeId('1US', 3), name: 'Analista Demo' }

describe('Flujos de insights con la interfaz en inglés (FE016, T5)', () => {
  it('listado: cabeceras, tipo y estados en inglés; los nombres de los flujos no cambian', async () => {
    const flows: FlowSummary[] = [
      { id: fakeId('1FL', 1), name: 'Motivos de fraude', author: AUTHOR, created_at: '2026-09-20T08:00:00+00:00', updated_at: '2026-09-27T10:30:00+00:00',
        status: 'valido', last_run: { id: fakeId('1RN', 1), created_at: '2026-09-27T11:00:00+00:00', status: 'ok' }, next_run: null },
      { id: fakeId('1FL', 2), name: 'Borrador de quejas', author: AUTHOR, created_at: '2026-09-20T08:00:00+00:00', updated_at: '2026-09-26T10:30:00+00:00',
        status: 'con_errores', last_run: null, next_run: null },
    ]
    signedInAs(USERS.analista, {
      ...english,
      'GET /api/flows': () => ({ status: 200, body: { items: flows } }),
      'GET /api/flows/catalog': () => ({ status: 200, body: CATALOG }),
      'GET /api/download-flows': () => ({ status: 200, body: { items: [] } }),
    })
    renderApp('/flujos')
    expect(await screen.findByRole('heading', { name: 'Insight flows' })).toBeInTheDocument()
    const fraud = await screen.findByRole('row', { name: /Motivos de fraude/ })
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(
      ['Name', 'Type', 'Author', 'Last modified', 'Last run', 'Next run', 'Status', 'Actions'])
    expect(within(fraud).getByText('Valid')).toBeInTheDocument()
    expect(within(fraud).getByText('OK')).toBeInTheDocument()
    expect(within(fraud).getByText('Insights')).toBeInTheDocument()
    expect(within(fraud).getByText('Analista Demo')).toBeInTheDocument()
    const draft = screen.getByRole('row', { name: /Borrador de quejas/ })
    expect(within(draft).getByText('With errors')).toBeInTheDocument()
    expect(within(draft).getByText('No runs')).toBeInTheDocument()
    expect(within(draft).getByRole('button', { name: /Duplicate/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /New flow/ })).toBeInTheDocument()
  })

  it('editor: paleta, lienzo y panel del Prompt en inglés; plantilla y etiquetas del usuario sin traducir', async () => {
    const ctx = setupEditor({ extraRoutes: english })
    await loaded()
    expect(screen.getByRole('complementary', { name: 'Node palette' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Prompt' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'History' })).toBeInTheDocument()
    expect(screen.getByText('Saved')).toBeInTheDocument()

    // Resumen del nodo en el lienzo: opciones del catálogo traducidas; plantilla del usuario tal cual.
    const card = within(ctx.node(nodeId(2)))
    expect(card.getByText('Clasifica {{summary}}')).toBeInTheDocument()
    expect(card.getByText('Simulated fast · T 0.2 · Label from a list (2 labels)')).toBeInTheDocument()
    expect(within(ctx.node(nodeId(1))).getByText('Random · 40 conversations')).toBeInTheDocument()
    expect(within(ctx.node(nodeId(1))).getByText('No filters')).toBeInTheDocument()

    fireEvent.click(ctx.node(nodeId(2)))
    const panel = await screen.findByRole('region', { name: 'Prompt configuration' })
    for (const text of ['Template', 'Model and temperature', 'Output format']) expect(within(panel).getByText(text)).toBeInTheDocument()
    expect(within(panel).getByLabelText('Prompt text')).toHaveValue('Clasifica {{summary}}')
    expect(within(panel).getByRole('option', { name: 'Simulated (no LLM)' })).toBeInTheDocument()
    expect(within(panel).getByRole('option', { name: 'Label from a list' })).toBeInTheDocument()
    expect(within(panel).getByText('Labels (2 to 20)')).toBeInTheDocument()
    expect(within(panel).getByLabelText('Label 1')).toHaveValue('A')
    expect(within(panel).getByRole('group', { name: 'Insert variable' })).toBeInTheDocument()
    expect(within(panel).getByText('Connections')).toBeInTheDocument()
  })

  it('editor: el rechazo de una conexión se explica en inglés y la validación también', async () => {
    setupEditor({ extraRoutes: english })
    await loaded()
    fireEvent.click(document.querySelector<HTMLElement>(`.react-flow__node[data-id="${nodeId(1)}"]`)!)
    const panel = await screen.findByRole('region', { name: 'Sampling configuration' })
    const user = userEvent.setup()
    await user.selectOptions(within(panel).getByLabelText('Add output to'), nodeId(4))
    expect(await screen.findByText('Cannot connect: A Sampling can only be connected to a Prompt.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Validate' }))
    expect(await screen.findByRole('region', { name: 'Validation' })).toBeInTheDocument()
    expect(await screen.findByText('The flow is valid.')).toBeInTheDocument()
  })

  it('ejecución: estado, métrica y tabla en inglés; resultados del flujo sin traducir', async () => {
    const GRAPH: FlowGraph = CHAINED
    const state = (status: NodeState['status'], processed = 0, total: number | null = null): NodeState => ({ status, processed, total, message: null })
    const ROW = (i: number) => ({ ...conversationItem(i), id: i === 0 ? DETAIL_ID : conversationItem(i).id }) as ConversationListItem
    const outputs: Record<string, RunOutput> = {
      [nodeId(4)]: { node_id: nodeId(4), kind: 'metrica', destination: 'reparto',
        result: { aggregation: 'porcentaje', total: 40, items: [{ label: 'A', count: 30, percent: 75 }, { label: 'B', count: 10, percent: 25 }] } },
      [nodeId(5)]: { node_id: nodeId(5), kind: 'tabla', destination: 'detalle',
        result: { rows: [{ conversation: ROW(0), result: 'Cliente molesto por un cargo' }, { conversation: ROW(1), result: { motivo: 'fraude', urgente: true } }] } },
    }
    const run: Run = {
      id: fakeId('1RN', 7), flow_id: FLOW_ID, seed: 1, graph: GRAPH, created_at: '2026-09-27T11:00:00+00:00',
      started_at: '2026-09-27T11:00:00+00:00', finished_at: '2026-09-27T11:00:02.500000+00:00', duration_ms: 2500,
      status: 'ok', sample_size: 40, user: { id: USERS.analista.id, name: 'Analista Demo' },
      nodes: Object.fromEntries(GRAPH.nodes.map((n) => [n.id, state('ok', 40, 40)])), outputs, origin: 'manual', notes: [], download: null,
    }
    signedInAs(USERS.analista, {
      ...detailRoutes, ...english,
      [`GET /api/flows/${FLOW_ID}`]: () => ({ status: 200, body: flowFixture(GRAPH) }),
      'GET /api/flows/catalog': () => ({ status: 200, body: CATALOG }),
      [`GET /api/flows/${FLOW_ID}/runs/${run.id}`]: () => ({ status: 200, body: run }),
    })
    renderApp(`/flujos/${FLOW_ID}/ejecuciones/${run.id}`)
    expect(await screen.findByRole('heading', { name: 'Run of Motivos de fraude' })).toBeInTheDocument()
    expect(screen.getByText('Sample: 40')).toBeInTheDocument()
    expect(screen.getByText('Duration: 2.5 s')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'History' })).toBeInTheDocument()

    const tabs = await screen.findByRole('tablist', { name: 'Outputs' })
    expect(within(tabs).getByRole('tab', { name: 'reparto' })).toBeInTheDocument()
    expect(await screen.findByText('% of conversations per label · sample of 40')).toBeInTheDocument()
    await userEvent.click(within(tabs).getByRole('tab', { name: 'detalle' }))
    const table = await screen.findByRole('table', { name: 'Insights per conversation: detalle' })
    for (const column of ['Date', 'Channel', 'Queue', 'Main topic', 'Result']) {
      expect(within(table).getByRole('columnheader', { name: column })).toBeInTheDocument()
    }
    expect(within(table).getByText('Cliente molesto por un cargo')).toBeInTheDocument()
    expect(within(table).getByText('yes')).toBeInTheDocument()
    await waitFor(() => expect(within(table).getAllByText('Voice').length).toBeGreaterThan(0))
  })
})

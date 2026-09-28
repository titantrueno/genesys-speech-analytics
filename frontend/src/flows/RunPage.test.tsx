import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import type { ConversationListItem } from '../api/conversations'
import { conversationDetailFixture, conversationItem, DETAIL_ID, detailRoutes, fakeId } from '../test/fixtures'
import { CATALOG, CHAINED, FLOW_ID, flowFixture, nodeId } from '../test/flowFixtures'
import { mockReactFlow } from '../test/reactFlow'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { FlowGraph, NodeState, Run, RunOutput, RunSummary } from './types'

beforeAll(mockReactFlow)

const RUN_ID = fakeId('1RN', 7)
const GRAPH: FlowGraph = {
  ...CHAINED,
  nodes: [...CHAINED.nodes, { id: nodeId(6), type: 'output', position: { x: 900, y: 200 }, config: { kind: 'informe', destination: 'resumen' } }],
  edges: [...CHAINED.edges, { source: nodeId(3), target: nodeId(6) }],
}
const state = (status: NodeState['status'], processed = 0, total: number | null = null, message: string | null = null): NodeState =>
  ({ status, processed, total, message })
const everyNode = (s: NodeState) => Object.fromEntries(GRAPH.nodes.map((n) => [n.id, s]))
const ROW = (i: number) => ({ ...conversationItem(i), id: i === 0 ? DETAIL_ID : conversationItem(i).id }) as ConversationListItem
const OUTPUTS: Record<string, RunOutput> = {
  [nodeId(6)]: { node_id: nodeId(6), kind: 'informe', destination: 'resumen', result: { text: 'Informe «resumen»\n\nMuestra: 40 conversaciones.' } },
  [nodeId(4)]: {
    node_id: nodeId(4), kind: 'metrica', destination: 'reparto',
    result: { aggregation: 'recuento', total: 40, items: [{ label: 'A', count: 30, percent: 75 }, { label: 'B', count: 10, percent: 25 }] },
  },
  [nodeId(5)]: {
    node_id: nodeId(5), kind: 'tabla', destination: 'detalle',
    result: { rows: [{ conversation: ROW(0), result: 'Cliente molesto por un cargo' }, { conversation: ROW(1), result: { motivo: 'fraude', urgente: true } }] },
  },
}

function run(overrides: Partial<Run> = {}): Run {
  return {
    id: RUN_ID, flow_id: FLOW_ID, seed: 1, graph: GRAPH, created_at: '2026-09-27T11:00:00+00:00',
    started_at: '2026-09-27T11:00:00+00:00', finished_at: '2026-09-27T11:00:02.500000+00:00', duration_ms: 2500,
    status: 'ok', sample_size: 40, user: { id: USERS.analista.id, name: 'Analista Demo' },
    nodes: everyNode(state('ok', 40, 40)), outputs: OUTPUTS, ...overrides,
  }
}

function setup(replies: Array<{ status: number; body?: unknown }>, path = `/flujos/${FLOW_ID}/ejecuciones/${RUN_ID}`, runs: RunSummary[] = []) {
  let calls = 0
  signedInAs(USERS.analista, {
    ...detailRoutes,
    [`GET /api/flows/${FLOW_ID}`]: () => ({ status: 200, body: flowFixture(GRAPH) }),
    'GET /api/flows/catalog': () => ({ status: 200, body: CATALOG }),
    [`GET /api/flows/${FLOW_ID}/runs/${RUN_ID}`]: () => replies[Math.min(calls++, replies.length - 1)],
    [`GET /api/flows/${FLOW_ID}/runs`]: () => ({ status: 200, body: { items: runs } }),
  })
  return { ...renderApp(path), calls: () => calls }
}

const nodeCard = (container: HTMLElement, id: string) => container.querySelector<HTMLElement>(`.react-flow__node[data-id="${id}"]`)!

describe('ejecución de un flujo', () => {
  it('actualiza el estado de cada nodo por polling hasta que termina y después deja de consultar', async () => {
    const pending = run({ status: 'pendiente', duration_ms: null, finished_at: null, sample_size: null, nodes: everyNode(state('pendiente')), outputs: {} })
    const running = run({
      status: 'en_curso', duration_ms: null, finished_at: null,
      nodes: { ...everyNode(state('pendiente')), [nodeId(1)]: state('ok', 40, 40), [nodeId(2)]: state('en_curso', 10, 40) }, outputs: {},
    })
    const { container, calls } = setup([{ status: 200, body: pending }, { status: 200, body: running }, { status: 200, body: run() }])
    expect(await screen.findByText('Ejecutando… el progreso se actualiza automáticamente.')).toBeInTheDocument()
    expect(within(nodeCard(container, nodeId(1))).getByText('Pendiente')).toBeInTheDocument()
    expect(within(nodeCard(container, nodeId(1))).getByText('Sin empezar')).toBeInTheDocument()
    expect(screen.getByText('Los resultados aparecerán al terminar la ejecución.')).toBeInTheDocument()

    await waitFor(() => expect(within(nodeCard(container, nodeId(2))).getByText('En curso')).toBeInTheDocument(), { timeout: 2000 })
    expect(within(nodeCard(container, nodeId(2))).getByText('10 de 40 procesadas')).toBeInTheDocument()
    expect(within(nodeCard(container, nodeId(1))).getByText('OK')).toBeInTheDocument()

    await waitFor(() => expect(screen.getByRole('tablist', { name: 'Outputs' })).toBeInTheDocument(), { timeout: 2000 })
    expect(within(nodeCard(container, nodeId(5))).getByText('40 de 40 procesadas')).toBeInTheDocument()
    expect(screen.queryByText(/Ejecutando…/)).not.toBeInTheDocument()
    const finalCalls = calls()
    await new Promise((resolve) => setTimeout(resolve, 1200))
    expect(calls()).toBe(finalCalls)
  })

  it('muestra fecha, usuario, muestra, duración y estado', async () => {
    setup([{ status: 200, body: run() }])
    const heading = await screen.findByRole('heading', { name: 'Ejecución de Motivos de fraude' })
    const summary = heading.nextElementSibling!
    expect(summary).toHaveTextContent('Analista Demo')
    expect(summary).toHaveTextContent('OK')
    expect(summary).toHaveTextContent('27 sept, 11:00')
    expect(summary).toHaveTextContent('Muestra: 40')
    expect(summary).toHaveTextContent('Duración: 2,5 s')
  })

  it('muestra una pestaña por output en el orden del grafo, con flechas de teclado', async () => {
    setup([{ status: 200, body: run() }])
    const tabs = await screen.findByRole('tablist', { name: 'Outputs' })
    expect(within(tabs).getAllByRole('tab').map((t) => t.textContent)).toEqual(['reparto', 'detalle', 'resumen'])
    expect(within(tabs).getByRole('tab', { name: 'reparto' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(within(tabs).getByRole('tab', { name: 'reparto' }), { key: 'ArrowLeft' })
    expect(within(tabs).getByRole('tab', { name: 'resumen' })).toHaveAttribute('aria-selected', 'true')
    expect(within(tabs).getByRole('tab', { name: 'resumen' })).toHaveFocus()
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Muestra: 40 conversaciones.')
  })

  it('la métrica se ve como gráfico de barras y como tabla', async () => {
    setup([{ status: 200, body: run() }])
    const user = userEvent.setup()
    const chart = await screen.findByRole('list', { name: 'Gráfico de reparto' })
    expect(within(chart).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['A30', 'B10'])
    await user.click(screen.getByRole('button', { name: 'Ver tabla' }))
    const table = screen.getByRole('table', { name: 'Tabla de reparto' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => r.textContent)).toEqual(['A3075,0 %', 'B1025,0 %'])
  })

  it('la tabla lleva al detalle de cada conversación y desde allí se vuelve a la ejecución', async () => {
    const { router } = setup([{ status: 200, body: run() }])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('tab', { name: 'detalle' }))
    const table = screen.getByRole('table', { name: 'Insights por conversación: detalle' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('Cliente molesto por un cargo')
    expect(rows[1]).toHaveTextContent('motivofraude')
    expect(rows[1]).toHaveTextContent('urgentesí')
    await user.click(within(rows[0]).getByText('Cliente molesto por un cargo'))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/conversaciones/${DETAIL_ID}`))
    expect(await screen.findByRole('heading', { name: `Conversación ${conversationDetailFixture.id}` })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Volver a la ejecución' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/${FLOW_ID}/ejecuciones/${RUN_ID}`))
  })

  it('una ejecución con error muestra el nodo que ha fallado', async () => {
    const failed = run({
      status: 'error', outputs: {},
      nodes: { ...everyNode(state('pendiente')), [nodeId(1)]: state('error', 0, 0, 'La muestra está vacía: ninguna conversación cumple los filtros.') },
    })
    setup([{ status: 200, body: failed }])
    expect(await screen.findByRole('alert')).toHaveTextContent('Sampling: La muestra está vacía')
    expect(screen.getByText('Esta ejecución no ha producido resultados.')).toBeInTheDocument()
  })

  it('una ejecución inexistente o un error de la API muestran un aviso', async () => {
    setup([{ status: 404, body: { detail: 'Ejecución no encontrada' } }])
    expect(await screen.findByRole('alert')).toHaveTextContent('Ejecución no encontrada.')
  })

  it('el lienzo de la ejecución es de solo lectura', async () => {
    const { container } = setup([{ status: 200, body: run() }])
    await screen.findByRole('tablist', { name: 'Outputs' })
    expect(container.querySelectorAll('.react-flow__node')).toHaveLength(6)
    expect(container.querySelectorAll('.react-flow__node.draggable')).toHaveLength(0)
    expect(container.querySelectorAll('.react-flow__handle.connectable')).toHaveLength(0)
  })
})

describe('historial de ejecuciones', () => {
  const RUNS: RunSummary[] = [
    { id: RUN_ID, created_at: '2026-09-27T11:00:00+00:00', started_at: null, finished_at: null, duration_ms: 2500, status: 'ok', sample_size: 40, user: { id: 'x', name: 'Analista Demo' } },
    { id: fakeId('1RN', 6), created_at: '2026-09-26T09:15:00+00:00', started_at: null, finished_at: null, duration_ms: 480, status: 'error', sample_size: 0, user: { id: 'y', name: 'Admin Demo' } },
  ]

  it('lista fecha, usuario, tamaño de muestra, duración y estado, y reabre una ejecución', async () => {
    const { router } = setup([{ status: 200, body: run() }], `/flujos/${FLOW_ID}/ejecuciones`, RUNS)
    const user = userEvent.setup()
    expect(await screen.findByRole('heading', { name: 'Historial de ejecuciones · Motivos de fraude' })).toBeInTheDocument()
    const rows = screen.getAllByRole('row').slice(1).map((r) => r.textContent)
    expect(rows).toEqual(['27 sept, 11:00Analista Demo402,5 sOK', '26 sept, 09:15Admin Demo0480 msError'])
    await user.click(screen.getByRole('link', { name: '27 sept, 11:00' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/${FLOW_ID}/ejecuciones/${RUN_ID}`))
    expect(await screen.findByRole('tablist', { name: 'Outputs' })).toBeInTheDocument()
  })

  it('sin ejecuciones lo indica', async () => {
    setup([], `/flujos/${FLOW_ID}/ejecuciones`, [])
    expect(await screen.findByText('Este flujo aún no se ha ejecutado.')).toBeInTheDocument()
  })

  it('desde el editor se abre el historial', async () => {
    const { router } = setup([], `/flujos/${FLOW_ID}`, RUNS)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('link', { name: 'Historial' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/${FLOW_ID}/ejecuciones`))
  })
})

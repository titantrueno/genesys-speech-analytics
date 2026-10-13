import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { fakeId } from '../test/fixtures'
import { CATALOG, CHAINED, FLOW_ID, flowFixture, nodeId } from '../test/flowFixtures'
import { mockReactFlow } from '../test/reactFlow'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { FlowGraph, FlowSummary, NodeState, Run, RunSummary } from './types'

beforeAll(mockReactFlow)

/** Vista de una ejecución end-to-end, historial y listado (FE017, T7; criterios 9 y 15). */
const RUN_ID = fakeId('1RN', 7)
const DOWNLOAD_ID = fakeId('1RN', 8)
const BOX = nodeId(9)
const GRAPH: FlowGraph = {
  version: 1,
  nodes: [{ id: BOX, type: 'descarga', position: { x: -300, y: 0 }, config: {
    interval: { type: 'relativo', unit: 'hoy' }, channels: ['voz', 'chat'], schedule: { type: 'cada_horas', hours: 1 }, active: true } },
  ...CHAINED.nodes],
  edges: [{ source: BOX, target: nodeId(1) }, ...CHAINED.edges],
}
const state = (status: NodeState['status'], processed = 0, total: number | null = null, message: string | null = null): NodeState =>
  ({ status, processed, total, message })
const counters = (inserted: number) => ({ found: 12, downloaded: inserted, inserted, updated: 1, skipped: 0, skipped_existing: 0,
  errors: 2, skipped_in_progress: 0, skipped_other_channel: 0, by_channel: { voz: 0, chat: 0 },
  by_quality: { completa: 0, parcial: 0, sin_transcripcion: 0 }, undelivered_messages: 0 })

function run(overrides: Partial<Run> = {}): Run {
  return {
    id: RUN_ID, flow_id: FLOW_ID, seed: 1, graph: GRAPH, created_at: '2026-10-14T09:00:00+00:00',
    started_at: '2026-10-14T09:00:00+00:00', finished_at: null, duration_ms: null, status: 'en_curso', sample_size: null,
    user: { id: 'system', name: 'Scheduler' }, origin: 'programada', notes: [],
    nodes: { ...Object.fromEntries(GRAPH.nodes.map((n) => [n.id, state('pendiente')])), [BOX]: state('en_curso', 3, 12) },
    outputs: {}, download: { node_id: BOX, run_id: DOWNLOAD_ID, status: 'en_curso', counters: counters(3), error: null },
    ...overrides,
  }
}

const SKIPPED_MESSAGE = 'The download returned no conversations'
const DONE_EMPTY = run({
  status: 'ok', finished_at: '2026-10-14T09:00:05+00:00', duration_ms: 5000,
  notes: ['Scheduled run at 08:00 skipped: another run was in progress'],
  nodes: { ...Object.fromEntries(GRAPH.nodes.map((n) => [n.id, state('omitido', 0, null, SKIPPED_MESSAGE)])), [BOX]: state('ok', 12, 12) },
  download: { node_id: BOX, run_id: DOWNLOAD_ID, status: 'completada', counters: { ...counters(0), updated: 0, errors: 0 }, error: null },
})

function setup(replies: Run[], options: { runs?: RunSummary[]; path?: string; flows?: FlowSummary[] } = {}) {
  let calls = 0
  const logCalls: string[] = []
  signedInAs(USERS.analista, {
    [`GET /api/flows/${FLOW_ID}`]: () => ({ status: 200, body: flowFixture(GRAPH) }),
    'GET /api/flows/catalog': () => ({ status: 200, body: CATALOG }),
    [`GET /api/flows/${FLOW_ID}/runs/${RUN_ID}`]: () => ({ status: 200, body: replies[Math.min(calls++, replies.length - 1)] }),
    [`GET /api/flows/${FLOW_ID}/runs/${RUN_ID}/download/log`]: (init) => {
      logCalls.push(init.url)
      return { status: 200, body: { items: [
        { id: 1, at: '2026-10-14T09:00:01+00:00', level: 'info', stage: 'search', message: '12 found', genesys_id: null },
        { id: 2, at: '2026-10-14T09:00:02+00:00', level: 'aviso', stage: 'normalization', message: 'Partial transcript',
          genesys_id: '687f2225-6f3b-4446-bfd3-f5d2b3416814' }] } }
    },
    [`GET /api/flows/${FLOW_ID}/runs`]: () => ({ status: 200, body: { items: options.runs ?? [] } }),
    'GET /api/flows': () => ({ status: 200, body: { items: options.flows ?? [] } }),
    'GET /api/download-flows': () => ({ status: 200, body: { items: [] } }),
  })
  return { ...renderApp(options.path ?? `/flujos/${FLOW_ID}/ejecuciones/${RUN_ID}`), logCalls }
}

const card = (container: HTMLElement, id: string) => container.querySelector<HTMLElement>(`.react-flow__node[data-id="${id}"]`)!

describe('ejecución con caja «Genesys download»', () => {
  it('muestra el estado y los contadores de la descarga y los actualiza por polling', async () => {
    const finished = run({ download: { node_id: BOX, run_id: DOWNLOAD_ID, status: 'en_curso', counters: counters(9), error: null } })
    setup([run(), finished, DONE_EMPTY])
    const section = await screen.findByRole('region', { name: 'Descarga de Genesys' })
    expect(within(section).getByText('En curso')).toBeInTheDocument()
    expect(within(section).getByText('Encontradas').nextSibling).toHaveTextContent('12')
    expect(within(section).getByText('Guardadas').nextSibling).toHaveTextContent('4')
    await waitFor(() => expect(within(section).getByText('Guardadas').nextSibling).toHaveTextContent('10'), { timeout: 3000 })
    await waitFor(() => expect(within(section).getByText('Completada')).toBeInTheDocument(), { timeout: 3000 })
  })

  it('abre el log de la descarga desde la ejecución', async () => {
    const { logCalls } = setup([DONE_EMPTY])
    const user = userEvent.setup()
    const section = await screen.findByRole('region', { name: 'Descarga de Genesys' })
    await user.click(within(section).getByRole('button', { name: 'Ver log de la descarga' }))
    const log = await screen.findByRole('region', { name: 'Log' })
    expect(await within(log).findByText('Partial transcript')).toBeInTheDocument()
    expect(logCalls.length).toBeGreaterThan(0)
  })

  it('los nodos omitidos dicen por qué y la ejecución muestra su origen y sus notas', async () => {
    const { container } = setup([DONE_EMPTY])
    await screen.findByRole('region', { name: 'Descarga de Genesys' })
    const sampling = card(container, nodeId(1))
    expect(within(sampling).getByText('Omitido')).toBeInTheDocument()
    expect(within(sampling).getByText(SKIPPED_MESSAGE)).toHaveClass('text-slate-500')
    expect(screen.getByText('Programada')).toBeInTheDocument()
    expect(screen.getByText('Scheduler')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('Scheduled run at 08:00 skipped: another run was in progress')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()  // omitido no es un error
  })

  it('una ejecución sin caja no muestra la sección de descarga', async () => {
    setup([run({ graph: CHAINED, download: null, status: 'ok', origin: 'manual',
      nodes: Object.fromEntries(CHAINED.nodes.map((n) => [n.id, state('ok', 40, 40)])) })])
    expect(await screen.findByText('Manual')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Descarga de Genesys' })).not.toBeInTheDocument()
  })

  it('el historial muestra el origen de cada ejecución', async () => {
    const summary = (n: number, origin: RunSummary['origin']): RunSummary => ({
      id: fakeId('1RN', n), created_at: '2026-10-14T09:00:00+00:00', started_at: null, finished_at: null, duration_ms: 1200,
      status: 'ok', sample_size: 5, user: { id: 'system', name: origin === 'programada' ? 'Scheduler' : 'Analista Demo' }, origin })
    setup([], { path: `/flujos/${FLOW_ID}/ejecuciones`, runs: [summary(1, 'programada'), summary(2, 'manual')] })
    const table = await screen.findByRole('table')
    expect(within(table).getByRole('columnheader', { name: 'Origen' })).toBeInTheDocument()
    const rows = within(table).getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('Programada')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Manual')).toBeInTheDocument()
  })

  it('el listado muestra la próxima ejecución de un flujo de insights programado', async () => {
    const flow = (n: number, next_run: string | null): FlowSummary => ({
      id: fakeId('1FL', n), name: `Flujo ${n}`, author: { id: fakeId('1US', 3), name: 'Analista Demo' },
      created_at: '2026-10-01T08:00:00+00:00', updated_at: '2026-10-13T10:30:00+00:00', status: 'valido', last_run: null, next_run })
    setup([], { path: '/flujos', flows: [flow(1, '2026-10-14T10:00:00+00:00'), flow(2, null)] })
    const first = (await screen.findByRole('link', { name: 'Flujo 1' })).closest('tr')!
    const second = screen.getByRole('link', { name: 'Flujo 2' }).closest('tr')!
    expect(first).toHaveTextContent('14 oct, 10:00')
    expect(second).not.toHaveTextContent('14 oct')
  })
})

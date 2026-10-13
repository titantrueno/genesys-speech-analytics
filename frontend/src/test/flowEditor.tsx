import { fireEvent, screen } from '@testing-library/react'
import type { User } from '../auth/types'
import { NODE_DRAG_TYPE } from '../flows/FlowCanvas'
import type { FlowGraph, Issue } from '../flows/types'
import { explorerRoutes, fakeId } from './fixtures'
import { CATALOG, CHAINED, FLOW_ID, flowFixture, nodeId } from './flowFixtures'
import { renderApp, signedInAs, USERS } from './utils'

/** Editor de flujos con la API simulada: guarda, valida, estima y ejecuta en memoria. */
type Reply = { status: number; body?: unknown }
export const RUN_ID = fakeId('1RN', 1)

export function setupEditor(options: {
  graph?: FlowGraph
  user?: User
  flowStatus?: number
  validate?: (graph: FlowGraph) => Issue[]
  run?: () => Reply
  saveStatus?: number
  estimate?: (body: { query: unknown; size?: number }) => Reply
  catalog?: Partial<typeof CATALOG>
  /** Rutas adicionales (p. ej. `GET /api/config/public` para probar otro idioma). */
  extraRoutes?: Parameters<typeof signedInAs>[1]
} = {}) {
  let stored = structuredClone(options.graph ?? CHAINED)
  const puts: FlowGraph[] = []
  const validations: FlowGraph[] = []
  const calls: string[] = []
  let minted = 100
  const estimates: Array<{ query: unknown; size?: number }> = []
  signedInAs(options.user ?? USERS.analista, {
    ...explorerRoutes([]),
    'POST /api/flows/sampling/estimate': (init) => {
      const body = JSON.parse(String(init.body))
      estimates.push(body)
      return options.estimate?.(body) ?? { status: 200, body: { available: 1234, sample_size: Math.min(body.size ?? 0, 1234) || null, period: { from: '2026-09-01', to: '2026-09-26' } } }
    },
    [`GET /api/flows/${FLOW_ID}`]: () => (options.flowStatus ? { status: options.flowStatus, body: { detail: 'Flujo no encontrado' } }
      : { status: 200, body: flowFixture(stored) }),
    'GET /api/flows/catalog': () => ({ status: 200, body: { ...CATALOG, ...options.catalog } }),
    [`PUT /api/flows/${FLOW_ID}/graph`]: (init) => {
      calls.push('PUT')
      const graph = JSON.parse(String(init.body)) as FlowGraph
      puts.push(graph)
      if (options.saveStatus) return { status: options.saveStatus, body: { detail: [{ path: 'edges[0]', message: 'Conexión no válida' }] } }
      const idMap: Record<string, string> = {}
      for (const node of graph.nodes) if (node.id.startsWith('tmp-')) idMap[node.id] = nodeId(minted++)
      const rename = (id: string) => idMap[id] ?? id
      stored = {
        version: 1,
        // El backend devuelve la configuración con su propio orden de claves: el editor no debe verlo como un cambio.
        nodes: graph.nodes.map((n) => ({ ...n, id: rename(n.id), config: Object.fromEntries(Object.entries(n.config).reverse()) }) as typeof n),
        edges: graph.edges.map((e) => ({ source: rename(e.source), target: rename(e.target) })),
      }
      return { status: 200, body: { ...flowFixture(stored), id_map: idMap } }
    },
    'POST /api/flows/validate': (init) => {
      const graph = JSON.parse(String(init.body)) as FlowGraph
      validations.push(graph)
      const issues = options.validate?.(graph) ?? []
      return { status: 200, body: { valid: issues.length === 0, issues } }
    },
    [`POST /api/flows/${FLOW_ID}/runs`]: () => {
      calls.push('RUN')
      return options.run?.() ?? { status: 202, body: { id: RUN_ID, status: 'pendiente' } }
    },
    ...options.extraRoutes,
  })
  const result = renderApp(`/flujos/${FLOW_ID}`)
  const nodes = () => [...result.container.querySelectorAll<HTMLElement>('.react-flow__node')]
  const node = (id: string) => result.container.querySelector<HTMLElement>(`.react-flow__node[data-id="${id}"]`)!
  return { ...result, puts, validations, estimates, calls, nodes, node, stored: () => stored }
}

export const loaded = () => screen.findByRole('heading', { name: 'Motivos de fraude' })
export const saveState = () => screen.getByText(/^(Guardado|Cambios sin guardar|Guardando…|Solo lectura)$/)

export function drop(type: string, target: HTMLElement) {
  fireEvent.drop(target, {
    clientX: 200, clientY: 150,
    dataTransfer: { getData: (format: string) => (format === NODE_DRAG_TYPE ? type : ''), types: [NODE_DRAG_TYPE] },
  })
}

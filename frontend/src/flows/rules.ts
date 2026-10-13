import type { TKey } from '../i18n/dictionaries'
import type { Params } from '../i18n/translate'
import type { FlowEdge, NodeType } from './types'

/**
 * Reglas de conexión de FE004, iguales a `backend/app/flows/connections.py`.
 * `rules.cases.json` se ejecuta en los dos lados para que no diverjan.
 */
/** `message` es una clave del diccionario (`flows.rej.*`): el editor la traduce con `t(message, params)`. */
export interface Rejection { code: string; message: TKey; params?: Params }

const ALLOWED = new Set(['sampling>prompt', 'prompt>prompt', 'prompt>output'])
const SINGLE_INPUT = new Set<NodeType>(['prompt', 'output'])
export const NODE_LABELS: Record<NodeType, string> = { sampling: 'Sampling', prompt: 'Prompt', output: 'Output' }

function pairRejection(source: NodeType, target: NodeType): Pick<Rejection, 'message' | 'params'> {
  if (source === 'output') return { message: 'flows.rej.pair_output' }
  if (target === 'sampling') return { message: 'flows.rej.pair_sampling_target' }
  if (source === 'sampling') return { message: 'flows.rej.pair_sampling_source' }
  return { message: 'flows.rej.pair_generic', params: { source: NODE_LABELS[source], target: NODE_LABELS[target] } }
}

function reaches(edges: FlowEdge[], start: string, goal: string): boolean {
  const pending = [start]
  const seen = new Set(pending)
  while (pending.length) {
    const current = pending.pop()!
    if (current === goal) return true
    for (const edge of edges) {
      if (edge.source === current && !seen.has(edge.target)) {
        seen.add(edge.target)
        pending.push(edge.target)
      }
    }
  }
  return false
}

export function connectionRejection(types: Map<string, NodeType>, edges: FlowEdge[], source: string, target: string): Rejection | null {
  const sourceType = types.get(source)
  const targetType = types.get(target)
  if (!sourceType || !targetType) return { code: 'unknown_node', message: 'flows.rej.unknown_node' }
  if (source === target) return { code: 'self_loop', message: 'flows.rej.self_loop' }
  if (!ALLOWED.has(`${sourceType}>${targetType}`)) return { code: 'invalid_pair', ...pairRejection(sourceType, targetType) }
  if (edges.some((e) => e.source === source && e.target === target)) return { code: 'duplicate', message: 'flows.rej.duplicate' }
  if (SINGLE_INPUT.has(targetType) && edges.some((e) => e.target === target)) {
    return { code: 'input_taken', message: 'flows.rej.input_taken', params: { node: NODE_LABELS[targetType] } }
  }
  if (reaches(edges, target, source)) return { code: 'cycle', message: 'flows.rej.cycle' }
  return null
}

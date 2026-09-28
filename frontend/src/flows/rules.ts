import type { FlowEdge, NodeType } from './types'

/**
 * Reglas de conexión de FE004, iguales a `backend/app/flows/connections.py`.
 * `rules.cases.json` se ejecuta en los dos lados para que no diverjan.
 */
export interface Rejection { code: string; message: string }

const ALLOWED = new Set(['sampling>prompt', 'prompt>prompt', 'prompt>output'])
const SINGLE_INPUT = new Set<NodeType>(['prompt', 'output'])
export const NODE_LABELS: Record<NodeType, string> = { sampling: 'Sampling', prompt: 'Prompt', output: 'Output' }

function pairMessage(source: NodeType, target: NodeType): string {
  if (source === 'output') return 'Un Output es el final del flujo: no tiene salidas.'
  if (target === 'sampling') return 'Un Sampling es el inicio del flujo: no admite entradas.'
  if (source === 'sampling') return 'Un Sampling solo puede conectarse a un Prompt.'
  return `No se puede conectar un ${NODE_LABELS[source]} a un ${NODE_LABELS[target]}.`
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
  if (!sourceType || !targetType) return { code: 'unknown_node', message: 'La conexión apunta a un nodo que no existe.' }
  if (source === target) return { code: 'self_loop', message: 'Un nodo no puede conectarse consigo mismo.' }
  if (!ALLOWED.has(`${sourceType}>${targetType}`)) return { code: 'invalid_pair', message: pairMessage(sourceType, targetType) }
  if (edges.some((e) => e.source === source && e.target === target)) return { code: 'duplicate', message: 'Estos nodos ya están conectados.' }
  if (SINGLE_INPUT.has(targetType) && edges.some((e) => e.target === target)) {
    return { code: 'input_taken', message: `El ${NODE_LABELS[targetType]} ya tiene una entrada; desconéctala antes.` }
  }
  if (reaches(edges, target, source)) return { code: 'cycle', message: 'La conexión crearía un ciclo.' }
  return null
}

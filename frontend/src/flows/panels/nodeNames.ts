import { nodeSummary, useCatalog } from '../catalog'
import type { CanvasNode } from '../graph'
import { NODE_LABELS } from '../rules'
import type { NodeContent } from '../types'

/** Nombre legible de un nodo: tipo, número dentro de su tipo y primera línea de su resumen («Prompt 2 · Clasifica…»). */
export function useNodeNames(nodes: CanvasNode[]): Map<string, string> {
  const catalog = useCatalog()
  const counters: Record<string, number> = {}
  return new Map(nodes.map((n) => {
    counters[n.type] = (counters[n.type] ?? 0) + 1
    const [summary] = nodeSummary({ type: n.type, config: n.data.config } as NodeContent, catalog)
    const short = summary.length > 40 ? `${summary.slice(0, 39)}…` : summary
    return [n.id, `${NODE_LABELS[n.type]} ${counters[n.type]} · ${short}`]
  }))
}

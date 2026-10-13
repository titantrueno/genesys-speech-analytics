import type { Edge, Node, XYPosition } from '@xyflow/react'
import type { FlowEdge, FlowGraph, FlowNode, Issue, NodeState, NodeType, OutputConfig, PromptConfig, SamplingConfig } from './types'

/** Datos de un nodo en el lienzo: su configuración y lo que se muestra encima (errores de validación o estado de ejecución). */
export interface CanvasNodeData extends Record<string, unknown> {
  config: SamplingConfig | PromptConfig | OutputConfig
  issues?: Issue[]
  state?: NodeState
}

export type CanvasNode = Node<CanvasNodeData, NodeType>
export type CanvasEdge = Edge

const TEMPORARY = /^tmp-[A-Za-z0-9_-]{1,40}$/

export const isTemporaryId = (id: string) => TEMPORARY.test(id)

/** Clave temporal de un nodo nuevo; el backend le asigna su identificador `1ND` al guardar (solo `app/ids.py` los genera). */
export function temporaryId(): string {
  return `tmp-${crypto.randomUUID()}`
}

export const edgeId = (edge: FlowEdge) => `${edge.source}>${edge.target}`

/** Proveedor y modelo que toma un Prompt nuevo (Configuración › Modelos de IA). */
export interface ModelDefaults { provider: string; model: string }
const SIMULATED: ModelDefaults = { provider: 'simulado', model: 'mock-rapido' }

export function defaultConfig(type: NodeType, defaults: ModelDefaults = SIMULATED): FlowNode['config'] {
  switch (type) {
    case 'descarga': return { interval: { type: 'relativo', unit: 'hoy' }, channels: ['voz', 'chat'], overwrite: false, schedule: { type: 'desactivada' }, active: true }
    case 'sampling': return { query: { root: { op: 'and', conditions: [] } }, method: 'aleatorio', size: 100 }
    case 'prompt': return { template: '', provider: defaults.provider, model: defaults.model, temperature: 0.2, output: { type: 'texto' } }
    case 'output': return { kind: 'tabla', destination: '' }
  }
}

export function newNode(type: NodeType, position: XYPosition, defaults?: ModelDefaults): CanvasNode {
  return { id: temporaryId(), type, position, data: { config: defaultConfig(type, defaults) } }
}

export function toCanvasNodes(graph: FlowGraph): CanvasNode[] {
  return graph.nodes.map((n) => ({ id: n.id, type: n.type, position: { ...n.position }, data: { config: structuredClone(n.config) } }))
}

export function toCanvasEdges(graph: FlowGraph): CanvasEdge[] {
  return graph.edges.map((e) => ({ id: edgeId(e), source: e.source, target: e.target }))
}

/** JSON del flujo a partir del lienzo; descarta selección, medidas y demás estado propio de React Flow. */
export function fromCanvas(nodes: CanvasNode[], edges: CanvasEdge[]): FlowGraph {
  return {
    version: 1,
    nodes: nodes.map((n) => ({ id: n.id, type: n.type, position: { x: n.position.x, y: n.position.y }, config: n.data.config }) as FlowNode),
    edges: edges.map((e) => ({ source: e.source, target: e.target })),
  }
}

/** Aplica los identificadores que devuelve el backend al guardar, conservando la selección y las medidas del lienzo. */
export function remapNodes(nodes: CanvasNode[], idMap: Record<string, string>): CanvasNode[] {
  return nodes.map((n) => (idMap[n.id] ? { ...n, id: idMap[n.id] } : n))
}

export function remapEdges(edges: CanvasEdge[], idMap: Record<string, string>): CanvasEdge[] {
  return edges.map((e) => {
    const source = idMap[e.source] ?? e.source
    const target = idMap[e.target] ?? e.target
    return source === e.source && target === e.target ? e : { ...e, id: edgeId({ source, target }), source, target }
  })
}

export function remapIds(nodes: CanvasNode[], edges: CanvasEdge[], idMap: Record<string, string>) {
  return { nodes: remapNodes(nodes, idMap), edges: remapEdges(edges, idMap) }
}

/** Igualdad de dos valores JSON sin depender del orden de las claves (el backend devuelve la configuración con su propio orden). */
export function sameJson(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null) return false
  if (Array.isArray(a) !== Array.isArray(b)) return false
  if (Array.isArray(a)) return a.length === (b as unknown[]).length && a.every((item, i) => sameJson(item, (b as unknown[])[i]))
  const left = Object.entries(a).filter(([, v]) => v !== undefined)
  const right = Object.entries(b).filter(([, v]) => v !== undefined)
  return left.length === right.length && left.every(([key, value]) => sameJson(value, (b as Record<string, unknown>)[key]))
}

const NODE_SIZE = { width: 240, height: 100 }
const GAP = { x: 60, y: 30 }
// Dos columnas: el lienzo se estrecha al abrir el panel de configuración y una fila larga quedaría fuera de la vista.
const COLUMNS = 2

/** Primer hueco libre de una rejilla que empieza en `origin`, para que un nodo añadido con botón no tape a otro. */
export function freePosition(origin: XYPosition, nodes: Pick<CanvasNode, 'position' | 'measured'>[]): XYPosition {
  const stepX = NODE_SIZE.width + GAP.x
  const stepY = NODE_SIZE.height + GAP.y
  const overlaps = (at: XYPosition) => nodes.some((n) => {
    const width = n.measured?.width ?? NODE_SIZE.width
    const height = n.measured?.height ?? NODE_SIZE.height
    return at.x < n.position.x + width + GAP.x / 2 && n.position.x < at.x + NODE_SIZE.width + GAP.x / 2
      && at.y < n.position.y + height + GAP.y / 2 && n.position.y < at.y + NODE_SIZE.height + GAP.y / 2
  })
  for (let i = 0; i < 100; i++) {
    const at = { x: origin.x + (i % COLUMNS) * stepX, y: origin.y + Math.floor(i / COLUMNS) * stepY }
    if (!overlaps(at)) return at
  }
  return origin
}

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

export function defaultConfig(type: NodeType): FlowNode['config'] {
  switch (type) {
    case 'sampling': return { query: { root: { op: 'and', conditions: [] } }, method: 'aleatorio', size: 100 }
    case 'prompt': return { template: '', model: 'mock-rapido', temperature: 0.2, output: { type: 'texto' } }
    case 'output': return { kind: 'tabla', destination: '' }
  }
}

export function newNode(type: NodeType, position: XYPosition): CanvasNode {
  return { id: temporaryId(), type, position, data: { config: defaultConfig(type) } }
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

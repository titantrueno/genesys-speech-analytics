import { describe, expect, it } from 'vitest'
import { edgeId, freePosition, fromCanvas, isTemporaryId, newNode, remapIds, sameJson, toCanvasEdges, toCanvasNodes } from './graph'
import { CHAINED, nodeId as N } from '../test/flowFixtures'
import type { FlowGraph } from './types'

describe('conversión entre el JSON del flujo y el lienzo', () => {
  it('JSON → lienzo → JSON devuelve exactamente el mismo flujo', () => {
    const nodes = toCanvasNodes(CHAINED)
    const edges = toCanvasEdges(CHAINED)
    expect(nodes.map((n) => [n.id, n.type, n.position])).toEqual(CHAINED.nodes.map((n) => [n.id, n.type, n.position]))
    expect(edges.map((e) => e.id)).toEqual(CHAINED.edges.map(edgeId))
    expect(fromCanvas(nodes, edges)).toEqual(CHAINED)
  })

  it('ignora el estado propio del lienzo (selección, medidas, arrastre)', () => {
    const nodes = toCanvasNodes(CHAINED).map((n) => ({ ...n, selected: true, dragging: false, measured: { width: 220, height: 80 } }))
    const edges = toCanvasEdges(CHAINED).map((e) => ({ ...e, selected: true }))
    expect(fromCanvas(nodes, edges)).toEqual(CHAINED)
  })

  it('crea nodos con clave temporal y configuración inicial', () => {
    const sampling = newNode('sampling', { x: 10, y: 20 })
    expect(isTemporaryId(sampling.id)).toBe(true)
    expect(sampling.id).toMatch(/^tmp-[A-Za-z0-9_-]{1,40}$/)
    expect(newNode('sampling', { x: 0, y: 0 }).id).not.toBe(sampling.id)
    expect(sampling).toMatchObject({ type: 'sampling', position: { x: 10, y: 20 } })
    expect(sampling.data.config).toEqual({ query: { root: { op: 'and', conditions: [] } }, method: 'aleatorio', size: 100 })
    expect(newNode('prompt', { x: 0, y: 0 }).data.config).toEqual({ template: '', provider: 'simulado', model: 'mock-rapido', temperature: 0.2, output: { type: 'texto' } })
    // Un Prompt nuevo toma el proveedor y el modelo por defecto de Configuración › Modelos de IA (FE013).
    expect(newNode('prompt', { x: 0, y: 0 }, { provider: 'gemini', model: 'gemini-3.5-flash-lite' }).data.config)
      .toMatchObject({ provider: 'gemini', model: 'gemini-3.5-flash-lite' })
    expect(newNode('output', { x: 0, y: 0 }).data.config).toEqual({ kind: 'tabla', destination: '' })
    expect(isTemporaryId(N(1))).toBe(false)
  })

  it('sustituye las claves temporales por los identificadores que asigna el backend', () => {
    const graph: FlowGraph = {
      version: 1,
      nodes: [{ ...CHAINED.nodes[0], id: 'tmp-a' }, { ...CHAINED.nodes[1], id: 'tmp-b' }, CHAINED.nodes[2]],
      edges: [{ source: 'tmp-a', target: 'tmp-b' }, { source: 'tmp-b', target: N(3) }],
    }
    const nodes = toCanvasNodes(graph).map((n) => ({ ...n, measured: { width: 200, height: 70 }, selected: n.id === 'tmp-b' }))
    const remapped = remapIds(nodes, toCanvasEdges(graph), { 'tmp-a': N(7), 'tmp-b': N(8) })
    expect(remapped.nodes.map((n) => n.id)).toEqual([N(7), N(8), N(3)])
    expect(remapped.nodes[1]).toMatchObject({ selected: true, measured: { width: 200, height: 70 } })
    expect(remapped.edges.map((e) => [e.id, e.source, e.target])).toEqual([
      [edgeId({ source: N(7), target: N(8) }), N(7), N(8)], [edgeId({ source: N(8), target: N(3) }), N(8), N(3)],
    ])
  })
})

describe('sameJson', () => {
  it('compara sin depender del orden de las claves', () => {
    expect(sameJson({ a: 1, b: { c: [1, { d: 2, e: 3 }] } }, { b: { c: [1, { e: 3, d: 2 }] }, a: 1 })).toBe(true)
    expect(sameJson({ a: 1, b: undefined }, { a: 1 })).toBe(true)
    expect(sameJson({ a: [1, 2] }, { a: [2, 1] })).toBe(false)
    expect(sameJson({ a: 1 }, { a: 1, b: 2 })).toBe(false)
    expect(sameJson({ a: null }, { a: {} })).toBe(false)
    expect(sameJson([], {})).toBe(false)
  })
})

describe('freePosition', () => {
  it('coloca el nodo nuevo en el primer hueco libre sin tapar a otro', () => {
    const origin = { x: 0, y: 0 }
    expect(freePosition(origin, [])).toEqual(origin)
    const first = { position: origin }
    const second = { position: freePosition(origin, [first]) }
    expect(second.position).toEqual({ x: 300, y: 0 })
    expect(freePosition(origin, [first, second])).toEqual({ x: 0, y: 130 })
    // Un nodo más alto de lo normal (medido) también ocupa su hueco.
    const tall = { position: { x: 0, y: 130 }, measured: { width: 240, height: 200 } }
    expect(freePosition(origin, [first, second, tall])).toEqual({ x: 300, y: 130 })
  })
})

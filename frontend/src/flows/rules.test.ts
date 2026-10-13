import { describe, expect, it } from 'vitest'
import cases from './rules.cases.json'
import { connectionRejection } from './rules'
import type { NodeType } from './types'

const types = new Map(cases.nodes.map((n) => [n.id, n.type as NodeType]))

describe('reglas de conexión (casos compartidos con el backend)', () => {
  it.each(cases.cases.map((c) => [c.name, c] as const))('%s', (_, testCase) => {
    const edges = testCase.edges.map(([source, target]) => ({ source, target }))
    const [source, target] = testCase.connect
    const rejection = connectionRejection(types, edges, source, target)
    expect(rejection?.code ?? null).toBe(testCase.expected)
    if (rejection) expect(rejection.message).not.toBe('')
  })

  it('cubren todos los códigos de rechazo', () => {
    expect(new Set(cases.cases.map((c) => c.expected))).toEqual(
      new Set([null, 'invalid_pair', 'self_loop', 'duplicate', 'input_taken', 'output_taken', 'cycle', 'unknown_node']))
  })
})

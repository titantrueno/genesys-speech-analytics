import { describe, expect, it } from 'vitest'
import { explorerSchemaFixture, QUEUE } from '../test/fixtures'
import {
  addCondition, addGroup, changeOperator, decodeQuery, DEFAULT_QUERY, encodeQuery, isComplete, pathFromApi, queryToText, removeNode,
  setGroupOp, updateCondition, type ExplorerQuery, type FieldSchema, type QuerySchema,
} from './queryModel'

const schema = explorerSchemaFixture as QuerySchema

const sample: ExplorerQuery = {
  from: '2026-09-01',
  to: '2026-09-26',
  root: {
    op: 'and',
    conditions: [
      { field: 'channel', operator: 'is', value: 'chat' },
      { op: 'or', conditions: [
        { field: 'sentiment', operator: 'lt', value: -0.3 },
        { field: 'resolution', operator: 'in', value: ['escalada', 'no_resuelta'] },
      ] },
      { field: 'transcript', operator: 'contains', value: '«cancelación» del préstamo', speaker: 'cliente' },
    ],
  },
}

describe('codificación en la URL', () => {
  it('codifica y decodifica sin pérdida, incluidas tildes y comillas', () => {
    const encoded = encodeQuery(sample)
    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/)
    expect(decodeQuery(encoded)).toEqual({ query: sample, error: false })
  })

  it.each(['', null, 'no-es-base64!!', btoa('{"root": 1}'), btoa('no json')])('un q vacío o corrupto (%s) da la consulta por defecto', (value) => {
    const result = decodeQuery(value)
    expect(result.query).toEqual(DEFAULT_QUERY)
    expect(result.error).toBe(Boolean(value))
  })
})

describe('texto legible', () => {
  it('muestra grupos anidados con etiquetas y formato es-ES', () => {
    expect(queryToText(sample, schema)).toBe(
      'Canal es Chat Y (Sentimiento < -0,3 O Resolución es alguno de Escalada, No resuelta) Y Transcripción (cliente) contiene ««cancelación» del préstamo»',
    )
  })

  it('cubre entre, checks, booleanos e identificadores', () => {
    const query: ExplorerQuery = { root: { op: 'and', conditions: [
      { field: 'duration', operator: 'between', value: [60, 300] },
      { field: 'check:verificacion_identidad', operator: 'fails' },
      { field: 'repeat_contact', operator: 'is', value: true },
      { field: 'queue', operator: 'is', value: QUEUE.tarjetas.id },
    ] } }
    expect(queryToText(query, schema)).toBe(
      'Duración (s) entre 60 y 300 Y Verificación de identidad del cliente no cumple Y Recontacto en 7 días es sí Y Cola es Tarjetas',
    )
  })

  it('una consulta vacía se describe como todas las conversaciones', () => {
    expect(queryToText(DEFAULT_QUERY, schema)).toBe('Todas las conversaciones del periodo')
  })
})

describe('edición inmutable por rutas', () => {
  it('añade, actualiza y quita condiciones y grupos sin mutar el original', () => {
    const frozen = structuredClone(sample)
    let q = addCondition(sample, [1], { field: 'duration', operator: 'gt', value: 120 })
    expect(q.root.conditions[1]).toMatchObject({ conditions: [{}, {}, { field: 'duration' }] })
    q = updateCondition(q, [1, 2], { value: 240 })
    expect(q.root.conditions[1]).toMatchObject({ conditions: [{}, {}, { value: 240 }] })
    q = addGroup(q, [], 'or')
    expect(q.root.conditions[3]).toEqual({ op: 'or', conditions: [] })
    q = setGroupOp(q, [1], 'and')
    expect(q.root.conditions[1]).toMatchObject({ op: 'and' })
    q = removeNode(q, [0])
    expect(q.root.conditions).toHaveLength(3)
    expect(sample).toEqual(frozen)
  })

  it('traduce las rutas de error de la API a rutas del modelo', () => {
    expect(pathFromApi('root')).toEqual([])
    expect(pathFromApi('root.conditions[1].conditions[0]')).toEqual([1, 0])
    expect(pathFromApi('from')).toBeNull()
  })
})

describe('«está vacío» (FE012)', () => {
  const field = (type: FieldSchema['type']): FieldSchema => ({
    key: 'f', label: 'Campo', type, operators: [{ key: 'is', label: 'es' }, { key: 'is_empty', label: 'está vacío' }],
    values: [{ value: 'a', label: 'A' }], min: 0, max: 10,
  })

  it('al elegirlo se quita el valor y la condición está completa', () => {
    const changed = changeOperator({ field: 'f', operator: 'is', value: 'a' }, 'is_empty', field('categorical'))
    expect(changed).toEqual({ field: 'f', operator: 'is_empty' })
    expect(isComplete(changed, field('categorical'))).toBe(true)
    expect(isComplete({ field: 'f', operator: 'is_empty' }, field('text'))).toBe(true)
    expect(isComplete({ field: 'f', operator: 'is_empty' }, field('numeric'))).toBe(true)
  })

  it('al volver a un operador con valor se parte del valor por defecto', () => {
    expect(changeOperator({ field: 'f', operator: 'is_empty' }, 'is', field('categorical')))
      .toEqual({ field: 'f', operator: 'is', value: 'a' })
    expect(changeOperator({ field: 'f', operator: 'is_not_empty' }, 'is', field('boolean')))
      .toEqual({ field: 'f', operator: 'is', value: true })
  })

  it('se lee en el texto de la consulta sin valor', () => {
    const schema = { reference_date: '2026-10-12', default_period: { from: '', to: '' }, fields: [field('categorical')] }
    expect(queryToText({ root: { op: 'and', conditions: [{ field: 'f', operator: 'is_empty' }] } }, schema))
      .toBe('Campo está vacío')
  })
})

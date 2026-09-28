import type { Flow, FlowCatalog, FlowGraph } from '../flows/types'
import { fakeId } from './fixtures'

export const nodeId = (n: number) => fakeId('1ND', n)
const N = nodeId

/** Sampling → Prompt (etiqueta) → Prompt encadenado, con una métrica y una tabla. */
export const CHAINED: FlowGraph = {
  version: 1,
  nodes: [
    { id: N(1), type: 'sampling', position: { x: 0, y: 15 }, config: { method: 'aleatorio', size: 40, query: { root: { op: 'and', conditions: [] } } } },
    { id: N(2), type: 'prompt', position: { x: 300, y: 0 }, config: { template: 'Clasifica {{summary}}', model: 'mock-rapido', temperature: 0.2, output: { type: 'etiqueta', labels: ['A', 'B'] } } },
    { id: N(3), type: 'prompt', position: { x: 600, y: 0 }, config: { template: 'Explica {{resultado_anterior}}', model: 'mock-preciso', temperature: 0.5, output: { type: 'texto' } } },
    { id: N(4), type: 'output', position: { x: 600, y: 200.5 }, config: { kind: 'metrica', aggregation: 'recuento', destination: 'reparto' } },
    { id: N(5), type: 'output', position: { x: 900, y: 0 }, config: { kind: 'tabla', destination: 'detalle' } },
  ],
  edges: [
    { source: N(1), target: N(2) }, { source: N(2), target: N(3) }, { source: N(2), target: N(4) }, { source: N(3), target: N(5) },
  ],
}


const options = <T extends string>(entries: Array<[T, string]>) => entries.map(([value, label]) => ({ value, label }))

/** Igual que `GET /api/flows/catalog`. */
export const CATALOG: FlowCatalog = {
  node_types: options([['sampling', 'Sampling'], ['prompt', 'Prompt'], ['output', 'Output']]),
  sampling_methods: options([['aleatorio', 'Aleatorio'], ['estratificado', 'Estratificado'], ['primeros_n', 'Primeros N']]),
  strata: options([['canal', 'Canal'], ['cola', 'Cola'], ['main_topic', 'Main topic']]),
  order_keys: options([['fecha', 'Fecha'], ['duracion', 'Duración'], ['sentimiento', 'Sentimiento'], ['csat', 'CSAT predicho']]),
  orders: options([['desc', 'Descendente'], ['asc', 'Ascendente']]),
  models: options([['mock-rapido', 'Simulado rápido'], ['mock-preciso', 'Simulado preciso']]),
  variables: options([
    ['transcripcion', 'Transcripción completa, turno a turno'], ['summary', 'Summary de la conversación'],
    ['main_topic', 'Main topic de la conversación'], ['metadatos', 'Canal, cola, fecha, duración, sentimiento y resolución'],
    ['resultado_anterior', 'Resultado del prompt anterior (solo en un prompt encadenado)'],
  ]),
  output_formats: options([['texto', 'Texto'], ['etiqueta', 'Etiqueta de una lista'], ['json', 'JSON con esquema']]),
  field_types: options([['texto', 'Texto'], ['numero', 'Número'], ['booleano', 'Booleano']]),
  output_kinds: options([['tabla', 'Tabla de insights por conversación'], ['metrica', 'Métrica agregada'], ['informe', 'Informe resumen']]),
  aggregations: options([['recuento', 'Recuento por etiqueta'], ['porcentaje', '% por etiqueta']]),
  limits: {
    max_sample_size: 1000, max_template: 4000, max_labels: 20, max_label: 60, max_fields: 20, max_field_name: 40,
    max_destination: 80, max_flow_name: 80, max_nodes: 50, max_edges: 100,
  },
}

export const FLOW_ID = fakeId('1FL', 1)

export function flowFixture(graph: FlowGraph = CHAINED): Flow {
  return {
    id: FLOW_ID, name: 'Motivos de fraude', author: { id: fakeId('1US', 3), name: 'Analista Demo' },
    created_at: '2026-09-20T08:00:00+00:00', updated_at: '2026-09-27T10:30:00+00:00', status: 'valido', graph,
  }
}

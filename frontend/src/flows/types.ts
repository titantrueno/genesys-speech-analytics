import type { ConversationListItem } from '../api/conversations'
import type { ExplorerQuery } from '../explorer/queryModel'

export type NodeType = 'sampling' | 'prompt' | 'output'
export type SamplingMethod = 'aleatorio' | 'estratificado' | 'primeros_n'
export type Stratum = 'canal' | 'cola' | 'main_topic'
export type OrderKey = 'fecha' | 'duracion' | 'sentimiento' | 'csat'
export type OutputFormatType = 'texto' | 'etiqueta' | 'json'
export type FieldType = 'texto' | 'numero' | 'booleano'
export type OutputKind = 'tabla' | 'metrica' | 'informe'
export type Aggregation = 'recuento' | 'porcentaje'

export interface SamplingConfig {
  query?: ExplorerQuery
  method?: SamplingMethod
  stratify_by?: Stratum
  order_by?: OrderKey
  order?: 'asc' | 'desc'
  size?: number
}

export interface SchemaField { name: string; type: FieldType }

export interface OutputFormat {
  type: OutputFormatType
  labels?: string[]
  fields?: SchemaField[]
}

export interface PromptConfig {
  template?: string
  model?: string
  temperature?: number
  output?: OutputFormat
}

export interface OutputConfig {
  kind?: OutputKind
  aggregation?: Aggregation
  destination?: string
}

interface BaseNode<T extends NodeType, C> {
  id: string
  type: T
  position: { x: number; y: number }
  config: C
}

export type FlowNode =
  | BaseNode<'sampling', SamplingConfig>
  | BaseNode<'prompt', PromptConfig>
  | BaseNode<'output', OutputConfig>

/** Tipo y configuración de un nodo, conservando la relación entre ambos. */
export type NodeContent = { [K in NodeType]: Pick<Extract<FlowNode, { type: K }>, 'type' | 'config'> }[NodeType]

export interface FlowEdge { source: string; target: string }

/** Formato JSON del flujo (versión 1), igual que `backend/app/flows/model.py`. */
export interface FlowGraph {
  version: 1
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export type FlowStatus = 'valido' | 'con_errores'
export type RunStatus = 'pendiente' | 'en_curso' | 'ok' | 'error'

export interface Person { id: string; name: string }

export interface FlowSummary {
  id: string
  name: string
  author: Person
  created_at: string
  updated_at: string
  status: FlowStatus
  last_run: { id: string; created_at: string; status: RunStatus } | null
}

export interface Flow extends Omit<FlowSummary, 'last_run'> {
  graph: FlowGraph
}

export interface Issue {
  code: string
  message: string
  node_id: string | null
  /** `warning` avisa sin impedir la ejecución (FE012); sin él, es un error. */
  severity?: 'error' | 'warning'
}

export interface Option<T extends string = string> { value: T; label: string }

export interface FlowCatalog {
  node_types: Option<NodeType>[]
  sampling_methods: Option<SamplingMethod>[]
  strata: Option<Stratum>[]
  order_keys: Option<OrderKey>[]
  orders: Option<'asc' | 'desc'>[]
  models: Option[]
  /** Modelo que toma un nodo Prompt nuevo (Configuración › Modelos de IA). */
  default_model: string
  variables: Option[]
  output_formats: Option<OutputFormatType>[]
  field_types: Option<FieldType>[]
  output_kinds: Option<OutputKind>[]
  aggregations: Option<Aggregation>[]
  limits: Record<'max_sample_size' | 'max_template' | 'max_labels' | 'max_label' | 'max_fields' | 'max_field_name'
    | 'max_destination' | 'max_flow_name' | 'max_nodes' | 'max_edges', number>
}

export interface NodeState {
  status: RunStatus
  processed: number
  total: number | null
  message: string | null
}

export interface RunSummary {
  id: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  status: RunStatus
  sample_size: number | null
  user: Person
}

export interface TableResult { rows: Array<{ conversation: ConversationListItem; result: unknown }> }
export interface MetricResult { aggregation: Aggregation; total: number; items: Array<{ label: string; count: number; percent: number }> }
export interface ReportResult { text: string }

export type RunOutput =
  | { node_id: string; kind: 'tabla'; destination: string; result: TableResult }
  | { node_id: string; kind: 'metrica'; destination: string; result: MetricResult }
  | { node_id: string; kind: 'informe'; destination: string; result: ReportResult }

export interface Run extends RunSummary {
  flow_id: string
  seed: number
  graph: FlowGraph
  nodes: Record<string, NodeState>
  outputs: Record<string, RunOutput>
}

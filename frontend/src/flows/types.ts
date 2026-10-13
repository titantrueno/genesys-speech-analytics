import type { ConversationListItem } from '../api/conversations'
import type { DownloadChannel, DownloadCounters, DownloadInterval, DownloadRunStatus, DownloadSchedule } from '../downloads/types'
import type { ExplorerQuery } from '../explorer/queryModel'

export type NodeType = 'descarga' | 'sampling' | 'prompt' | 'output'
export type SamplingMethod = 'aleatorio' | 'estratificado' | 'primeros_n'
export type Stratum = 'canal' | 'cola' | 'main_topic'
export type OrderKey = 'fecha' | 'duracion' | 'sentimiento' | 'csat'
export type OutputFormatType = 'texto' | 'etiqueta' | 'json'
export type FieldType = 'texto' | 'numero' | 'booleano' | 'lista'
export type OutputKind = 'tabla' | 'metrica' | 'informe' | 'campo'
/** Campo del análisis que escribe un Output «campo» (FE013). */
/** Campo destino de «Guardar en campos» (FE013 y FE014): uno del análisis, un check (`compliance:<código>`) o una entidad. */
export type AnalysisTarget = 'summary' | 'main_topic' | 'resolution' | 'csat' | 'effort' | 'churn_risk' | 'sentiment'
  | 'secondary_topics' | 'keywords'
export type TargetField = AnalysisTarget | `compliance:${string}` | `entity:${string}`
export type TargetGroup = 'analisis' | 'cumplimiento' | 'entidades'
export interface TargetOption extends Option<TargetField> { group: TargetGroup }
export type Aggregation = 'recuento' | 'porcentaje'

/** Caja «Genesys download» (FE017): la configuración de un flujo de descarga, sin nombre ni zona horaria. */
export interface DownloadConfig {
  interval?: DownloadInterval
  channels?: DownloadChannel[]
  overwrite?: boolean
  schedule?: DownloadSchedule
  active?: boolean
}

export interface SamplingConfig {
  query?: ExplorerQuery
  method?: SamplingMethod
  stratify_by?: Stratum
  order_by?: OrderKey
  order?: 'asc' | 'desc'
  /** Un número, o «All conversations» (`'all'`, FE017): todas las que cumplen los filtros. */
  size?: number | 'all'
}

export interface SchemaField {
  name: string
  type: FieldType
  /** Valores permitidos de un campo de texto (FE013): el LLM los recibe como `enum`. */
  options?: string[]
}

export interface OutputFormat {
  type: OutputFormatType
  labels?: string[]
  fields?: SchemaField[]
}

export interface PromptConfig {
  template?: string
  /** Sin proveedor, el nodo es simulado (flujos guardados antes de FE013). */
  provider?: string
  model?: string
  temperature?: number
  output?: OutputFormat
}

/** Un campo destino y de dónde sale: la respuesta entera (sin `source`) o un campo del JSON del Prompt. */
export interface FieldMapping { target: TargetField; source?: string }

export interface OutputConfig {
  kind?: OutputKind
  aggregation?: Aggregation
  destination?: string
  /** Solo en `campo` (FE013). */
  mappings?: FieldMapping[]
  overwrite?: boolean
}

interface BaseNode<T extends NodeType, C> {
  id: string
  type: T
  position: { x: number; y: number }
  config: C
}

export type FlowNode =
  | BaseNode<'descarga', DownloadConfig>
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
/** `omitido` (FE017): el nodo no se ejecuta porque la descarga de la caja no trajo conversaciones. */
export type NodeStatus = RunStatus | 'omitido'
export type RunOrigin = 'manual' | 'programada'

export interface Person { id: string; name: string }

export interface FlowSummary {
  id: string
  name: string
  author: Person
  created_at: string
  updated_at: string
  status: FlowStatus
  last_run: { id: string; created_at: string; status: RunStatus } | null
  /** Próxima ejecución de un flujo con caja «Genesys download» programada y activa (FE017). */
  next_run: string | null
}

export interface Flow extends Omit<FlowSummary, 'last_run' | 'next_run'> {
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
  /** Proveedores con sus modelos; el primer modelo es el que se propone al elegir el proveedor (FE013). */
  providers: Array<Option & { models: Array<Option & { temperature: boolean }> }>
  /** Proveedor y modelo que toma un nodo Prompt nuevo (Configuración › Modelos de IA). */
  default_provider: string
  default_model: string
  variables: Option[]
  output_formats: Option<OutputFormatType>[]
  field_types: Option<FieldType>[]
  output_kinds: Option<OutputKind>[]
  /** Campos destino de un Output «campo» (FE013). */
  target_fields: TargetOption[]
  /** Plantillas para crear un flujo ya configurado (FE013). */
  templates: Option[]
  /** Origen de datos activo: un Output «campo» solo se ejecuta con `real`. */
  origin: 'sintetico' | 'real'
  aggregations: Option<Aggregation>[]
  limits: Record<'max_sample_size' | 'max_template' | 'max_labels' | 'max_label' | 'max_fields' | 'max_field_name'
    | 'max_mappings' | 'max_destination' | 'max_flow_name' | 'max_nodes' | 'max_edges', number>
}

export interface NodeState {
  status: NodeStatus
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
  /** Lanzada a mano o por el programador (FE017). */
  origin: RunOrigin
}

export interface TableResult { rows: Array<{ conversation: ConversationListItem; result: unknown }> }
export interface MetricResult { aggregation: Aggregation; total: number; items: Array<{ label: string; count: number; percent: number }> }
export interface ReportResult { text: string }
export type FieldState = 'escrito' | 'omitido' | 'rechazado' | 'sin_valor' | 'error'
/** Valor ya validado que se guarda: texto, número, lista de textos o el resultado de un check (`null`, «no aplica»). */
export type FieldValue = string | number | boolean | null | string[]
export interface FieldsResult {
  targets: TargetField[]
  rows: Array<{ conversation: ConversationListItem; values: Partial<Record<TargetField, FieldValue>>
    states: Partial<Record<TargetField, FieldState>>
    /** Por qué falló la conversación entera (Prompt rechazado, no encontrada). */
    reason: string | null
    /** Por qué no se guardó un campo (FE014): valor rechazado, ya tenía valor, Genesys ya da el sentimiento. */
    reasons?: Partial<Record<TargetField, string>> }>
  counts: Partial<Record<TargetField, Partial<Record<FieldState, number>>>>
}

export type RunOutput =
  | { node_id: string; kind: 'tabla'; destination: string; result: TableResult }
  | { node_id: string; kind: 'metrica'; destination: string; result: MetricResult }
  | { node_id: string; kind: 'informe'; destination: string; result: ReportResult }
  | { node_id: string; kind: 'campo'; destination: string; result: FieldsResult }

export interface Run extends RunSummary {
  flow_id: string
  seed: number
  graph: FlowGraph
  nodes: Record<string, NodeState>
  outputs: Record<string, RunOutput>
  /** Programadas omitidas o errores de validación de una programada que no pudo arrancar (FE017). */
  notes: string[]
  /** Descarga de la caja «Genesys download» (FE017); `null` sin caja. */
  download: RunDownload | null
}

export interface RunDownload {
  node_id: string
  run_id: string
  status: DownloadRunStatus
  counters: DownloadCounters
  error: string | null
}

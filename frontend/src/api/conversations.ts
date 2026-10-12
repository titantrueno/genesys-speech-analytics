import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiRequest } from './client'
import type { MetricsFilters } from './metrics'

export type Channel = 'voz' | 'chat'
export type Resolution = 'resuelta' | 'no_resuelta' | 'escalada'
export type SortKey = 'date' | 'duration' | 'sentiment'
export type SortOrder = 'asc' | 'desc'

export type TranscriptQuality = 'completa' | 'parcial' | 'sin_transcripcion'

export interface ConversationListItem {
  id: string
  started_at: string
  channel: Channel
  /** Sin cola o sin agente en las conversaciones reales que no pasaron por ellos (FE012). */
  queue_id: string | null
  queue: string | null
  agent_id: string | null
  agent: string | null
  main_topic: string | null
  main_topic_label: string | null
  summary: string
  sentiment: number | null
  resolution: Resolution | null
  csat: number | null
  duration_s: number
  /** Conversación real sin el análisis de la plataforma (FE012). */
  analysis_pending: boolean
  /** Solo en conversaciones reales; `null` en las sintéticas. */
  ani: string | null
  external_tag: string | null
  contained_in_bot: boolean | null
  transcript_quality: TranscriptQuality | null
}

export interface ConversationList {
  total: number
  page: number
  page_size: number
  pages: number
  items: ConversationListItem[]
}

export interface ConversationQuery extends MetricsFilters {
  resolution: string[]
  churn_risk: string[]
  sentiment_lt?: string
  compliant?: string
  repeat_contact?: string
  /** Búsqueda exacta por ANI (con o sin +34) y por `externalTag` en conversaciones reales (FE012). */
  phone?: string
  external_tag?: string
  page: number
  page_size: number
  sort: SortKey
  order: SortOrder
}

export function useConversations(query: ConversationQuery) {
  return useQuery({
    queryKey: ['conversations', query],
    queryFn: ({ signal }) => apiRequest<ConversationList>('/api/conversations', { query: { ...query }, signal }),
    placeholderData: keepPreviousData,
  })
}

export interface Turn {
  speaker: 'cliente' | 'agente' | 'bot' | 'sistema'
  text: string
  offset_s: number
  sentiment: number | null
  /** `false`: mensaje de chat que Genesys no llegó a entregar; conserva su texto. */
  delivered?: boolean
}

export interface GenesysSegment {
  seq: number
  kind: 'cliente' | 'flujo_entrada' | 'ivr' | 'cola' | 'agente' | 'externo'
  name: string | null
  started_at: string
  ended_at: string | null
  disconnect_type: string | null
  exit_reason: string | null
  transfer_target: string | null
  queue: { id: string; genesys_id: string; name: string } | null
  agent: { id: string; genesys_id: string; name: string } | null
  flow: { id: string; name: string; type: string | null } | null
  wrapup: { id: string; name: string } | null
}

export interface GenesysTopic {
  seq: number
  topic_id: string
  name: string
  phrase: string | null
  speaker: Turn['speaker'] | null
  turn_seq: number | null
  offset_s: number | null
  confidence: number | null
}

/** Analítica de Genesys de una conversación real (FE011); `metrics` no trae las métricas que el canal no tiene. */
export interface GenesysInfo {
  genesys_id: string
  direction: string | null
  ani: string | null
  dnis: string | null
  external_tag: string | null
  transcript_quality: TranscriptQuality
  disconnect_type: string | null
  transferred: boolean
  reconnected: boolean
  contained_in_bot: boolean
  derived_to_agent: boolean
  abandoned_in_queue: boolean
  undelivered_messages: number
  customer_sentiment: number | null
  mos: number | null
  metrics: Record<string, unknown>
  segments: GenesysSegment[]
  topics: GenesysTopic[]
  divisions: Array<{ id: string; name: string }>
}

export interface ConversationDetail {
  id: string
  channel: Channel
  started_at: string
  duration_s: number
  queue_id: string | null
  queue: string | null
  agent_id: string | null
  agent: string | null
  customer_id: string | null
  main_topic_label: string | null
  turns: Turn[]
  analysis: {
    summary: string
    main_topic: string | null
    secondary_topics: string[]
    sentiment: number | null
    sentiment_timeline: number[]
    resolution: Resolution | null
    csat: number | null
    effort: number | null
    churn_risk: 'bajo' | 'medio' | 'alto' | null
    compliance: Record<string, boolean | null>
    entities: Array<{ type: 'importe' | 'producto' | 'fecha' | 'comercio'; value: string }>
    keywords: string[]
    /** Sin el análisis de la plataforma (conversaciones reales, FE012): los campos que faltan son `null` o vacíos. */
    pending?: boolean
  }
  /** Solo en conversaciones reales. */
  genesys?: GenesysInfo | null
}

export function useConversation(id: string) {
  return useQuery({
    queryKey: ['conversation', id],
    queryFn: ({ signal }) => apiRequest<ConversationDetail>(`/api/conversations/${encodeURIComponent(id)}`, { signal }),
  })
}

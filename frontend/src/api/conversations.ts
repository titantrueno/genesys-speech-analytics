import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiRequest } from './client'
import type { MetricsFilters } from './metrics'

export type Channel = 'voz' | 'chat'
export type Resolution = 'resuelta' | 'no_resuelta' | 'escalada'
export type SortKey = 'date' | 'duration' | 'sentiment'
export type SortOrder = 'asc' | 'desc'

export interface ConversationListItem {
  id: string
  started_at: string
  channel: Channel
  queue_id: string
  queue: string
  agent_id: string
  agent: string
  main_topic: string
  main_topic_label: string
  summary: string
  sentiment: number
  resolution: Resolution
  csat: number
  duration_s: number
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
  sentiment: number
}

export interface ConversationDetail {
  id: string
  channel: Channel
  started_at: string
  duration_s: number
  queue_id: string
  queue: string
  agent_id: string
  agent: string
  customer_id: string
  main_topic_label: string
  turns: Turn[]
  analysis: {
    summary: string
    main_topic: string
    secondary_topics: string[]
    sentiment: number
    sentiment_timeline: number[]
    resolution: Resolution
    csat: number
    effort: number
    churn_risk: 'bajo' | 'medio' | 'alto'
    compliance: Record<string, boolean | null>
    entities: Array<{ type: 'importe' | 'producto' | 'fecha' | 'comercio'; value: string }>
    keywords: string[]
  }
}

export function useConversation(id: string) {
  return useQuery({
    queryKey: ['conversation', id],
    queryFn: ({ signal }) => apiRequest<ConversationDetail>(`/api/conversations/${encodeURIComponent(id)}`, { signal }),
  })
}

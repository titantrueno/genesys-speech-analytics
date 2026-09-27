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
  queue: string
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

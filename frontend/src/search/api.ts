import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiRequest } from '../api/client'
import type { Channel, ConversationListItem, Turn } from '../api/conversations'
import type { Period } from '../api/metrics'

export type SearchGroup = 'conversation' | 'fragment'

export interface SearchParams {
  q: string
  from?: string
  to?: string
  channel?: Channel
  queue: string[]
  min_score: number
  group: SearchGroup
}

export interface SearchResult {
  conversation_id: string
  start_turn: number
  end_turn: number
  score: number
  turns: Array<{ index: number; speaker: Exclude<Turn['speaker'], 'sistema'>; text: string }>
  highlights: string[]
  conversation: ConversationListItem
}

export interface SearchResponse {
  query: string
  expansions: string[]
  period: Period
  total: number
  max_score: number | null
  results: SearchResult[]
}

export const RESULT_LIMIT = 50

export function useSemanticSearch(params: SearchParams | null) {
  return useQuery({
    queryKey: ['search', 'semantic', params],
    queryFn: ({ signal }) => apiRequest<SearchResponse>('/api/search/semantic', {
      query: {
        ...params!,
        min_score: params!.min_score > 0 ? params!.min_score : undefined,
        group: params!.group === 'fragment' ? 'fragment' : undefined,
        limit: RESULT_LIMIT,
      },
      signal,
    }),
    enabled: params !== null,
    placeholderData: keepPreviousData,
    retry: false,
  })
}

import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '../api/client'
import type { QuerySchema } from './queryModel'

export interface Suggestion { value: string; label: string; count: number }

export function useQuerySchema() {
  return useQuery({
    queryKey: ['query-schema'],
    queryFn: ({ signal }) => apiRequest<QuerySchema>('/api/query/schema', { signal }),
    staleTime: Infinity,
  })
}

export function useSuggestions(field: string, from: string | undefined, to: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ['query-suggest', field, from, to],
    queryFn: ({ signal }) => apiRequest<{ values: Suggestion[] }>('/api/query/suggest', { query: { field, from, to }, signal }),
    enabled,
    staleTime: 60_000,
  })
}

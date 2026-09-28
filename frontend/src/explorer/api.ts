import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '../api/client'
import type { ExplorerQuery, QuerySchema } from './queryModel'

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

export interface SavedQuery {
  id: string
  name: string
  query: ExplorerQuery
  created_at: string
  updated_at: string
}

const SAVED_KEY = ['saved-queries']

export function useSavedQueries() {
  return useQuery({
    queryKey: SAVED_KEY,
    queryFn: ({ signal }) => apiRequest<{ items: SavedQuery[] }>('/api/query/saved', { signal }),
  })
}

export function useSavedQueryMutations() {
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: SAVED_KEY })
  return {
    create: useMutation({
      mutationFn: (body: { name: string; query: ExplorerQuery }) =>
        apiRequest<SavedQuery>('/api/query/saved', { method: 'POST', body }),
      onSuccess: refresh,
    }),
    rename: useMutation({
      mutationFn: ({ id, name }: { id: string; name: string }) =>
        apiRequest<SavedQuery>(`/api/query/saved/${id}`, { method: 'PATCH', body: { name } }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (id: string) => apiRequest<void>(`/api/query/saved/${id}`, { method: 'DELETE' }),
      onSuccess: refresh,
    }),
  }
}

export function useInterpret() {
  return useMutation({
    mutationFn: (text: string) =>
      apiRequest<{ query: ExplorerQuery; unrecognized: string[] }>('/api/query/interpret', { method: 'POST', body: { text } }),
  })
}

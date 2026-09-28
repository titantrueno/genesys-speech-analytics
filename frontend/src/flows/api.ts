import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '../api/client'
import type { Flow, FlowSummary } from './types'

const FLOWS_KEY = ['flows']

export const flowKey = (id: string) => ['flow', id]

export function useFlows() {
  return useQuery({
    queryKey: FLOWS_KEY,
    queryFn: ({ signal }) => apiRequest<{ items: FlowSummary[] }>('/api/flows', { signal }),
    staleTime: 0,
  })
}

export function useFlowMutations() {
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: FLOWS_KEY })
  return {
    create: useMutation({
      mutationFn: (name: string) => apiRequest<Flow>('/api/flows', { method: 'POST', body: { name } }),
      onSuccess: refresh,
    }),
    duplicate: useMutation({
      mutationFn: (id: string) => apiRequest<Flow>(`/api/flows/${id}/duplicate`, { method: 'POST' }),
      onSuccess: refresh,
    }),
    rename: useMutation({
      mutationFn: ({ id, name }: { id: string; name: string }) =>
        apiRequest<Flow>(`/api/flows/${id}`, { method: 'PATCH', body: { name } }),
      onSuccess: (flow) => {
        client.setQueryData(flowKey(flow.id), flow)
        return refresh()
      },
    }),
    remove: useMutation({
      mutationFn: (id: string) => apiRequest<void>(`/api/flows/${id}`, { method: 'DELETE' }),
      onSuccess: refresh,
    }),
  }
}

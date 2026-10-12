import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '../api/client'
import type { ExplorerQuery } from '../explorer/queryModel'
import type { Flow, FlowCatalog, FlowGraph, FlowSummary, Issue, Run, RunSummary } from './types'

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
      mutationFn: (body: { name: string; template?: string }) => apiRequest<Flow>('/api/flows', { method: 'POST', body }),
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

export function useFlow(id: string) {
  return useQuery({
    queryKey: flowKey(id),
    queryFn: ({ signal }) => apiRequest<Flow>(`/api/flows/${id}`, { signal }),
    staleTime: 0,
    gcTime: 0,
  })
}

export function useFlowCatalog() {
  return useQuery({
    queryKey: ['flow-catalog'],
    queryFn: ({ signal }) => apiRequest<FlowCatalog>('/api/flows/catalog', { signal }),
    staleTime: Infinity,
  })
}

export function useSaveGraph(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (graph: FlowGraph) =>
      apiRequest<Flow & { id_map: Record<string, string> }>(`/api/flows/${id}/graph`, { method: 'PUT', body: graph }),
    onSuccess: () => client.invalidateQueries({ queryKey: FLOWS_KEY }),
  })
}

/** Validación del grafo actual, aunque no esté guardado; cada grafo tiene su propia clave, así que una respuesta antigua no pisa a la nueva. */
export function useValidation(graph: FlowGraph, enabled: boolean) {
  return useQuery({
    queryKey: ['flow-validate', graph],
    queryFn: ({ signal }) => apiRequest<{ valid: boolean; issues: Issue[] }>('/api/flows/validate', { method: 'POST', body: graph, signal }),
    enabled,
    staleTime: Infinity,
  })
}

export function useStartRun(id: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => apiRequest<Run>(`/api/flows/${id}/runs`, { method: 'POST' }),
    onSettled: () => {
      client.invalidateQueries({ queryKey: FLOWS_KEY })
      client.invalidateQueries({ queryKey: ['flow-runs', id] })
    },
  })
}

export interface Estimate { available: number; sample_size: number | null; period: { from: string; to: string } }

export function useEstimate(query: ExplorerQuery | undefined, size: number | undefined) {
  return useQuery({
    queryKey: ['flow-estimate', query, size],
    queryFn: ({ signal }) => apiRequest<Estimate>('/api/flows/sampling/estimate', { method: 'POST', body: { query, size }, signal }),
    enabled: query !== undefined,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

export const RUN_POLL_MS = 500
const isActive = (run: Run | undefined) => run?.status === 'pendiente' || run?.status === 'en_curso'

export function useRuns(flowId: string) {
  return useQuery({
    queryKey: ['flow-runs', flowId],
    queryFn: ({ signal }) => apiRequest<{ items: RunSummary[] }>(`/api/flows/${flowId}/runs`, { signal }),
    staleTime: 0,
  })
}

/** Detalle de una ejecución; mientras no termina se consulta cada medio segundo (el progreso llega por polling). */
export function useRun(flowId: string, runId: string) {
  return useQuery({
    queryKey: ['flow-run', flowId, runId],
    queryFn: ({ signal }) => apiRequest<Run>(`/api/flows/${flowId}/runs/${runId}`, { signal }),
    refetchInterval: (query) => (isActive(query.state.data) ? RUN_POLL_MS : false),
    staleTime: 0,
  })
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '../api/client'
import type { DownloadFlow, DownloadFlowInput } from './types'

export const DOWNLOAD_FLOWS_KEY = ['download-flows']
export const downloadFlowKey = (id: string) => ['download-flow', id]

/** Sin reintentos: si el servicio de ingesta no responde (503), el listado de flujos lo dice al momento. */
export function useDownloadFlows(enabled = true) {
  return useQuery({
    queryKey: DOWNLOAD_FLOWS_KEY,
    queryFn: ({ signal }) => apiRequest<{ items: DownloadFlow[] }>('/api/download-flows', { signal }),
    staleTime: 0,
    retry: false,
    enabled,
  })
}

export function useDownloadFlow(id: string) {
  return useQuery({
    queryKey: downloadFlowKey(id),
    queryFn: ({ signal }) => apiRequest<DownloadFlow>(`/api/download-flows/${id}`, { signal }),
    staleTime: 0,
    retry: false,
  })
}

export function useDownloadMutations() {
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: DOWNLOAD_FLOWS_KEY })
  return {
    create: useMutation({
      mutationFn: (body: DownloadFlowInput) => apiRequest<DownloadFlow>('/api/download-flows', { method: 'POST', body }),
      onSuccess: refresh,
    }),
    update: useMutation({
      mutationFn: ({ id, body }: { id: string; body: DownloadFlowInput }) =>
        apiRequest<DownloadFlow>(`/api/download-flows/${id}`, { method: 'PUT', body }),
      onSuccess: (flow) => {
        client.setQueryData(downloadFlowKey(flow.id), flow)
        return refresh()
      },
    }),
    remove: useMutation({
      mutationFn: (id: string) => apiRequest<void>(`/api/download-flows/${id}`, { method: 'DELETE' }),
      onSuccess: refresh,
    }),
  }
}

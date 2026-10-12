import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { API_URL, ApiError, apiRequest, tokenStorage } from '../api/client'
import type {
  DownloadFlow, DownloadFlowInput, DownloadRun, DownloadRunStatus, GenesysConnector, GenesysTest, LogEntry, LogLevel,
} from './types'

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

export const DOWNLOAD_POLL_MS = 2000
const ACTIVE: DownloadRunStatus[] = ['pendiente', 'en_curso']
export const isActive = (status: DownloadRunStatus | undefined) => status !== undefined && ACTIVE.includes(status)
const runsKey = (flowId: string) => ['download-runs', flowId]

export function useStartDownload(flowId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => apiRequest<DownloadRun>(`/api/download-flows/${flowId}/runs`, { method: 'POST' }),
    onSettled: () => {
      client.invalidateQueries({ queryKey: DOWNLOAD_FLOWS_KEY })
      client.invalidateQueries({ queryKey: runsKey(flowId) })
    },
  })
}

/** Historial; mientras alguna ejecución sigue activa, se refresca cada 2 s. */
export function useDownloadRuns(flowId: string) {
  return useQuery({
    queryKey: runsKey(flowId),
    queryFn: ({ signal }) => apiRequest<{ items: DownloadRun[] }>(`/api/download-flows/${flowId}/runs`, { signal }),
    refetchInterval: (query) => (query.state.data?.items.some((run) => isActive(run.status)) ? DOWNLOAD_POLL_MS : false),
    staleTime: 0,
    retry: false,
  })
}

/** Estado y contadores de una ejecución; se consulta cada 2 s hasta que termina. */
export function useDownloadRun(flowId: string, runId: string) {
  return useQuery({
    queryKey: ['download-run', flowId, runId],
    queryFn: ({ signal }) => apiRequest<DownloadRun>(`/api/download-flows/${flowId}/runs/${runId}`, { signal }),
    refetchInterval: (query) => (isActive(query.state.data?.status) ? DOWNLOAD_POLL_MS : false),
    staleTime: 0,
    retry: false,
  })
}

/**
 * Log de una ejecución, cargado por tramos: cada consulta pide solo las entradas posteriores a la última (`after`) y las
 * añade a las que ya tiene. Con `polling`, cada 2 s.
 */
export function useDownloadLog(flowId: string, runId: string, level: LogLevel | null, polling: boolean) {
  const client = useQueryClient()
  const key = ['download-log', flowId, runId, level]
  return useQuery({
    queryKey: key,
    queryFn: async ({ signal }) => {
      const previous = client.getQueryData<LogEntry[]>(key) ?? []
      const { items } = await apiRequest<{ items: LogEntry[] }>(`/api/download-flows/${flowId}/runs/${runId}/log`, {
        query: { after: previous.at(-1)?.id ?? 0, level }, signal,
      })
      return [...previous, ...items]
    },
    refetchInterval: polling ? DOWNLOAD_POLL_MS : false,
    staleTime: 0,
  })
}

/** Descarga el log completo en texto (`format=text`) como fichero, con la sesión actual. */
export async function downloadLogFile(flowId: string, runId: string): Promise<void> {
  const token = tokenStorage.get()
  const response = await fetch(`${API_URL}/api/download-flows/${flowId}/runs/${runId}/log?format=text`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) throw new ApiError(response.status, `Error ${response.status}`)
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `log-${runId}.txt`
  anchor.click()
  URL.revokeObjectURL(url)
}

export function useGenesysConnector() {
  return useQuery({
    queryKey: ['genesys-connector'],
    queryFn: ({ signal }) => apiRequest<GenesysConnector>('/api/config/connectors/genesys', { signal }),
    retry: false,
  })
}

export function useTestGenesys() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => apiRequest<GenesysTest>('/api/config/connectors/genesys/test', { method: 'POST' }),
    onSettled: () => client.invalidateQueries({ queryKey: ['genesys-connector'] }),
  })
}

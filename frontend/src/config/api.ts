import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiRequest } from '../api/client'
import type {
  AuditEntry, CheckInput, GeneralConfig, ComplianceCheck, Connector, FieldIssue, PlatformConfig, SectionCode, Taxonomy, Topic, TopicInput, TopicKind,
} from './types'

export const CONFIG_KEY = ['config']

export function useConfig(enabled = true) {
  return useQuery({
    queryKey: CONFIG_KEY,
    queryFn: ({ signal }) => apiRequest<PlatformConfig>('/api/config', { signal }),
    staleTime: 60_000,
    enabled,
  })
}

export const DEFAULT_PLATFORM_NAME = 'Speech & Text Analytics'

/** Nombre, zona horaria e idioma: sin sesión (login) y para todos los roles. */
export function usePublicConfig() {
  return useQuery({
    queryKey: ['config-public'],
    queryFn: ({ signal }) => apiRequest<GeneralConfig>('/api/config/public', { signal }),
    staleTime: 60_000,
    retry: false,
  })
}

export function useConnectors() {
  return useQuery({
    queryKey: ['config-connectors'],
    queryFn: ({ signal }) => apiRequest<{ items: Connector[] }>('/api/config/connectors', { signal }),
  })
}

export function useAudit(section: SectionCode) {
  return useQuery({
    queryKey: ['config-audit', section],
    queryFn: ({ signal }) => apiRequest<{ items: AuditEntry[] }>('/api/config/audit', { query: { section }, signal }),
  })
}

export function useTaxonomy() {
  return useQuery({
    queryKey: ['config-taxonomy'],
    queryFn: ({ signal }) => apiRequest<Taxonomy>('/api/config/taxonomy', { signal }),
  })
}

export function useChecks() {
  return useQuery({
    queryKey: ['config-checks'],
    queryFn: ({ signal }) => apiRequest<{ items: ComplianceCheck[] }>('/api/config/compliance-checks', { signal }),
  })
}

/**
 * Escritura de configuración. Un cambio puede afectar a cualquier sección (catálogos, métricas, fechas, enmascarado,
 * campos del explorador), así que al guardar se invalidan todas las consultas en caché.
 */
export function useConfigMutation<TBody, TResult = unknown>(request: (body: TBody) => Promise<TResult>) {
  const client = useQueryClient()
  return useMutation({ mutationFn: request, onSuccess: () => client.invalidateQueries() })
}

export const configRequests = {
  general: (body: unknown) => apiRequest<PlatformConfig>('/api/config/general', { method: 'PUT', body }),
  privacy: (body: unknown) => apiRequest<PlatformConfig>('/api/config/privacy', { method: 'PUT', body }),
  ai: (body: unknown) => apiRequest<PlatformConfig>('/api/config/ai', { method: 'PUT', body }),
  sync: (id: string) => apiRequest<Connector>(`/api/config/connectors/${id}/sync`, { method: 'POST' }),
  kpi: ({ code, ...body }: { code: string } & Record<string, unknown>) =>
    apiRequest<PlatformConfig>(`/api/config/kpis/${code}`, { method: 'PUT', body }),
  createTopic: ({ kind, body }: { kind: TopicKind; body: TopicInput }) =>
    apiRequest<Topic>(`/api/config/taxonomy/${kind}`, { method: 'POST', body }),
  updateTopic: ({ kind, id, body }: { kind: TopicKind; id: string; body: TopicInput }) =>
    apiRequest<Topic>(`/api/config/taxonomy/${kind}/${id}`, { method: 'PUT', body }),
  deleteTopic: ({ kind, id }: { kind: TopicKind; id: string }) =>
    apiRequest<void>(`/api/config/taxonomy/${kind}/${id}`, { method: 'DELETE' }),
  createCheck: (body: CheckInput) => apiRequest<ComplianceCheck>('/api/config/compliance-checks', { method: 'POST', body }),
  updateCheck: ({ id, body }: { id: string; body: CheckInput }) =>
    apiRequest<ComplianceCheck>(`/api/config/compliance-checks/${id}`, { method: 'PUT', body }),
  deleteCheck: (id: string) => apiRequest<void>(`/api/config/compliance-checks/${id}`, { method: 'DELETE' }),
}

/** Primer error de un campo o de alguno de sus elementos (`keywords`, `keywords.0`…). */
export function errorFor(errors: Record<string, string>, field: string): string | undefined {
  return errors[field] ?? Object.entries(errors).find(([key]) => key.startsWith(`${field}.`))?.[1]
}

/** Errores por campo de una respuesta `422` (clave: último elemento de la ruta, o `campo.índice` en listas). */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.status !== 422 || !Array.isArray(error.detail)) return {}
  const result: Record<string, string> = {}
  for (const issue of error.detail as FieldIssue[]) {
    const path = issue.loc.filter((part) => part !== 'body')
    const key = path.map(String).join('.')
    if (key && !(key in result)) result[key] = issue.msg
  }
  return result
}

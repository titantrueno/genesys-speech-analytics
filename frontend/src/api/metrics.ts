import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiRequest } from './client'

export type KpiCode =
  | 'volume' | 'aht_s' | 'sentiment_avg' | 'negative_pct' | 'resolution_rate' | 'escalation_rate' | 'fcr_rate'
  | 'csat_avg' | 'effort_avg' | 'compliance_rate' | 'churn_high_pct' | 'first_response_s' | 'avg_turns'
export type KpiUnit = 'conversaciones' | 's' | 'índice' | '%' | '1-5' | 'turnos'
export type Dimension = 'main_topic' | 'channel' | 'queue' | 'agent'
export type Granularity = 'day' | 'week'
export type KpiValues = Record<KpiCode, number | null>

export interface Period { from: string; to: string }

export interface KpiSummary {
  code: KpiCode
  label: string
  unit: KpiUnit
  higher_is_better: boolean
  value: number | null
  previous: number | null
  delta: number | null
  delta_pct: number | null
}

export interface SummaryResponse {
  period: Period
  previous_period: Period
  kpis: KpiSummary[]
  compliance_by_check: Array<{ code: string; label: string; value: number | null; applicable: number }>
}

export interface TimeseriesResponse {
  kpi: KpiCode
  granularity: Granularity
  period: Period
  points: Array<{ period_start: string; period_end: string; value: number | null }>
}

export interface BreakdownResponse {
  dimension: Dimension
  period: Period
  items: Array<{ key: string; label: string; kpis: KpiValues }>
}

export interface Catalog {
  reference_date: string
  channels: Array<{ code: string; label: string }>
  queues: Array<{ id: string; name: string }>
  agents: Array<{ id: string; name: string; queue_id: string; queue: string }>
  main_topics: Array<{ code: string; name: string }>
  compliance_checks: Array<{ code: string; label: string }>
  resolutions: Array<{ code: string; label: string }>
  churn_risks: Array<{ code: string; label: string }>
}

export interface MetricsFilters {
  from?: string
  to?: string
  channel?: string
  queue: string[]
  agent: string[]
  main_topic: string[]
}

export function useSummary(filters: MetricsFilters) {
  return useQuery({
    queryKey: ['metrics', 'summary', filters],
    queryFn: ({ signal }) => apiRequest<SummaryResponse>('/api/metrics/summary', { query: { ...filters }, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useTimeseries(kpi: KpiCode, granularity: Granularity, filters: MetricsFilters) {
  return useQuery({
    queryKey: ['metrics', 'timeseries', kpi, granularity, filters],
    queryFn: ({ signal }) => apiRequest<TimeseriesResponse>('/api/metrics/timeseries', {
      query: { ...filters, kpi, granularity }, signal,
    }),
    placeholderData: keepPreviousData,
  })
}

export function useBreakdown(dimension: Dimension, filters: MetricsFilters) {
  return useQuery({
    queryKey: ['metrics', 'breakdown', dimension, filters],
    queryFn: ({ signal }) => apiRequest<BreakdownResponse>('/api/metrics/breakdown', { query: { ...filters, dimension }, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useCatalog() {
  return useQuery({
    queryKey: ['catalog'],
    queryFn: ({ signal }) => apiRequest<Catalog>('/api/catalog', { signal }),
    staleTime: Infinity,
  })
}

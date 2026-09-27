import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import type { Granularity, MetricsFilters } from '../api/metrics'

export type FilterChanges = Record<string, string | string[] | undefined>

export const FILTER_KEYS = [
  'from', 'to', 'channel', 'queue', 'agent', 'main_topic',
  'resolution', 'churn_risk', 'sentiment_lt', 'compliant', 'repeat_contact',
] as const

export const PERIOD_PRESETS = [7, 30, 90] as const
export const DEFAULT_PRESET = 30

export function isoDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function presetRange(days: number, today = new Date()): { from: string; to: string } {
  const to = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1)
  const from = new Date(to.getFullYear(), to.getMonth(), to.getDate() - (days - 1))
  return { from: isoDate(from), to: isoDate(to) }
}

export function parseIsoDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function matchingPreset(from?: string, to?: string, today = new Date()): number | 'custom' {
  if (!from && !to) return DEFAULT_PRESET
  const match = PERIOD_PRESETS.find((days) => {
    const range = presetRange(days, today)
    return range.from === from && range.to === to
  })
  return match ?? 'custom'
}

export function useDashboardFilters() {
  const [params, setParams] = useSearchParams()

  const filters = useMemo<MetricsFilters>(() => ({
    from: params.get('from') ?? undefined,
    to: params.get('to') ?? undefined,
    channel: params.get('channel') ?? undefined,
    queue: params.getAll('queue'),
    agent: params.getAll('agent'),
    main_topic: params.getAll('main_topic'),
  }), [params])

  const granularity: Granularity = params.get('granularity') === 'week' ? 'week' : 'day'

  const update = useCallback((changes: FilterChanges) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (!('page' in changes)) next.delete('page')
      for (const [key, value] of Object.entries(changes)) {
        next.delete(key)
        for (const item of Array.isArray(value) ? value : [value]) {
          if (item) next.append(key, item)
        }
      }
      return next
    })
  }, [setParams])

  const clear = useCallback(() => setParams(new URLSearchParams()), [setParams])

  const activeCount = FILTER_KEYS.filter((key) => params.has(key)).length

  return { filters, granularity, update, clear, activeCount, params, search: params.toString() }
}

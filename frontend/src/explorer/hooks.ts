import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import type { SortKey, SortOrder, ConversationListItem } from '../api/conversations'
import type { KpiCode, KpiUnit, Period } from '../api/metrics'
import type { ExplorerQuery } from './queryModel'

export interface RunKpi {
  code: KpiCode
  label: string
  unit: KpiUnit
  higher_is_better: boolean
  value: number | null
}

export interface QueryRunResponse {
  period: Period
  kpis: RunKpi[]
  total: number
  page: number
  page_size: number
  pages: number
  items: ConversationListItem[]
}

export interface RunOptions {
  page: number
  sort: SortKey
  order: SortOrder
}

export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

export function useQueryRun(query: ExplorerQuery, options: RunOptions) {
  return useQuery({
    queryKey: ['query-run', query, options],
    queryFn: ({ signal }) => apiRequest<QueryRunResponse>('/api/query/run', {
      method: 'POST', body: query, query: { page: options.page, page_size: 25, sort: options.sort, order: options.order }, signal,
    }),
    placeholderData: keepPreviousData,
    retry: false,
  })
}

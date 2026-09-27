import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import type { SortKey, SortOrder } from '../api/conversations'
import { decodeQuery, encodeQuery, type ExplorerQuery } from './queryModel'

export function useExplorerState() {
  const [params, setParams] = useSearchParams()
  const { query, error } = useMemo(() => decodeQuery(params.get('q')), [params])

  const setQuery = useCallback((next: ExplorerQuery) => {
    setParams((prev) => {
      const updated = new URLSearchParams(prev)
      updated.set('q', encodeQuery(next))
      updated.delete('page')
      return updated
    }, { replace: true })
  }, [setParams])

  const sort: SortKey = (['date', 'duration', 'sentiment'] as const).find((s) => s === params.get('sort')) ?? 'date'
  const order: SortOrder = params.get('order') === 'asc' ? 'asc' : 'desc'
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)

  const setListing = useCallback((changes: { page?: number; sort?: SortKey; order?: SortOrder }) => {
    setParams((prev) => {
      const updated = new URLSearchParams(prev)
      for (const [key, value] of Object.entries(changes)) {
        const isDefault = (key === 'page' && value === 1) || (key === 'sort' && value === 'date') || (key === 'order' && value === 'desc')
        if (value === undefined || isDefault) updated.delete(key)
        else updated.set(key, String(value))
      }
      if (!('page' in changes)) updated.delete('page')
      return updated
    })
  }, [setParams])

  return { query, invalidLink: error, setQuery, page, sort, order, setListing }
}

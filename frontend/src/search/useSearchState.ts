import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import type { Channel } from '../api/conversations'
import type { SearchGroup, SearchParams } from './api'

export type SearchChanges = Partial<Record<'q' | 'from' | 'to' | 'channel' | 'min_score' | 'group', string | undefined>> & {
  queue?: string[]
}

/** La búsqueda vive en la URL para que recargar, compartir o volver desde el detalle la reproduzca. */
export function useSearchState() {
  const [params, setParams] = useSearchParams()

  const search = useMemo((): SearchParams | null => {
    const q = params.get('q')?.trim() ?? ''
    if (!q) return null
    const channel = (['voz', 'chat'] as const).find((c) => c === params.get('channel')) as Channel | undefined
    const minScore = Number(params.get('min_score'))
    return {
      q,
      from: params.get('from') ?? undefined,
      to: params.get('to') ?? undefined,
      channel,
      queue: params.getAll('queue'),
      min_score: Number.isFinite(minScore) && minScore > 0 && minScore <= 1 ? minScore : 0,
      group: params.get('group') === 'fragment' ? 'fragment' : 'conversation',
    }
  }, [params])

  const update = useCallback((changes: SearchChanges) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      for (const [key, value] of Object.entries(changes)) {
        next.delete(key)
        for (const item of Array.isArray(value) ? value : [value]) if (item) next.append(key, item)
      }
      return next
    }, { replace: !('q' in changes) })
  }, [setParams])

  const raw = {
    q: params.get('q') ?? '',
    from: params.get('from') ?? undefined,
    to: params.get('to') ?? undefined,
    channel: params.get('channel') ?? '',
    queue: params.getAll('queue'),
    minScore: search?.min_score ?? Math.min(1, Math.max(0, Number(params.get('min_score')) || 0)),
    group: (params.get('group') === 'fragment' ? 'fragment' : 'conversation') as SearchGroup,
  }
  return { search, raw, update }
}

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { searchResponse } from '../test/fixtures'
import { useSemanticSearch, type SearchParams } from './api'

function wrapper() {
  const client = new QueryClient()
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const params = (q: string): SearchParams => ({ q, queue: [], min_score: 0, group: 'conversation' })

describe('useSemanticSearch', () => {
  it('no llama a la API sin consulta', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useSemanticSearch(null), { wrapper: wrapper() })
    expect(fetchMock).not.toHaveBeenCalled()
    expect(result.current.fetchStatus).toBe('idle')
  })

  it('una respuesta lenta de una búsqueda anterior no sustituye a la actual', async () => {
    sessionStorage.setItem('sta.token', 'tok')
    const pending: Record<string, (body: unknown) => void> = {}
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const q = new URL(url, 'http://localhost').searchParams.get('q') ?? ''
      return new Promise((resolve) => {
        pending[q] = (body) => resolve(new Response(JSON.stringify(body), { status: 200 }))
      })
    }))
    const { result, rerender } = renderHook(({ p }) => useSemanticSearch(p), {
      wrapper: wrapper(), initialProps: { p: params('tarjeta') },
    })
    await waitFor(() => expect(pending.tarjeta).toBeDefined())
    rerender({ p: params('cajero') })
    await waitFor(() => expect(pending.cajero).toBeDefined())
    act(() => pending.cajero(searchResponse(2)))
    await waitFor(() => expect(result.current.data?.total).toBe(2))
    act(() => pending.tarjeta(searchResponse(1)))
    await new Promise((r) => setTimeout(r, 20))
    expect(result.current.data?.total).toBe(2)
  })
})

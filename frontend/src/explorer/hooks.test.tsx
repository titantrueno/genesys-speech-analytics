import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useDebouncedValue, useQueryRun } from './hooks'
import type { ExplorerQuery } from './queryModel'

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

const q = (value: string): ExplorerQuery => ({ root: { op: 'and', conditions: [{ field: 'channel', operator: 'is', value }] } })

afterEach(() => vi.useRealTimers())

describe('debounce', () => {
  it('varias ediciones seguidas producen un único valor tras 300 ms', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), { initialProps: { value: 'a' } })
    rerender({ value: 'b' })
    act(() => { vi.advanceTimersByTime(200) })
    rerender({ value: 'c' })
    act(() => { vi.advanceTimersByTime(299) })
    expect(result.current).toBe('a')
    act(() => { vi.advanceTimersByTime(1) })
    expect(result.current).toBe('c')
  })
})

describe('respuestas desordenadas', () => {
  it('una respuesta lenta de una consulta anterior no sustituye a la actual', async () => {
    sessionStorage.setItem('sta.token', 'tok')
    const pending: Record<string, (body: unknown) => void> = {}
    vi.stubGlobal('fetch', vi.fn((_url: string, init: RequestInit) => {
      const value = JSON.parse(String(init.body)).root.conditions[0].value
      return new Promise((resolve) => {
        pending[value] = (body) => resolve(new Response(JSON.stringify(body), { status: 200 }))
      })
    }))
    const { result, rerender } = renderHook(({ query }) => useQueryRun(query, { page: 1, sort: 'date', order: 'desc' }), {
      wrapper: wrapper(), initialProps: { query: q('voz') },
    })
    await waitFor(() => expect(pending.voz).toBeDefined())
    rerender({ query: q('chat') })
    await waitFor(() => expect(pending.chat).toBeDefined())

    act(() => pending.chat({ total: 2, items: [], kpis: [], page: 1, page_size: 25, pages: 1, period: { from: 'a', to: 'b' } }))
    await waitFor(() => expect(result.current.data?.total).toBe(2))
    act(() => pending.voz({ total: 1, items: [], kpis: [], page: 1, page_size: 25, pages: 1, period: { from: 'a', to: 'b' } }))
    await new Promise((r) => setTimeout(r, 20))
    expect(result.current.data?.total).toBe(2)
  })
})

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  catalogFixture, conversationDetailFixture, conversationItem, DETAIL_ID, detailCatalog, MISSING_ID, searchResponse, searchResult,
  similarResponse,
} from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from '../auth/types'

type Reply = { status: number; body?: unknown }
const Q = 'me han cobrado algo que no he comprado'
const offsetTop = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetTop')
let scrollTo: ReturnType<typeof vi.fn>

beforeEach(() => {
  scrollTo = vi.fn()
  Element.prototype.scrollTo = scrollTo as unknown as typeof Element.prototype.scrollTo
  // Cada burbuja «mide» 100 px: el turno N empieza en N·100.
  Object.defineProperty(HTMLElement.prototype, 'offsetTop', {
    configurable: true, get() { return Number((this as HTMLElement).dataset.turn ?? 0) * 100 },
  })
})
afterEach(() => {
  if (offsetTop) Object.defineProperty(HTMLElement.prototype, 'offsetTop', offsetTop)
  vi.restoreAllMocks()
})

function setup(user: User = USERS.analista, similar: (url: URL) => Reply = (url) => ({
  status: 200, body: similarResponse(url.pathname.split('/').pop()!),
})) {
  const detail = (id: string) => ({ status: 200, body: { ...conversationDetailFixture, id } })
  const first = searchResult(0).conversation_id
  return signedInAs(user, {
    'GET /api/catalog': () => ({ status: 200, body: { ...detailCatalog, reference_date: catalogFixture.reference_date } }),
    'GET /api/search/semantic': () => ({ status: 200, body: searchResponse(3) }),
    [`GET /api/conversations/${DETAIL_ID}`]: () => detail(DETAIL_ID),
    [`GET /api/conversations/${first}`]: () => detail(first),
    [`GET /api/conversations/${conversationItem(1).id}`]: () => detail(conversationItem(1).id),
    [`GET /api/search/similar/${DETAIL_ID}`]: ({ url }) => similar(new URL(url, 'http://localhost')),
    [`GET /api/search/similar/${MISSING_ID}`]: () => ({ status: 404, body: { detail: 'Conversación no encontrada' } }),
  })
}

function bubbles() {
  return within(screen.getByRole('list', { name: 'Transcripción' })).getAllByRole('listitem')
}

async function openDetail(path: string) {
  const result = renderApp(path)
  await screen.findByRole('heading', { level: 1, name: /conversación 1CO-/i })
  return result
}

describe('detalle abierto en un turno', () => {
  it('desplaza solo el chat hasta el turno indicado y lo resalta', async () => {
    setup()
    await openDetail(`/conversaciones/${DETAIL_ID}?turn=4`)
    await waitFor(() => expect(scrollTo).toHaveBeenCalled())
    expect(scrollTo.mock.contexts[0]).toBe(screen.getByTestId('chat-scroll'))
    expect(scrollTo.mock.calls[0][0]).toMatchObject({ top: 400 })
    expect(bubbles()[4]).toHaveAttribute('data-active', 'true')
  })

  it.each(['99', '-1', 'abc', '2.5'])('ignora un turno no válido (%s) sin error', async (turn) => {
    setup()
    await openDetail(`/conversaciones/${DETAIL_ID}?turn=${turn}`)
    expect(scrollTo).not.toHaveBeenCalled()
    expect(bubbles().some((b) => b.hasAttribute('data-active'))).toBe(false)
  })

  it('elegir otro turno desde el análisis sustituye al de la URL', async () => {
    setup()
    await openDetail(`/conversaciones/${DETAIL_ID}?turn=4`)
    const point = within(screen.getByRole('group', { name: /evolución del sentimiento/i })).getAllByRole('button')[2]
    await userEvent.setup().click(point)
    await waitFor(() => expect(bubbles()[6]).toHaveAttribute('data-active', 'true'))
    expect(bubbles()[4]).not.toHaveAttribute('data-active')
  })

  it('volver a la búsqueda restaura la búsqueda', async () => {
    setup()
    const { router } = renderApp(`/busqueda?q=${encodeURIComponent(Q)}&min_score=0.2&group=fragment`)
    const searchUrl = `/busqueda?q=${encodeURIComponent(Q)}&min_score=0.2&group=fragment`
    const [card] = await screen.findAllByRole('article')
    await userEvent.setup().click(within(card).getByText(/entiendo su preocupación/i))
    await userEvent.setup().click(await screen.findByRole('link', { name: 'Volver a la búsqueda' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/busqueda'))
    expect(`${router.state.location.pathname}${router.state.location.search}`).toBe(searchUrl)
  })
})

describe('conversaciones similares', () => {
  it('el botón aparece con el permiso de búsqueda y abre las 10 más cercanas', async () => {
    const fetchMock = setup()
    const { router } = await openDetail(`/conversaciones/${DETAIL_ID}`)
    await userEvent.setup().click(screen.getByRole('link', { name: 'Buscar conversaciones similares' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/busqueda'))
    expect(router.state.location.search).toBe(`?similar=${DETAIL_ID}`)
    expect(await screen.findByRole('heading', { name: /conversaciones similares a/i })).toHaveTextContent(DETAIL_ID.slice(0, 12))
    const cards = await screen.findAllByRole('article')
    expect(cards).toHaveLength(10)
    expect(within(cards[0]).getByText('90 %')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/search/semantic'))).toBe(false)
  })

  it('un similar abre su detalle y volver regresa a los similares', async () => {
    setup()
    const { router } = renderApp(`/busqueda?similar=${DETAIL_ID}`)
    const [card] = await screen.findAllByRole('article')
    expect(within(card).getByRole('link')).toHaveAttribute('href', `/conversaciones/${conversationItem(1).id}`)
    await userEvent.setup().click(within(card).getByText(conversationItem(1).main_topic_label))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/conversaciones/${conversationItem(1).id}`))
    await userEvent.setup().click(await screen.findByRole('link', { name: 'Volver a la búsqueda' }))
    await waitFor(() => expect(router.state.location.search).toBe(`?similar=${DETAIL_ID}`))
  })

  it('sin el permiso de búsqueda el botón no aparece', async () => {
    setup(USERS.viewer)
    await openDetail(`/conversaciones/${DETAIL_ID}`)
    expect(screen.queryByRole('link', { name: 'Buscar conversaciones similares' })).toBeNull()
  })

  it('una conversación de origen inexistente muestra un aviso', async () => {
    setup()
    renderApp(`/busqueda?similar=${MISSING_ID}`)
    expect(await screen.findByText('La conversación de origen no existe.')).toBeInTheDocument()
  })

  it('un error de la API muestra un aviso', async () => {
    setup(USERS.analista, () => ({ status: 500, body: { detail: 'error' } }))
    renderApp(`/busqueda?similar=${DETAIL_ID}`)
    expect(await screen.findByText(/no se han podido cargar las conversaciones similares/i)).toBeInTheDocument()
  })

  it('buscar un texto desde la vista de similares sale de ella', async () => {
    setup()
    const { router } = renderApp(`/busqueda?similar=${DETAIL_ID}`)
    await screen.findAllByRole('article')
    const user = userEvent.setup()
    await user.type(screen.getByRole('searchbox', { name: 'Consulta' }), Q)
    await user.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(new URLSearchParams(router.state.location.search).get('q')).toBe(Q))
    expect(new URLSearchParams(router.state.location.search).get('similar')).toBeNull()
    expect(await screen.findByText('3 conversaciones')).toBeInTheDocument()
  })
})

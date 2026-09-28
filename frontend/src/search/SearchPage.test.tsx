import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { catalogFixture, conversationDetailFixture, detailCatalog, QUEUE, searchResponse, searchResult } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

type Reply = { status: number; body?: unknown }

function openSearch(path = '/busqueda', reply: (url: URL) => Reply | Promise<Reply> = () => ({ status: 200, body: searchResponse(3) })) {
  const urls: URL[] = []
  const first = searchResult(0)
  signedInAs(USERS.analista, {
    'GET /api/catalog': () => ({ status: 200, body: { ...detailCatalog, reference_date: catalogFixture.reference_date } }),
    'GET /api/search/semantic': ({ url }) => { const parsed = new URL(url, 'http://localhost'); urls.push(parsed); return reply(parsed) },
    [`GET /api/conversations/${first.conversation_id}`]: () => ({ status: 200, body: { ...conversationDetailFixture, id: first.conversation_id } }),
  })
  const result = renderApp(path)
  return { ...result, urls, last: () => urls[urls.length - 1].searchParams, first }
}

async function submit(text: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByRole('searchbox', { name: 'Consulta' }), text)
  await user.click(screen.getByRole('button', { name: 'Buscar' }))
  return user
}

const Q = 'me han cobrado algo que no he comprado'

afterEach(() => vi.restoreAllMocks())

describe('búsqueda semántica: formulario y URL', () => {
  it('sin consulta muestra el estado inicial y no llama a la API', async () => {
    const { urls } = openSearch()
    expect(await screen.findByRole('heading', { level: 1, name: 'Búsqueda semántica' })).toBeInTheDocument()
    expect(screen.getByText(/escribe lo que buscas/i)).toBeInTheDocument()
    expect(urls).toHaveLength(0)
  })

  it('escribir no busca; enviar el formulario busca y guarda la consulta en la URL', async () => {
    const { urls, router, last } = openSearch()
    const user = userEvent.setup()
    await user.type(await screen.findByRole('searchbox', { name: 'Consulta' }), Q)
    expect(urls).toHaveLength(0)
    await user.keyboard('{Enter}')
    await waitFor(() => expect(urls).toHaveLength(1))
    expect(last().get('q')).toBe(Q)
    expect(last().get('group')).toBeNull()
    expect(new URLSearchParams(router.state.location.search).get('q')).toBe(Q)
  })

  it('una consulta vacía no se envía', async () => {
    const { urls } = openSearch()
    await submit('   ')
    expect(urls).toHaveLength(0)
  })

  it('restaura consulta, filtros, umbral y agrupación desde la URL', async () => {
    const path = `/busqueda?q=${encodeURIComponent(Q)}&from=2026-06-01&to=2026-06-15&channel=chat&queue=${QUEUE.tarjetas.id}&min_score=0.3&group=fragment`
    const { last } = openSearch(path)
    await screen.findByText('3 fragmentos')
    expect(Object.fromEntries(last())).toEqual({
      q: Q, from: '2026-06-01', to: '2026-06-15', channel: 'chat', queue: QUEUE.tarjetas.id, min_score: '0.3', group: 'fragment', limit: '50',
    })
    expect(screen.getByRole('searchbox', { name: 'Consulta' })).toHaveValue(Q)
    expect(screen.getByLabelText('Canal')).toHaveValue('chat')
    expect(screen.getByRole('slider', { name: /puntuación mínima/i })).toHaveValue('30')
    expect(screen.getByLabelText('Mostrar')).toHaveValue('fragment')
  })

  it('canal, cola e intervalo relanzan la búsqueda', async () => {
    const { last } = openSearch(`/busqueda?q=${encodeURIComponent(Q)}`)
    await screen.findByText('3 conversaciones')
    const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Canal'), 'voz')
    await waitFor(() => expect(last().get('channel')).toBe('voz'))
    await user.click(screen.getByRole('button', { name: /cola/i }))
    await user.click(screen.getByRole('checkbox', { name: 'Tarjetas' }))
    await waitFor(() => expect(last().getAll('queue')).toEqual([QUEUE.tarjetas.id]))
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-06-10' } })
    await waitFor(() => expect(last().get('from')).toBe('2026-06-10'))
  })

  it('el intervalo por defecto parte de la fecha de referencia del backend', async () => {
    openSearch()
    await waitFor(() => expect(screen.getByLabelText('Hasta')).toHaveValue('2026-06-30'))
    expect(screen.getByLabelText('Desde')).toHaveValue('2026-06-01')
  })
})

describe('búsqueda semántica: resultados', () => {
  it('muestra el fragmento resaltado, la puntuación y los metadatos', async () => {
    openSearch(`/busqueda?q=${encodeURIComponent(Q)}`)
    const results = await screen.findByRole('region', { name: 'Resultados' })
    expect(await within(results).findByText('3 conversaciones')).toBeInTheDocument()
    expect(within(results).getByText(/también se ha buscado/i).parentElement).toHaveTextContent('cargo, no reconozco, fraude')
    const cards = within(results).getAllByRole('article')
    expect(cards).toHaveLength(3)
    const card = cards[0]
    expect([...card.querySelectorAll('mark')].map((m) => m.textContent)).toEqual(['cargo', 'reconozco'])
    const meter = within(card).getByRole('meter', { name: 'Puntuación' })
    expect(meter).toHaveAttribute('aria-valuenow', '87')
    expect(within(card).getByText('87 %')).toBeInTheDocument()
    expect(within(card).getByText('Cargo no reconocido')).toBeInTheDocument()
    expect(within(card).getByText(searchResult(0).conversation.queue)).toBeInTheDocument()
    expect(within(card).getAllByText('Cliente')).toHaveLength(2)
    expect(within(card).getByText(searchResult(0).conversation.agent)).toBeInTheDocument()
  })

  it('el umbral relanza la búsqueda con debounce', async () => {
    const { urls, last } = openSearch(`/busqueda?q=${encodeURIComponent(Q)}`)
    await screen.findByText('3 conversaciones')
    const slider = screen.getByRole('slider', { name: /puntuación mínima/i })
    fireEvent.change(slider, { target: { value: '10' } })
    await new Promise((r) => setTimeout(r, 100))
    fireEvent.change(slider, { target: { value: '20' } })
    fireEvent.change(slider, { target: { value: '40' } })
    await waitFor(() => expect(last().get('min_score')).toBe('0.4'))
    expect(urls.filter((u) => u.searchParams.get('min_score')).length).toBe(1)
    expect(screen.getByText('40 %')).toBeInTheDocument()
  })

  it('agrupar por fragmentos relanza la búsqueda', async () => {
    const { last } = openSearch(`/busqueda?q=${encodeURIComponent(Q)}`)
    await screen.findByText('3 conversaciones')
    await userEvent.setup().selectOptions(screen.getByLabelText('Mostrar'), 'fragment')
    await waitFor(() => expect(last().get('group')).toBe('fragment'))
    expect(await screen.findByText('3 fragmentos')).toBeInTheDocument()
  })

  it('sin resultados sugiere bajar el umbral o ampliar el intervalo', async () => {
    openSearch(`/busqueda?q=${encodeURIComponent(Q)}&min_score=0.9`, () => ({ status: 200, body: searchResponse(0) }))
    expect(await screen.findByText(/no hay resultados/i)).toBeInTheDocument()
    expect(screen.getByText(/baja la puntuación mínima o amplía el intervalo/i)).toBeInTheDocument()
  })

  it('un error de la API muestra un aviso sin bloquear el formulario', async () => {
    openSearch(`/busqueda?q=${encodeURIComponent(Q)}`, () => ({ status: 500, body: { detail: 'error' } }))
    expect(await screen.findByText(/no se ha podido completar la búsqueda/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Buscar' })).toBeEnabled()
    expect(screen.getByRole('searchbox', { name: 'Consulta' })).toBeEnabled()
  })

  it('mientras llega la respuesta indica que está buscando', async () => {
    openSearch(`/busqueda?q=${encodeURIComponent(Q)}`, () => new Promise<Reply>(() => undefined))
    expect(await screen.findByText('Buscando…')).toHaveAttribute('role', 'status')
  })
})

describe('búsqueda semántica: abrir un resultado', () => {
  it('un clic en la tarjeta abre el detalle en su turno y pasa la búsqueda como origen', async () => {
    const { router, first } = openSearch(`/busqueda?q=${encodeURIComponent(Q)}&group=fragment`)
    const [card] = await screen.findAllByRole('article')
    await userEvent.setup().click(within(card).getByText(/entiendo su preocupación/i))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/conversaciones/${first.conversation_id}`))
    expect(router.state.location.search).toBe('?turn=3')
    const state = router.state.location.state as { from?: { pathname: string; search: string } }
    expect(state.from?.pathname).toBe('/busqueda')
    expect(state.from?.search).toContain('group=fragment')
  })

  it('la tarjeta tiene un único enlace y no es una parada de tabulación extra', async () => {
    const { first } = openSearch(`/busqueda?q=${encodeURIComponent(Q)}`)
    const [card] = await screen.findAllByRole('article')
    const links = within(card).getAllByRole('link')
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', `/conversaciones/${first.conversation_id}?turn=3`)
    expect(card).not.toHaveAttribute('tabindex')
    expect(card.className).toContain('cursor-pointer')
  })

  it.each([['Ctrl', '{Control>}'], ['Cmd', '{Meta>}']])('%s+clic abre una pestaña nueva', async (_name, key) => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const { router, first } = openSearch(`/busqueda?q=${encodeURIComponent(Q)}`)
    const [card] = await screen.findAllByRole('article')
    const user = userEvent.setup()
    await user.keyboard(key)
    await user.click(within(card).getByText('Cargo no reconocido'))
    expect(open).toHaveBeenCalledWith(`/conversaciones/${first.conversation_id}?turn=3`, '_blank', 'noopener')
    expect(router.state.location.pathname).toBe('/busqueda')
  })

  it('el clic central abre una pestaña nueva y con texto seleccionado no navega', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    const { router, first } = openSearch(`/busqueda?q=${encodeURIComponent(Q)}`)
    const [card] = await screen.findAllByRole('article')
    await userEvent.setup().pointer({ keys: '[MouseMiddle]', target: within(card).getByText('Cargo no reconocido') })
    expect(open).toHaveBeenCalledWith(`/conversaciones/${first.conversation_id}?turn=3`, '_blank', 'noopener')
    vi.spyOn(window, 'getSelection').mockReturnValue({ toString: () => 'cargo' } as unknown as Selection)
    await userEvent.setup().click(within(card).getByText(/entiendo su preocupación/i))
    expect(router.state.location.pathname).toBe('/busqueda')
  })
})

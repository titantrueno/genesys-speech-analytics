import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { catalogFixture, conversationRoutes } from '../test/fixtures'
import { mockApi, renderApp, signedInAs, USERS } from '../test/utils'

function lastListRequest(fetchMock: ReturnType<typeof mockApi>) {
  const urls = fetchMock.mock.calls.map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((u) => u.pathname === '/api/conversations')
  return urls[urls.length - 1].searchParams
}

async function openList(path = '/conversaciones', routes = conversationRoutes) {
  const fetchMock = signedInAs(USERS.admin, routes)
  const result = renderApp(path)
  await screen.findByRole('heading', { level: 1, name: 'Conversaciones' })
  return { fetchMock, ...result }
}

describe('listado de conversaciones', () => {
  it('muestra el total y las columnas de la spec', async () => {
    await openList()
    expect(await screen.findByText('60 conversaciones')).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Conversaciones' })
    const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent?.trim())
    expect(headers).toEqual(['Fecha', 'Canal', 'Cola', 'Agente', 'Main topic', 'Summary', 'Duración', 'Sentimiento', 'Resolución', 'CSAT'])
    expect(within(table).getAllByRole('row')).toHaveLength(26)
  })

  it('el summary muestra la primera frase y el texto completo al pasar el ratón', async () => {
    await openList()
    const cell = await screen.findByText('La clienta llama porque no reconoce un cargo número 0.')
    expect(cell).toHaveAttribute('title', expect.stringContaining('Queda resuelta con una reclamación abierta.'))
  })

  it('cada fila enlaza al detalle conservando el listado para volver', async () => {
    const { router } = await openList('/conversaciones?channel=voz&page=2')
    const table = await screen.findByRole('table', { name: 'Conversaciones' })
    await userEvent.setup().click(within(table).getAllByRole('link')[0])
    await waitFor(() => expect(router.state.location.pathname).toMatch(/^\/conversaciones\/CNV-/))
    const state = router.state.location.state as { from?: { search: string } }
    expect(state.from?.search).toBe('?channel=voz&page=2')
  })

  it('pasa los filtros de la URL, incluidos los de drill-down, a la API', async () => {
    const { fetchMock } = await openList('/conversaciones?main_topic=cajeros&resolution=escalada&sentiment_lt=-0.3&compliant=false&repeat_contact=true&churn_risk=alto')
    await screen.findByText('60 conversaciones')
    const p = lastListRequest(fetchMock)
    expect(p.get('main_topic')).toBe('cajeros')
    expect(p.get('resolution')).toBe('escalada')
    expect(p.get('sentiment_lt')).toBe('-0.3')
    expect(p.get('compliant')).toBe('false')
    expect(p.get('repeat_contact')).toBe('true')
    expect(p.get('churn_risk')).toBe('alto')
    expect(p.get('page_size')).toBe('25')
  })

  it('muestra los filtros activos como chips eliminables', async () => {
    const { router, fetchMock } = await openList('/conversaciones?main_topic=cajeros&resolution=escalada&compliant=true&from=2026-09-01&to=2026-09-20&page=2')
    const chips = await screen.findByRole('list', { name: 'Filtros activos' })
    const labels = within(chips).getAllByRole('listitem').map((c) => c.textContent)
    expect(labels).toEqual(expect.arrayContaining([
      expect.stringContaining('Incidencia en cajero'),
      expect.stringContaining('Escalada'),
      expect.stringContaining('Cumple todos los checks'),
      expect.stringContaining('1 sept – 20 sept'),
    ]))
    await userEvent.setup().click(within(chips).getByRole('button', { name: /quitar filtro resolución: escalada/i }))
    await waitFor(() => expect(router.state.location.search).not.toContain('resolution'))
    expect(router.state.location.search).not.toContain('page=')
    await waitFor(() => expect(lastListRequest(fetchMock).has('resolution')).toBe(false))
    expect(catalogFixture.main_topics.length).toBeGreaterThan(0)
  })

  it('pagina de 25 en 25', async () => {
    const { router, fetchMock } = await openList()
    await screen.findByText('Página 1 de 3')
    await userEvent.setup().click(screen.getByRole('button', { name: /siguiente/i }))
    await waitFor(() => expect(router.state.location.search).toContain('page=2'))
    await waitFor(() => expect(lastListRequest(fetchMock).get('page')).toBe('2'))
    expect(await screen.findByText('Página 2 de 3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /anterior/i })).toBeEnabled()
  })

  it('ordena por fecha, duración o sentimiento desde la cabecera', async () => {
    const { router, fetchMock } = await openList()
    const user = userEvent.setup()
    const table = await screen.findByRole('table', { name: 'Conversaciones' })
    expect(within(table).getByRole('columnheader', { name: /fecha/i })).toHaveAttribute('aria-sort', 'descending')

    await user.click(within(table).getByRole('button', { name: /duración/i }))
    await waitFor(() => expect(router.state.location.search).toContain('sort=duration'))
    await waitFor(() => expect(lastListRequest(fetchMock).get('sort')).toBe('duration'))
    expect(lastListRequest(fetchMock).get('order')).toBe('desc')

    await user.click(within(table).getByRole('button', { name: /duración/i }))
    await waitFor(() => expect(lastListRequest(fetchMock).get('order')).toBe('asc'))
    expect(within(table).getByRole('columnheader', { name: /duración/i })).toHaveAttribute('aria-sort', 'ascending')
  })

  it('muestra un estado vacío cuando no hay resultados', async () => {
    await openList('/conversaciones', {
      ...conversationRoutes,
      'GET /api/conversations': () => ({ status: 200, body: { total: 0, page: 1, page_size: 25, pages: 0, items: [] } }),
    })
    expect(await screen.findByText(/no hay conversaciones con estos filtros/i)).toBeInTheDocument()
  })
})

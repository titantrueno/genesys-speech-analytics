import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { conversationDetailFixture, detailCatalog, explorerRoutes, fakeId, runResult } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import { encodeQuery, type ExplorerQuery } from './queryModel'

const QUERY: ExplorerQuery = { root: { op: 'and', conditions: [
  { field: 'channel', operator: 'is', value: 'chat' },
  { field: 'resolution', operator: 'is', value: 'escalada' },
] } }
const FIRST_ID = fakeId('1CO', 1000)

async function openResults(run?: Parameters<typeof explorerRoutes>[1], path = `/explorador?q=${encodeQuery(QUERY)}`) {
  const bodies: unknown[] = []
  const urls: URLSearchParams[] = []
  const handler = run ?? (() => ({ status: 200, body: runResult(60) }))
  signedInAs(USERS.analista, {
    ...explorerRoutes(bodies, (body, url) => { urls.push(new URL(url, 'http://localhost').searchParams); return handler(body, url) }),
    'GET /api/catalog': () => ({ status: 200, body: detailCatalog }),
    [`GET /api/conversations/${FIRST_ID}`]: () => ({ status: 200, body: { ...conversationDetailFixture, id: FIRST_ID } }),
  })
  const result = renderApp(path)
  await screen.findByRole('heading', { level: 1, name: 'Explorador' })
  return { ...result, urls, lastUrl: () => urls[urls.length - 1] }
}

describe('resultados del explorador', () => {
  it('muestra recuento, KPIs sin enlace y la tabla de conversaciones', async () => {
    await openResults()
    const results = await screen.findByRole('region', { name: 'Resultados' })
    expect(await within(results).findByText('60 conversaciones')).toBeInTheDocument()
    const volume = within(results).getByRole('group', { name: 'Volumen' })
    expect(within(volume).getByText('1.319')).toBeInTheDocument()
    expect(within(volume).queryByRole('link')).toBeNull()
    expect(within(volume).queryByText(/periodo anterior/i)).toBeNull()
    expect(within(within(results).getByRole('table', { name: 'Conversaciones' })).getAllByRole('row')).toHaveLength(26)
  })

  it('pagina y ordena con la API y guarda el estado en la URL', async () => {
    const { router, lastUrl } = await openResults()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /siguiente/i }))
    await waitFor(() => expect(lastUrl().get('page')).toBe('2'))
    expect(router.state.location.search).toContain('page=2')
    await user.click(within(screen.getByRole('table', { name: 'Conversaciones' })).getByRole('button', { name: /duración/i }))
    await waitFor(() => expect(lastUrl().get('sort')).toBe('duration'))
    expect(lastUrl().get('page')).toBe('1')
  })

  it('una fila abre el detalle y volver regresa al explorador con la misma consulta', async () => {
    const { router } = await openResults()
    const listUrl = router.state.location.search
    const table = await screen.findByRole('table', { name: 'Conversaciones' })
    await userEvent.setup().click(within(table).getAllByRole('row')[1].querySelectorAll('td')[5])
    await waitFor(() => expect(router.state.location.pathname).toBe(`/conversaciones/${FIRST_ID}`))
    await userEvent.setup().click(await screen.findByRole('link', { name: /volver al explorador/i }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/explorador'))
    expect(router.state.location.search).toBe(listUrl)
  })

  it('sin resultados sugiere quitar la última condición', async () => {
    const { router } = await openResults((body) => ({
      status: 200, body: runResult((body as ExplorerQuery).root.conditions.length > 1 ? 0 : 5),
    }))
    expect(await screen.findByText(/no hay conversaciones que cumplan la consulta/i)).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Quitar la última condición' }))
    await waitFor(() => expect(screen.getByText('5 conversaciones')).toBeInTheDocument())
    expect(router.state.location.search).toContain('q=')
    expect(screen.getByText('Canal es Chat')).toBeInTheDocument()
  })

  it('un error de la API muestra un aviso sin bloquear el constructor', async () => {
    await openResults(() => ({ status: 500, body: { detail: 'error' } }))
    expect(await screen.findByText(/no se han podido cargar los resultados/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Añadir condición' })).toBeEnabled()
  })

  it('mientras llega la primera respuesta indica que está cargando', async () => {
    await openResults(() => new Promise(() => undefined) as never)
    expect(await screen.findByText(/cargando resultados/i)).toBeInTheDocument()
  })
})

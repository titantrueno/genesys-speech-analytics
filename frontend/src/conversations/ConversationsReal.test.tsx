import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { realCatalog, realListItem } from '../test/realFixtures'
import { catalogFixture, conversationRoutes } from '../test/fixtures'
import { mockApi, renderApp, signedInAs, USERS } from '../test/utils'

const ITEMS = Array.from({ length: 4 }, (_, i) => realListItem(i))

function realRoutes() {
  return {
    'GET /api/conversations': () => ({ status: 200, body: { total: 4, page: 1, page_size: 25, pages: 1, items: ITEMS } }),
    'GET /api/catalog': () => ({ status: 200, body: realCatalog }),
  }
}

function lastParams(fetchMock: ReturnType<typeof mockApi>) {
  const urls = fetchMock.mock.calls.map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((u) => u.pathname === '/api/conversations')
  return urls[urls.length - 1].searchParams
}

async function openReal(path = '/conversaciones') {
  const fetchMock = signedInAs(USERS.admin, realRoutes())
  renderApp(path)
  await screen.findByRole('heading', { level: 1, name: 'Conversaciones' })
  await screen.findByText('4 conversaciones')
  return fetchMock
}

describe('listado de conversaciones reales', () => {
  it('añade las columnas de teléfono, externalTag, contención y calidad de la transcripción', async () => {
    await openReal()
    const table = screen.getByRole('table', { name: 'Conversaciones' })
    const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent?.trim())
    expect(headers).toEqual(['Fecha', 'Canal', 'Cola', 'Agente', 'ANI', 'externalTag', 'Contención', 'Transcripción',
      'Main topic', 'Summary', 'Duración', 'Sentimiento', 'Resolución', 'CSAT'])
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows[1]).toHaveTextContent('+34675075376')
    expect(rows[1]).toHaveTextContent('Javier Del Olmo')
    expect(rows[1]).toHaveTextContent('Derivada')
    expect(rows[0]).toHaveTextContent('Contenida en el asistente')
    expect(rows[2]).toHaveTextContent('Parcial')
  })

  it('un summary vacío se muestra como «Análisis pendiente»', async () => {
    await openReal()
    const table = screen.getByRole('table', { name: 'Conversaciones' })
    const row = within(table).getAllByRole('row')[1]
    expect(within(row).getAllByText('Análisis pendiente').length).toBeGreaterThanOrEqual(3) // main topic, summary y resolución
  })

  it('permite buscar por teléfono y por externalTag, y la búsqueda queda como filtro activo', async () => {
    const fetchMock = await openReal()
    const search = screen.getByRole('search', { name: 'Buscar por teléfono o externalTag' })
    await userEvent.type(within(search).getByLabelText('Teléfono (ANI)'), '675 075 376')
    await userEvent.type(within(search).getByLabelText('externalTag'), 'Javier Del Olmo')
    await userEvent.click(within(search).getByRole('button', { name: 'Buscar' }))
    await screen.findByRole('list', { name: 'Filtros activos' })
    const params = lastParams(fetchMock)
    expect(params.get('phone')).toBe('675 075 376')
    expect(params.get('external_tag')).toBe('Javier Del Olmo')
    const chips = within(screen.getByRole('list', { name: 'Filtros activos' }))
    expect(chips.getByText('Teléfono: 675 075 376')).toBeInTheDocument()
    await userEvent.click(chips.getByRole('button', { name: 'Quitar filtro externalTag: Javier Del Olmo' }))
    await screen.findByText('Teléfono: 675 075 376')
    expect(lastParams(fetchMock).has('external_tag')).toBe(false)
  })

  it('con datos sintéticos no hay búsqueda por teléfono ni columnas de Genesys', async () => {
    signedInAs(USERS.admin, { ...conversationRoutes, 'GET /api/catalog': () => ({ status: 200, body: { ...catalogFixture, origin: 'sintetico' } }) })
    renderApp('/conversaciones')
    await screen.findByText('60 conversaciones')
    expect(screen.queryByRole('search', { name: 'Buscar por teléfono o externalTag' })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'ANI' })).not.toBeInTheDocument()
  })
})

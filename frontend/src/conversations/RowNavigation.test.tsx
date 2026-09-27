import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { conversationRoutes, fakeId } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

const LIST_URL = '/conversaciones?channel=voz&page=2&sort=duration'
const COLUMNS = ['Fecha', 'Canal', 'Cola', 'Agente', 'Main topic', 'Summary', 'Duración', 'Sentimiento', 'Resolución', 'CSAT']

async function openList() {
  signedInAs(USERS.admin, conversationRoutes)
  const result = renderApp(LIST_URL)
  const table = await screen.findByRole('table', { name: 'Conversaciones' })
  await within(table).findAllByRole('link')
  const firstRow = within(table).getAllByRole('row')[1]
  return { ...result, table, firstRow, firstId: fakeId('1CO', 1000 - 25) }
}

describe('fila clicable del listado', () => {
  it.each(COLUMNS.map((c, i) => [c, i]))('un clic en la celda %s abre el detalle de esa fila', async (_column, index) => {
    const { router, firstRow, firstId } = await openList()
    const cell = within(firstRow).getAllByRole('cell')[index as number]
    await userEvent.setup().click(cell)
    await waitFor(() => expect(router.state.location.pathname).toBe(`/conversaciones/${firstId}`))
    const state = router.state.location.state as { from?: { search: string } }
    expect(state.from?.search).toBe('?channel=voz&page=2&sort=duration')
  })

  it('pulsar el enlace de la fecha navega una sola vez', async () => {
    const { router, firstRow, firstId } = await openList()
    const locations: string[] = []
    const unsubscribe = router.subscribe((state) => locations.push(state.location.pathname))
    await userEvent.setup().click(within(firstRow).getByRole('link'))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/conversaciones/${firstId}`))
    unsubscribe()
    expect(locations.filter((p) => p === `/conversaciones/${firstId}`).length).toBeLessThanOrEqual(2)
    expect(new Set(locations.filter((p) => p.startsWith('/conversaciones/1CO'))).size).toBe(1)
    expect(router.state.historyAction).toBe('PUSH')
  })

  it('la fila no es un enlace ni una parada de tabulación extra', async () => {
    const { firstRow } = await openList()
    expect(firstRow).not.toHaveAttribute('role')
    expect(firstRow).not.toHaveAttribute('tabindex')
    expect(within(firstRow).getAllByRole('link')).toHaveLength(1)
    expect(firstRow.className).toContain('cursor-pointer')
  })
})

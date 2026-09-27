import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { detailRoutes } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

async function openDetail(path = '/conversaciones/CNV-000005') {
  signedInAs(USERS.viewer, detailRoutes)
  const result = renderApp(path)
  await screen.findByRole('heading', { level: 1, name: /CNV-000005/ })
  return result
}

function bubbles() {
  return within(screen.getByRole('list', { name: 'Transcripción' })).getAllByRole('listitem')
}

describe('detalle de conversación', () => {
  it('muestra el main topic destacado y el summary completo en la cabecera', async () => {
    await openDetail()
    const header = screen.getByRole('region', { name: 'Resumen de la conversación' })
    expect(within(header).getByText('Cargo no reconocido')).toBeInTheDocument()
    expect(within(header).getByText(/Queda pendiente de que aporte la denuncia/)).toBeInTheDocument()
    expect(within(header).getByText('Chat')).toBeInTheDocument()
  })

  it('pinta la transcripción como un chat: cliente a la izquierda, agente y bot a la derecha, sistema centrado', async () => {
    await openDetail()
    const items = bubbles()
    expect(items).toHaveLength(8)
    const sides = items.map((li) => [li.dataset.speaker, li.dataset.side])
    expect(sides).toEqual([
      ['bot', 'right'], ['cliente', 'left'], ['sistema', 'center'], ['agente', 'right'],
      ['cliente', 'left'], ['agente', 'right'], ['cliente', 'left'], ['sistema', 'center'],
    ])
    expect(within(items[0]).getByText('Asistente virtual')).toBeInTheDocument()
    expect(within(items[3]).getByText('Sergio Molina')).toBeInTheDocument()
    expect(within(items[1]).getByText('Cliente')).toBeInTheDocument()
  })

  it('cada burbuja muestra su marca de tiempo relativa y un indicador de sentimiento', async () => {
    await openDetail()
    const items = bubbles()
    expect(within(items[3]).getByText('1:03')).toBeInTheDocument()
    expect(within(items[6]).getByText('5:58')).toBeInTheDocument()
    expect(within(items[6]).getByText('Sentimiento negativo')).toBeInTheDocument()
    expect(within(items[5]).getByText('Sentimiento positivo')).toBeInTheDocument()
    expect(within(items[2]).queryByText(/Sentimiento/)).toBeNull()
  })

  it('resalta las palabras clave del análisis', async () => {
    await openDetail()
    const marks = Array.from(document.querySelectorAll('mark')).map((m) => m.textContent?.toLowerCase())
    expect(marks).toEqual(expect.arrayContaining(['no reconozco', 'fraude']))
  })

  it('el panel de análisis muestra resultado, cumplimiento, temas y entidades', async () => {
    await openDetail()
    const panel = screen.getByRole('complementary', { name: 'Análisis' })
    expect(within(panel).getByText('No resuelta')).toBeInTheDocument()
    expect(within(panel).getByText('1,3 / 5')).toBeInTheDocument()
    expect(within(panel).getByText('4,4 / 5')).toBeInTheDocument()
    expect(within(panel).getByText('Alto')).toBeInTheDocument()

    const checks = within(panel).getByRole('list', { name: 'Cumplimiento' })
    const identity = (await within(checks).findByText('Verificación de identidad del cliente')).closest('li')!
    expect(identity).toHaveTextContent('No cumple')
    const fraud = within(checks).getByText('Ofrecimiento de bloqueo preventivo en casos de fraude').closest('li')!
    expect(fraud).toHaveTextContent('No aplica')
    expect(within(checks).getByText('Saludo e identificación del agente').closest('li')).toHaveTextContent('Cumple')

    expect(within(panel).getByText('reiteración del problema')).toBeInTheDocument()
    expect(within(panel).getByText('TiendaYa Online')).toBeInTheDocument()
  })

  it('pulsar un punto de la evolución del sentimiento desplaza solo el chat hasta ese turno', async () => {
    const scrollTo = vi.fn()
    Element.prototype.scrollTo = scrollTo as unknown as typeof Element.prototype.scrollTo
    await openDetail()
    const target = bubbles()[4]
    Object.defineProperty(target, 'offsetTop', { configurable: true, value: 900 })
    Object.defineProperty(target, 'offsetHeight', { configurable: true, value: 60 })
    const chat = screen.getByTestId('chat-scroll')
    Object.defineProperty(chat, 'clientHeight', { configurable: true, value: 400 })

    const chart = screen.getByRole('group', { name: /evolución del sentimiento/i })
    const points = within(chart).getAllByRole('button')
    expect(points).toHaveLength(3)
    await userEvent.setup().click(points[1])

    expect(scrollTo).toHaveBeenCalledTimes(1)
    expect(scrollTo.mock.contexts[0]).toBe(chat)
    expect(scrollTo.mock.calls[0][0]).toMatchObject({ top: 900 - 200 + 30 })
    await waitFor(() => expect(bubbles()[4]).toHaveAttribute('data-active', 'true'))
  })

  it('los puntos del gráfico son accesibles con teclado', async () => {
    Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo
    await openDetail()
    const point = within(screen.getByRole('group', { name: /evolución del sentimiento/i })).getAllByRole('button')[2]
    point.focus()
    await userEvent.setup().keyboard('{Enter}')
    await waitFor(() => expect(bubbles()[6]).toHaveAttribute('data-active', 'true'))
  })

  it('volver al listado conserva filtros, página y orden', async () => {
    signedInAs(USERS.viewer, detailRoutes)
    const { router } = renderApp('/conversaciones?main_topic=cajeros&page=2&sort=duration&order=asc')
    await screen.findByRole('heading', { level: 1, name: 'Conversaciones' })
    await router.navigate('/conversaciones/CNV-000005', { state: { from: { pathname: '/conversaciones', search: '?main_topic=cajeros&page=2&sort=duration&order=asc' } } })
    await userEvent.setup().click(await screen.findByRole('link', { name: /volver al listado/i }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/conversaciones'))
    expect(router.state.location.search).toBe('?main_topic=cajeros&page=2&sort=duration&order=asc')
  })

  it('sin listado previo, volver lleva al listado por defecto', async () => {
    const { router } = await openDetail()
    await userEvent.setup().click(screen.getByRole('link', { name: /volver al listado/i }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/conversaciones'))
    expect(router.state.location.search).toBe('')
  })

  it('una conversación inexistente muestra un aviso', async () => {
    signedInAs(USERS.viewer, detailRoutes)
    renderApp('/conversaciones/CNV-999999')
    expect(await screen.findByText(/conversación no encontrada/i)).toBeInTheDocument()
  })
})

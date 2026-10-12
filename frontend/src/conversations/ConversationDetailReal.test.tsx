import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  REAL_CHAT_ID, REAL_RECONNECT_ID, REAL_UNDELIVERED_ID, REAL_VOICE_ID, realCatalog, realChatDetail, realReconnectDetail,
  realUndeliveredDetail, realVoiceDetail,
} from '../test/realFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

beforeEach(() => {
  Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo
})

const DETAILS = [realVoiceDetail, realChatDetail, realUndeliveredDetail, realReconnectDetail]

async function open(id: string, details: Array<{ id: string }> = DETAILS) {
  signedInAs(USERS.viewer, {
    'GET /api/catalog': () => ({ status: 200, body: realCatalog }),
    ...Object.fromEntries(details.map((d) => [`GET /api/conversations/${d.id}`, () => ({ status: 200, body: d })])),
  })
  renderApp(`/conversaciones/${id}`)
  await screen.findByRole('heading', { level: 1, name: new RegExp(id) })
}

const turns = () => within(screen.getByRole('list', { name: 'Transcripción' })).getAllByRole('listitem')
const genesys = () => screen.getByRole('complementary', { name: 'Analítica de Genesys' })

describe('detalle de una llamada real bot → agente', () => {
  it('distingue los turnos de cliente, bot y agente y marca la transferencia entre el bot y el agente', async () => {
    await open(REAL_VOICE_ID)
    expect(turns().map((li) => [li.dataset.speaker, li.dataset.side])).toEqual([
      ['bot', 'right'], ['cliente', 'left'], ['bot', 'right'], ['agente', 'right'], ['cliente', 'left'],
    ])
    expect(within(turns()[0]).getByText('Asistente virtual')).toBeInTheDocument()
    expect(within(turns()[3]).getByText('Javier Del Olmo')).toBeInTheDocument()
    const lines = screen.getAllByRole('separator')
    expect(lines).toHaveLength(1)
    expect(lines[0]).toHaveTextContent('Transferencia del asistente virtual al agente')
    // La línea va justo entre el último turno del bot y el primero del agente.
    expect(lines[0].previousElementSibling).toBe(turns()[2])
    expect(lines[0].nextElementSibling).toBe(turns()[3])
  })

  it('con el análisis pendiente lo dice en lugar de mostrar ceros', async () => {
    await open(REAL_VOICE_ID)
    const header = screen.getByRole('region', { name: 'Resumen de la conversación' })
    expect(within(header).getAllByText('Análisis pendiente').length).toBeGreaterThan(0)
    const analysis = screen.getByRole('complementary', { name: 'Análisis' })
    expect(within(analysis).getByText('Análisis pendiente')).toBeInTheDocument()
    expect(within(analysis).queryByText(/CSAT predicho/)).not.toBeInTheDocument()
    expect(within(analysis).queryByText(/0,0 \/ 5/)).not.toBeInTheDocument()
    expect(within(genesys()).getByText('Análisis pendiente')).toBeInTheDocument()
  })

  it('con summary y main topic de un flujo (FE013), el aviso de pendiente ya no los incluye', async () => {
    const written = { ...realVoiceDetail, analysis: { ...realVoiceDetail.analysis, summary: 'Resumen generado por el LLM.', main_topic: 'cajeros' } }
    await open(REAL_VOICE_ID, [written])
    expect(screen.getByRole('region', { name: 'Resumen de la conversación' })).toHaveTextContent('Resumen generado por el LLM.')
    const analysis = screen.getByRole('complementary', { name: 'Análisis' })
    expect(analysis).toHaveTextContent('La resolución, el cumplimiento y las puntuaciones llegarán con el análisis de la plataforma.')
    expect(analysis).not.toHaveTextContent(/El summary, el main topic/)
  })

  it('el panel de Genesys muestra teléfonos, etiqueta, recorrido, wrap-up, cierre y contención', async () => {
    await open(REAL_VOICE_ID)
    const panel = within(genesys())
    expect(panel.getByText('+34675075376')).toBeInTheDocument()
    expect(panel.getByText('+34919187266')).toBeInTheDocument()
    expect(panel.getByText('Javier Del Olmo', { selector: 'dd' })).toBeInTheDocument()
    const route = panel.getByRole('list', { name: 'Recorrido' })
    expect(within(route).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      expect.stringContaining('Asistente virtual · Sierra VoiceAgent'),
      expect.stringContaining('Cola · AIT_Transcription'),
      expect.stringContaining('Agente · Javier Del Olmo'),
    ])
    expect(panel.getByText('Default Wrap-up Code')).toBeInTheDocument()
    expect(panel.getByText('El agente o el asistente')).toBeInTheDocument()
    expect(panel.getByText('Derivada a agente')).toBeInTheDocument()
    expect(panel.getByText('Contenida en el asistente')).toBeInTheDocument()
  })

  it('muestra los tiempos, la calidad de la llamada, el reparto del tiempo y la confianza de la transcripción', async () => {
    await open(REAL_VOICE_ID)
    const panel = within(genesys())
    expect(panel.getByText('Gestión')).toBeInTheDocument()
    expect(panel.getByText('3:32 min')).toBeInTheDocument() // 212,4 s
    expect(panel.getByText('Espera en cola')).toBeInTheDocument()
    expect(panel.getByText('MOS')).toBeInTheDocument()
    expect(panel.getByText('4,3')).toBeInTheDocument()
    expect(panel.getByText('Factor R')).toBeInTheDocument()
    const split = panel.getByRole('list', { name: 'Reparto del tiempo' })
    expect(split).toHaveTextContent('Silencio')
    expect(split).toHaveTextContent('14,9 %')
    expect(panel.getByText('Calidad de la transcripción')).toBeInTheDocument()
    expect(panel.getByText('Completa')).toBeInTheDocument()
    const confidence = panel.getByRole('list', { name: 'Confianza media por hablante' })
    expect(confidence).toHaveTextContent('Cliente')
    expect(confidence).toHaveTextContent('87 %')
  })

  it('al pulsar un tema, el chat se desplaza a su turno', async () => {
    await open(REAL_VOICE_ID)
    await userEvent.click(within(genesys()).getByRole('button', { name: /Realización de pagos/ }))
    expect(Element.prototype.scrollTo).toHaveBeenCalled()
    await waitFor(() => expect(turns()[4]).toHaveAttribute('data-active', 'true'))
    expect(turns()[0]).not.toHaveAttribute('data-active')
  })
})

describe('detalle de un chat real', () => {
  it('un chat bot → agente no muestra el ANI ni los campos que su canal no tiene', async () => {
    await open(REAL_CHAT_ID)
    const panel = within(genesys())
    expect(panel.queryByText('ANI')).not.toBeInTheDocument()
    expect(panel.queryByText('DNIS')).not.toBeInTheDocument()
    expect(panel.queryByText('MOS')).not.toBeInTheDocument()
    expect(panel.getByText('Primera respuesta')).toBeInTheDocument()
    expect(panel.getByText('Respuesta media del agente')).toBeInTheDocument()
    expect(screen.getAllByRole('separator')).toHaveLength(1)
  })

  it('un mensaje no entregado conserva su texto y lleva la marca «No entregado»', async () => {
    await open(REAL_UNDELIVERED_ID)
    const failed = turns()[1]
    expect(within(failed).getByText('lo estoy revisando, un segundo')).toBeInTheDocument()
    expect(within(failed).getByText('No entregado')).toBeInTheDocument()
    expect(within(turns()[2]).queryByText('No entregado')).not.toBeInTheDocument()
    expect(within(genesys()).getByText('Mensajes no entregados')).toBeInTheDocument()
  })

  it('en una reconexión se repiten los tramos y cada transferencia del bot al agente tiene su línea', async () => {
    await open(REAL_RECONNECT_ID)
    const route = within(genesys()).getByRole('list', { name: 'Recorrido' })
    expect(within(route).getAllByRole('listitem')).toHaveLength(6)
    expect(screen.getAllByRole('separator')).toHaveLength(2)
    expect(within(genesys()).getByText('Reconexión')).toBeInTheDocument()
  })
})

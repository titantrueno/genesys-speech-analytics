import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { loaded, setupEditor as setup } from '../test/flowEditor'
import { CHAINED, nodeId } from '../test/flowFixtures'
import { mockReactFlow } from '../test/reactFlow'
import { USERS } from '../test/utils'
import { fromCanvas, toCanvasEdges, toCanvasNodes } from './graph'
import type { FlowGraph } from './types'

beforeAll(mockReactFlow)

const BOX = nodeId(9)
/** La caja «Genesys download» delante del Sampling del flujo encadenado (FE017). */
const WITH_BOX: FlowGraph = {
  version: 1,
  nodes: [
    { id: BOX, type: 'descarga', position: { x: -300, y: 15 }, config: {
      interval: { type: 'relativo', unit: 'hoy' }, channels: ['voz', 'chat'], overwrite: false,
      schedule: { type: 'cada_horas', hours: 1 }, active: true } },
    ...CHAINED.nodes,
  ],
  edges: [{ source: BOX, target: nodeId(1) }, ...CHAINED.edges],
}

async function openNode(ctx: ReturnType<typeof setup>, id: string, name: RegExp) {
  await loaded()
  fireEvent.click(ctx.node(id))
  return screen.findByRole('region', { name })
}

async function saved(ctx: ReturnType<typeof setup>, id: string) {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  await waitFor(() => expect(ctx.puts.length).toBeGreaterThan(0))
  return ctx.puts.at(-1)!.nodes.find((n) => n.id === id)!.config as Record<string, unknown>
}

describe('caja «Genesys download» en el editor (FE017)', () => {
  it('la paleta la añade y su panel guarda intervalo, canales, programación, activo y Sobrescribir', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Añadir Genesys download' }))
    const panel = await screen.findByRole('region', { name: 'Configuración del Genesys download' })
    expect(within(panel).getByLabelText('Periodo')).toHaveValue('hoy')
    await user.selectOptions(within(panel).getByLabelText('Periodo'), 'horas')
    await user.type(within(panel).getByLabelText('Cantidad'), '6')
    await user.click(within(panel).getByRole('checkbox', { name: 'Voz' }))
    await user.selectOptions(within(panel).getByLabelText('Programación'), 'cada_horas')
    await user.type(within(panel).getByLabelText('Cada cuántas horas'), '2')
    await user.click(within(panel).getByRole('checkbox', { name: 'Sobrescribir' }))
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(ctx.puts.length).toBe(1))
    const box = ctx.puts[0].nodes.find((n) => n.type === 'descarga')!
    expect(box.config).toEqual({
      interval: { type: 'relativo', unit: 'horas', amount: 6 }, channels: ['chat'], overwrite: true,
      schedule: { type: 'cada_horas', hours: 2 }, active: true,
    })
  })

  it('una programación con intervalo específico avisa con el mensaje de los flujos de descarga', async () => {
    const ctx = setup({ graph: WITH_BOX })
    const user = userEvent.setup()
    const panel = await openNode(ctx, BOX, /Configuración del Genesys download/)
    await user.click(within(panel).getByRole('radio', { name: 'Específico' }))
    expect(within(panel).getByText('Una descarga programada necesita un intervalo relativo')).toBeInTheDocument()
    await user.selectOptions(within(panel).getByLabelText('Programación'), 'desactivada')
    expect(within(panel).queryByText('Una descarga programada necesita un intervalo relativo')).not.toBeInTheDocument()
  })

  it('con una caja en el flujo, la paleta no deja añadir otra y explica por qué', async () => {
    setup({ graph: WITH_BOX })
    await loaded()
    const add = screen.getByRole('button', { name: 'Añadir Genesys download' })
    expect(add).toBeDisabled()
    expect(add).toHaveAccessibleDescription('Un flujo solo puede tener una Genesys download.')
  })

  it('la caja solo se conecta a un Sampling: conectarla a un Prompt avisa del motivo', async () => {
    const ctx = setup({ graph: { ...WITH_BOX, edges: CHAINED.edges } })
    const user = userEvent.setup()
    const panel = await openNode(ctx, BOX, /Configuración del Genesys download/)
    expect(within(panel).queryByLabelText('Conectar entrada desde')).not.toBeInTheDocument()
    await user.selectOptions(within(panel).getByLabelText('Añadir salida hacia'), nodeId(2))
    expect(await screen.findByRole('alert')).toHaveTextContent('Una Genesys download solo puede conectarse a un Sampling.')
    await user.selectOptions(within(panel).getByLabelText('Añadir salida hacia'), nodeId(1))
    await waitFor(() => expect(ctx.container.querySelectorAll('.react-flow__edge')).toHaveLength(5))
  })

  it('Sampling «All conversations» oculta método y tamaño y guarda size "all"', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await openNode(ctx, nodeId(1), /Configuración del Sampling/)
    await within(panel).findByLabelText('Método')
    await user.click(within(panel).getByRole('checkbox', { name: 'All conversations' }))
    expect(within(panel).queryByLabelText('Método')).not.toBeInTheDocument()
    expect(within(panel).queryByLabelText('Tamaño de la muestra')).not.toBeInTheDocument()
    const config = await saved(ctx, nodeId(1))
    expect(config.size).toBe('all')
    expect(config).not.toHaveProperty('method')
    await waitFor(() => expect(ctx.estimates.at(-1)?.size).toBe('all'))
    await user.click(within(panel).getByRole('checkbox', { name: 'All conversations' }))
    expect(within(panel).getByLabelText('Método')).toHaveValue('aleatorio')
    expect(within(panel).getByLabelText('Tamaño de la muestra')).toHaveValue(100)
  })

  it('detrás de la caja, el Sampling no tiene fechas y la estimación depende de la descarga', async () => {
    const ctx = setup({ graph: WITH_BOX, estimate: () => ({ status: 200, body: {
      available: null, sample_size: null, period: null, depends_on_download: true } }) })
    const panel = await openNode(ctx, nodeId(1), /Configuración del Sampling/)
    await within(panel).findByLabelText('Método')
    expect(within(panel).queryByLabelText('Desde')).not.toBeInTheDocument()
    expect(within(panel).getByText(/Las conversaciones las da la Genesys download/)).toBeInTheDocument()
    expect(await within(panel).findByText('El número de conversaciones depende de la descarga.')).toBeInTheDocument()
    await waitFor(() => expect(ctx.estimates.at(-1)).toMatchObject({ after_download: true }))
    // Su entrada, en Conexiones.
    expect(within(panel).getAllByRole('listitem').some((li) => /^Genesys download 1/.test(li.textContent ?? ''))).toBe(true)
  })

  it('sin flows:edit, la caja está en solo lectura', async () => {
    const ctx = setup({ graph: WITH_BOX, user: USERS.lector })
    const panel = await openNode(ctx, BOX, /Configuración del Genesys download/)
    expect(within(panel).getByLabelText('Periodo')).toBeDisabled()
    expect(within(panel).getByLabelText('Programación')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Añadir Genesys download' })).not.toBeInTheDocument()
  })

  it('el lienzo conserva la caja al ir y volver del JSON', () => {
    expect(fromCanvas(toCanvasNodes(WITH_BOX), toCanvasEdges(WITH_BOX))).toEqual(WITH_BOX)
  })
})

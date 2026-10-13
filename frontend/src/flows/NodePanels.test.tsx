import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { loaded, setupEditor as setup } from '../test/flowEditor'
import { nodeId } from '../test/flowFixtures'
import { mockReactFlow } from '../test/reactFlow'
import { USERS } from '../test/utils'

beforeAll(mockReactFlow)

async function open(id: number, ctx: ReturnType<typeof setup>) {
  await loaded()
  fireEvent.click(ctx.node(nodeId(id)))
  const panel = await screen.findByRole('region', { name: /^Configuración del/ })
  if (id === 1) await within(panel).findByLabelText('Método') // el Sampling espera al esquema de campos de FE002
  return panel
}

async function saveAndGetConfig(ctx: ReturnType<typeof setup>, id: string) {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  await waitFor(() => expect(ctx.puts.length).toBeGreaterThan(0))
  return ctx.puts.at(-1)!.nodes.find((n) => n.id === id)!.config as Record<string, unknown>
}

describe('panel de configuración', () => {
  it('se abre al seleccionar un nodo y se cierra', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    expect(panel).toHaveAccessibleName('Configuración del Prompt')
    await user.click(within(panel).getByRole('button', { name: 'Cerrar configuración' }))
    await waitFor(() => expect(screen.queryByRole('region', { name: /^Configuración del/ })).not.toBeInTheDocument())
  })

  it('Sampling: método, estratos, orden y tamaño llegan al JSON del flujo', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(1, ctx)
    await user.selectOptions(within(panel).getByLabelText('Método'), 'estratificado')
    expect(within(panel).getByLabelText('Estratificar por')).toHaveValue('canal')
    await user.selectOptions(within(panel).getByLabelText('Estratificar por'), 'cola')
    const size = within(panel).getByLabelText('Tamaño de la muestra')
    await user.clear(size)
    await user.type(size, '250')
    expect(await saveAndGetConfig(ctx, nodeId(1))).toMatchObject({ method: 'estratificado', stratify_by: 'cola', size: 250 })

    await user.selectOptions(within(panel).getByLabelText('Método'), 'primeros_n')
    expect(within(panel).queryByLabelText('Estratificar por')).not.toBeInTheDocument()
    expect(within(panel).getByLabelText('Ordenar por')).toHaveValue('fecha')
    expect(within(panel).getByLabelText('Sentido')).toHaveValue('desc')
    await user.selectOptions(within(panel).getByLabelText('Ordenar por'), 'csat')
    const config = await saveAndGetConfig(ctx, nodeId(1))
    expect(config).toMatchObject({ method: 'primeros_n', order_by: 'csat', order: 'desc', size: 250 })
    expect(config).not.toHaveProperty('stratify_by')
  })

  it('Sampling: limita el tamaño a 1–1.000', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(1, ctx)
    const size = within(panel).getByLabelText('Tamaño de la muestra')
    await user.clear(size)
    await user.type(size, '5000')
    expect(size).toHaveValue(1000)
  })

  it('Sampling: estima las conversaciones disponibles con debounce', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(1, ctx)
    expect(await within(panel).findByText(/conversaciones disponibles/)).toHaveTextContent('1.234 conversaciones disponibles · muestra de 40')
    const before = ctx.estimates.length
    const size = within(panel).getByLabelText('Tamaño de la muestra')
    await user.clear(size)
    await user.type(size, '321')
    await waitFor(() => expect(ctx.estimates.at(-1)?.size).toBe(321))
    // Escribir «321» no lanza una estimación por pulsación.
    expect(ctx.estimates.slice(before).map((e) => e.size)).not.toContain(32)
    await waitFor(() => expect(within(panel).getByText(/conversaciones disponibles/)).toHaveTextContent('muestra de 321'))
  })

  it('Sampling: reutiliza el constructor de FE002 y solo estima con condiciones completas', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(1, ctx)
    await user.click(within(panel).getByRole('button', { name: 'Añadir condición' }))
    const condition = within(panel).getByRole('group', { name: 'Condición 1' })
    await user.selectOptions(within(condition).getByLabelText('Campo'), 'transcript')
    await new Promise((resolve) => setTimeout(resolve, 600)) // más que el debounce de la estimación
    const sentConditions = () => ctx.estimates.flatMap((e) => (e.query as { root: { conditions: Array<{ value?: unknown }> } }).root.conditions)
    expect(sentConditions().filter((c) => c.value === '')).toEqual([])
    await user.type(within(condition).getByLabelText('Valor'), 'fraude')
    await waitFor(() => expect((ctx.estimates.at(-1)!.query as { root: { conditions: unknown[] } }).root.conditions).toHaveLength(1))
    fireEvent.change(within(panel).getByLabelText('Desde'), { target: { value: '2026-09-10' } })
    const config = await saveAndGetConfig(ctx, nodeId(1))
    expect(config.query).toEqual({
      from: '2026-09-10', to: '2026-09-26',
      root: { op: 'and', conditions: [{ field: 'transcript', operator: 'contains', value: 'fraude' }] },
    })
    expect(within(panel).getByText(/Transcripción contiene «fraude»/)).toBeInTheDocument()
  })

  it('Sampling: avisa si la estimación falla o la muestra estaría vacía', async () => {
    let status = 200
    const ctx = setup({ estimate: () => (status === 200 ? { status, body: { available: 0, sample_size: 0, period: { from: 'a', to: 'b' } } } : { status }) })
    const panel = await open(1, ctx)
    expect(await within(panel).findByText(/la muestra estaría vacía/)).toBeInTheDocument()
    status = 422
    const user = userEvent.setup()
    await user.type(within(panel).getByLabelText('Tamaño de la muestra'), '1')
    expect(await within(panel).findByRole('alert')).toHaveTextContent('No se ha podido estimar')
  })

  it('Prompt: plantilla con variables, modelo y temperatura', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    const template = within(panel).getByLabelText('Texto del prompt')
    await user.clear(template)
    await user.type(template, 'Resume: ')
    await user.click(within(panel).getByRole('button', { name: '{{metadatos}}' }))
    expect(template).toHaveValue('Resume: {{metadatos}}')
    expect(within(panel).getByRole('button', { name: '{{resultado_anterior}}' })).toBeDisabled()
    await user.selectOptions(within(panel).getByLabelText('Modelo'), 'mock-preciso')
    fireEvent.change(within(panel).getByLabelText(/^Temperatura/), { target: { value: '0.7' } })
    expect(within(panel).getByText('Temperatura: 0.7')).toBeInTheDocument()
    expect(await saveAndGetConfig(ctx, nodeId(2))).toMatchObject({ template: 'Resume: {{metadatos}}', model: 'mock-preciso', temperature: 0.7 })
  })

  it('Prompt: un nodo sin proveedor es simulado; al cambiar de proveedor propone su primer modelo', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    expect(within(panel).getByLabelText('Proveedor')).toHaveValue('simulado')
    expect(within(panel).getByLabelText('Modelo')).toHaveValue('mock-rapido')
    await user.selectOptions(within(panel).getByLabelText('Proveedor'), 'gemini')
    expect(within(panel).getByLabelText('Modelo')).toHaveValue('gemini-3.5-flash-lite')
    expect([...within(panel).getByLabelText('Modelo').querySelectorAll('option')].map((o) => o.value)).toEqual(['gemini-3.5-flash-lite'])
    expect(await saveAndGetConfig(ctx, nodeId(2))).toMatchObject({ provider: 'gemini', model: 'gemini-3.5-flash-lite' })
  })

  it('Prompt: con un modelo que no admite temperatura, el control se desactiva y lo explica', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    expect(within(panel).getByLabelText(/^Temperatura/)).toBeEnabled()
    await user.selectOptions(within(panel).getByLabelText('Proveedor'), 'anthropic')
    expect(within(panel).getByLabelText(/^Temperatura/)).toBeDisabled()
    expect(panel).toHaveTextContent(/no admite temperatura/i)
  })

  it('Prompt: {{resultado_anterior}} solo en un prompt encadenado', async () => {
    const ctx = setup()
    const panel = await open(3, ctx)
    expect(within(panel).getByRole('button', { name: '{{resultado_anterior}}' })).toBeEnabled()
  })

  it('Prompt: etiquetas y esquema JSON', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    const labels = within(panel).getByRole('group', { name: 'Etiquetas' })
    expect(within(labels).getByLabelText('Etiqueta 1')).toHaveValue('A')
    await user.click(within(labels).getByRole('button', { name: 'Añadir etiqueta' }))
    await user.type(within(labels).getByLabelText('Etiqueta 3'), 'C')
    await user.click(within(labels).getByRole('button', { name: 'Quitar etiqueta 1' }))
    expect((await saveAndGetConfig(ctx, nodeId(2))).output).toEqual({ type: 'etiqueta', labels: ['B', 'C'] })

    await user.selectOptions(within(panel).getByLabelText('Formato'), 'json')
    const schema = within(panel).getByRole('group', { name: 'Esquema JSON' })
    await user.type(within(schema).getByLabelText('Nombre del campo 1'), 'motivo')
    await user.click(within(schema).getByRole('button', { name: 'Añadir campo' }))
    await user.type(within(schema).getByLabelText('Nombre del campo 2'), 'gravedad')
    await user.selectOptions(within(schema).getByLabelText('Tipo del campo 2'), 'numero')
    expect((await saveAndGetConfig(ctx, nodeId(2))).output).toEqual({
      type: 'json', fields: [{ name: 'motivo', type: 'texto' }, { name: 'gravedad', type: 'numero' }],
    })
  })

  it('Output: tipo, agregación y destino', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(5, ctx)
    expect(within(panel).queryByLabelText('Agregación')).not.toBeInTheDocument()
    await user.selectOptions(within(panel).getByLabelText('Tipo de output'), 'metrica')
    expect(within(panel).getByLabelText('Agregación')).toHaveValue('recuento')
    await user.selectOptions(within(panel).getByLabelText('Agregación'), 'porcentaje')
    const destination = within(panel).getByLabelText('Nombre de destino')
    await user.clear(destination)
    await user.type(destination, 'motivos')
    expect(await saveAndGetConfig(ctx, nodeId(5))).toEqual({ kind: 'metrica', aggregation: 'porcentaje', destination: 'motivos' })
  })

  it('lista las conexiones del nodo y permite desconectarlas', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    const connections = within(panel).getByRole('region', { name: 'Conexiones' })
    const items = () => within(connections).getAllByRole('listitem').map((li) => li.textContent)
    expect(items()).toEqual([
      'Sampling 1 · Aleatorio · 40 conversacionesDesconectar', expect.stringMatching(/^Prompt 2 · /), expect.stringMatching(/^Output 1 · /),
    ])
    await user.click(within(connections).getByRole('button', { name: /Desconectar de Output 1/ }))
    await waitFor(() => expect(ctx.container.querySelectorAll('.react-flow__edge')).toHaveLength(3))
    expect(items()).toHaveLength(2)
  })

  it('conecta desde el panel aplicando las reglas y avisa del motivo si las incumple', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    const picker = within(panel).getByLabelText('Añadir salida hacia')
    await user.selectOptions(picker, nodeId(1))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se puede conectar: Un Sampling solo admite como entrada una Genesys download.')
    await user.selectOptions(picker, nodeId(5))
    expect(screen.getByRole('alert')).toHaveTextContent('El Output ya tiene una entrada')
    expect(ctx.container.querySelectorAll('.react-flow__edge')).toHaveLength(4)

    await user.click(screen.getByRole('button', { name: 'Añadir Output' }))
    const newPanel = await screen.findByRole('region', { name: 'Configuración del Output' })
    await user.selectOptions(within(newPanel).getByLabelText('Conectar entrada desde'), nodeId(2))
    await waitFor(() => expect(ctx.container.querySelectorAll('.react-flow__edge')).toHaveLength(5))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('elimina el nodo con su botón', async () => {
    const ctx = setup()
    const user = userEvent.setup()
    const panel = await open(3, ctx)
    await user.click(within(panel).getByRole('button', { name: 'Eliminar nodo' }))
    await waitFor(() => expect(ctx.nodes()).toHaveLength(4))
    expect(ctx.container.querySelectorAll('.react-flow__edge')).toHaveLength(2)
    expect(screen.queryByRole('region', { name: /^Configuración del/ })).not.toBeInTheDocument()
    // Las conexiones del nodo borrado tampoco quedan en el JSON (React Flow no pinta las huérfanas, pero se guardarían).
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(ctx.puts).toHaveLength(1))
    expect(ctx.puts[0].edges.every((e) => e.source !== nodeId(3) && e.target !== nodeId(3))).toBe(true)
    expect(ctx.puts[0].edges).toHaveLength(2)
  })

  it('sin flows:edit el panel es de solo lectura', async () => {
    const ctx = setup({ user: USERS.lector })
    const panel = await open(2, ctx)
    expect(within(panel).getByRole('group', { name: 'Configuración' })).toBeDisabled()
    expect(within(panel).getByLabelText('Texto del prompt')).toBeDisabled()
    expect(within(panel).queryByRole('button', { name: 'Eliminar nodo' })).not.toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /Desconectar/ })).not.toBeInTheDocument()
    expect(within(panel).queryByLabelText('Añadir salida hacia')).not.toBeInTheDocument()
  })
})

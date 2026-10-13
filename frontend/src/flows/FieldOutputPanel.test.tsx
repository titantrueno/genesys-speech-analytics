import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { loaded, setupEditor } from '../test/flowEditor'
import { CATALOG, nodeId } from '../test/flowFixtures'
import { mockReactFlow } from '../test/reactFlow'
import { nodeSummary } from './catalog'
import type { FlowGraph, PromptConfig } from './types'

beforeAll(mockReactFlow)

const N = nodeId
const JSON_PROMPT: PromptConfig = {
  template: 'Resume y clasifica {{transcripcion}}', provider: 'gemini', model: 'gemini-3.5-flash-lite', temperature: 0.2,
  output: { type: 'json', fields: [
    { name: 'summary', type: 'texto' }, { name: 'main_topic', type: 'texto', options: ['Cajeros', 'Comisiones'] },
    { name: 'urgente', type: 'booleano' }] },
}

function graph(prompt: PromptConfig, output: FlowGraph['nodes'][number]['config'] = { kind: 'tabla', destination: 'detalle' }): FlowGraph {
  return {
    version: 1,
    nodes: [
      { id: N(1), type: 'sampling', position: { x: 0, y: 0 }, config: { method: 'aleatorio', size: 10, query: { root: { op: 'and', conditions: [] } } } },
      { id: N(2), type: 'prompt', position: { x: 300, y: 0 }, config: prompt },
      { id: N(3), type: 'output', position: { x: 600, y: 0 }, config: output } as FlowGraph['nodes'][number],
    ],
    edges: [{ source: N(1), target: N(2) }, { source: N(2), target: N(3) }],
  }
}

async function open(id: number, ctx: ReturnType<typeof setupEditor>) {
  await loaded()
  fireEvent.click(ctx.node(N(id)))
  return screen.findByRole('region', { name: /^Configuración del/ })
}

async function saved(ctx: ReturnType<typeof setupEditor>, id: string) {
  await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
  await waitFor(() => expect(ctx.puts.length).toBeGreaterThan(0))
  return ctx.puts.at(-1)!.nodes.find((n) => n.id === id)!.config as Record<string, unknown>
}

describe('Output «Guardar en campos»', () => {
  it('con datos sintéticos la opción está desactivada y lo explica', async () => {
    const ctx = setupEditor({ graph: graph(JSON_PROMPT) })
    const panel = await open(3, ctx)
    const option = within(panel).getByRole('option', { name: 'Guardar en campos de la conversación' })
    expect(option).toBeDisabled()
    expect(panel).toHaveTextContent(/Guardar en campos solo funciona con datos reales/i)
  })

  it('con un Prompt JSON guarda summary y main topic de una llamada, con sus campos de origen', async () => {
    const ctx = setupEditor({ graph: graph(JSON_PROMPT), catalog: { origin: 'real' } })
    const user = userEvent.setup()
    const panel = await open(3, ctx)
    await user.selectOptions(within(panel).getByLabelText('Tipo de output'), 'campo')
    expect(within(panel).queryByLabelText('Nombre de destino')).not.toBeInTheDocument()
    expect(within(panel).getByLabelText('Campo destino 1')).toHaveValue('summary')
    const source = within(panel).getByLabelText('Campo del JSON 1')
    // Solo los campos de texto del JSON pueden alimentar un campo destino.
    expect([...source.querySelectorAll('option')].map((o) => o.value)).toEqual(['', 'summary', 'main_topic'])
    await user.selectOptions(source, 'summary')
    await user.click(within(panel).getByRole('button', { name: 'Añadir campo destino' }))
    expect(within(panel).getByLabelText('Campo destino 2')).toHaveValue('main_topic')
    await user.selectOptions(within(panel).getByLabelText('Campo del JSON 2'), 'main_topic')
    // Un destino ya asignado no se puede repetir en otra asignación.
    expect(within(within(panel).getByLabelText('Campo destino 2')).getByRole('option', { name: 'Summary' })).toBeDisabled()
    const overwrite = within(panel).getByRole('checkbox', { name: 'Sobrescribir valores existentes' })
    expect(overwrite).not.toBeChecked()
    await user.click(overwrite)
    const config = await saved(ctx, N(3))
    expect(config).toEqual({ kind: 'campo', overwrite: true, mappings: [
      { target: 'summary', source: 'summary' }, { target: 'main_topic', source: 'main_topic' }] })
  })

  it('con un Prompt de texto hay una sola asignación con la respuesta entera', async () => {
    const ctx = setupEditor({ graph: graph({ ...JSON_PROMPT, output: { type: 'texto' } }), catalog: { origin: 'real' } })
    const user = userEvent.setup()
    const panel = await open(3, ctx)
    await user.selectOptions(within(panel).getByLabelText('Tipo de output'), 'campo')
    expect(within(panel).queryByLabelText('Campo del JSON 1')).not.toBeInTheDocument()
    expect(panel).toHaveTextContent(/respuesta completa del Prompt/i)
    expect(within(panel).queryByRole('button', { name: 'Añadir campo destino' })).not.toBeInTheDocument()
    expect(await saved(ctx, N(3))).toEqual({ kind: 'campo', overwrite: false, mappings: [{ target: 'summary' }] })
  })

  it('quitar una asignación y volver a tabla limpia la configuración', async () => {
    const ctx = setupEditor({ graph: graph(JSON_PROMPT, { kind: 'campo', overwrite: false, mappings: [
      { target: 'summary', source: 'summary' }, { target: 'main_topic', source: 'main_topic' }] }), catalog: { origin: 'real' } })
    const user = userEvent.setup()
    const panel = await open(3, ctx)
    await user.click(within(panel).getByRole('button', { name: 'Quitar campo destino 1' }))
    expect(within(panel).getByLabelText('Campo destino 1')).toHaveValue('main_topic')
    await user.selectOptions(within(panel).getByLabelText('Tipo de output'), 'tabla')
    await user.type(within(panel).getByLabelText('Nombre de destino'), 'detalle')
    expect(await saved(ctx, N(3))).toEqual({ kind: 'tabla', destination: 'detalle' })
  })

  it('en el lienzo resume los campos destino', () => {
    expect(nodeSummary({ type: 'output', config: { kind: 'campo', mappings: [{ target: 'summary', source: 'summary' },
      { target: 'main_topic', source: 'main_topic' }] } }, CATALOG)).toEqual(['Guardar en campos de la conversación', '→ Summary + Main topic'])
  })
})

describe('valores permitidos en el esquema JSON', () => {
  it('un campo de texto puede limitarse a una lista de valores, uno por línea', async () => {
    const ctx = setupEditor({ graph: graph({ ...JSON_PROMPT, output: { type: 'json', fields: [{ name: 'motivo', type: 'texto' }] } }) })
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    await user.click(within(panel).getByRole('checkbox', { name: 'Limitar el campo 1 a una lista de valores' }))
    const values = within(panel).getByLabelText('Valores permitidos del campo 1')
    await user.type(values, 'Cajeros{Enter}Comisiones{Enter}{Enter}')
    expect(await saved(ctx, N(2))).toMatchObject({ output: { type: 'json', fields: [
      { name: 'motivo', type: 'texto', options: ['Cajeros', 'Comisiones'] }] } })
  })

  it('un campo numérico o booleano no ofrece valores permitidos', async () => {
    const ctx = setupEditor({ graph: graph(JSON_PROMPT) })
    const panel = await open(2, ctx)
    expect(within(panel).getByRole('checkbox', { name: 'Limitar el campo 2 a una lista de valores' })).toBeChecked()
    expect(within(panel).getByLabelText('Valores permitidos del campo 2')).toHaveValue('Cajeros\nComisiones')
    expect(within(panel).queryByRole('checkbox', { name: 'Limitar el campo 3 a una lista de valores' })).not.toBeInTheDocument()
  })
})

const FULL_PROMPT: PromptConfig = {
  ...JSON_PROMPT,
  output: { type: 'json', fields: [
    { name: 'summary', type: 'texto' }, { name: 'csat', type: 'numero' }, { name: 'esfuerzo', type: 'numero' },
    { name: 'temas', type: 'lista', options: ['Fraude'] }, { name: 'saludo', type: 'texto', options: ['cumple', 'no_cumple', 'no_aplica'] },
    { name: 'urgente', type: 'booleano' }] },
}

describe('análisis completo en «Guardar en campos» (FE014)', () => {
  it('el desplegable de destino agrupa análisis, cumplimiento y entidades', async () => {
    const ctx = setupEditor({ graph: graph(FULL_PROMPT, { kind: 'campo', overwrite: false, mappings: [{ target: 'summary', source: 'summary' }] }),
      catalog: { origin: 'real' } })
    const panel = await open(3, ctx)
    const target = within(panel).getByLabelText('Campo destino 1')
    const groups = [...target.querySelectorAll('optgroup')]
    expect(groups.map((g) => g.label)).toEqual(['Análisis', 'Cumplimiento', 'Entidades'])
    expect([...groups[1].querySelectorAll('option')].map((o) => o.textContent)).toEqual([
      'Saludo e identificación del agente', 'Despedida con resumen de la gestión'])
    expect([...groups[2].querySelectorAll('option')].map((o) => o.value)).toEqual([
      'entity:importe', 'entity:producto', 'entity:fecha', 'entity:comercio'])
  })

  it('cada destino ofrece solo los campos del JSON de su tipo', async () => {
    const ctx = setupEditor({ graph: graph(FULL_PROMPT, { kind: 'campo', overwrite: false, mappings: [{ target: 'summary', source: 'summary' }] }),
      catalog: { origin: 'real' } })
    const user = userEvent.setup()
    const panel = await open(3, ctx)
    const sources = (i: number) => [...within(panel).getByLabelText(`Campo del JSON ${i}`).querySelectorAll('option')].map((o) => o.value)
    await user.selectOptions(within(panel).getByLabelText('Campo destino 1'), 'csat')
    expect(sources(1)).toEqual(['', 'csat', 'esfuerzo'])
    await user.selectOptions(within(panel).getByLabelText('Campo destino 1'), 'secondary_topics')
    expect(sources(1)).toEqual(['', 'temas'])
    await user.selectOptions(within(panel).getByLabelText('Campo destino 1'), 'compliance:saludo')
    expect(sources(1)).toEqual(['', 'summary', 'saludo'])
    await user.selectOptions(within(panel).getByLabelText('Campo del JSON 1'), 'saludo')
    expect(await saved(ctx, N(3))).toEqual({ kind: 'campo', overwrite: false, mappings: [{ target: 'compliance:saludo', source: 'saludo' }] })
  })

  it('el esquema admite el tipo «Lista» con valores permitidos', async () => {
    const ctx = setupEditor({ graph: graph({ ...JSON_PROMPT, output: { type: 'json', fields: [{ name: 'temas', type: 'texto' }] } }) })
    const user = userEvent.setup()
    const panel = await open(2, ctx)
    await user.selectOptions(within(panel).getByLabelText('Tipo del campo 1'), 'lista')
    await user.click(within(panel).getByRole('checkbox', { name: 'Limitar el campo 1 a una lista de valores' }))
    await user.type(within(panel).getByLabelText('Valores permitidos del campo 1'), 'Fraude{Enter}App móvil')
    expect(await saved(ctx, N(2))).toMatchObject({ output: { type: 'json', fields: [
      { name: 'temas', type: 'lista', options: ['Fraude', 'App móvil'] }] } })
  })
})

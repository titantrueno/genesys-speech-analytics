import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it } from 'vitest'
import { drop, loaded, RUN_ID, saveState, setupEditor as setup } from '../test/flowEditor'
import { CHAINED, FLOW_ID, nodeId } from '../test/flowFixtures'
import { mockReactFlow } from '../test/reactFlow'
import { USERS } from '../test/utils'
import { NODE_DRAG_TYPE } from './FlowCanvas'
import { sameJson } from './graph'
import type { Issue } from './types'

beforeAll(mockReactFlow)

describe('editor de flujos', () => {
  it('reconstruye el flujo guardado: nodos, conexiones y resumen de su configuración', async () => {
    const { nodes, container } = setup()
    await loaded()
    expect(nodes().map((n) => n.dataset.id)).toEqual(CHAINED.nodes.map((n) => n.id))
    expect(container.querySelectorAll('.react-flow__edge')).toHaveLength(4)
    expect(screen.getByLabelText('Sampling: Aleatorio · 40 conversaciones')).toBeInTheDocument()
    expect(screen.getByLabelText('Prompt: Clasifica {{summary}}')).toHaveTextContent('Simulado rápido · T 0.2 · Etiqueta de una lista (2 etiquetas)')
    expect(screen.getByLabelText('Output: Métrica agregada · Recuento por etiqueta')).toHaveTextContent('→ reparto')
    // Recién cargado no hay cambios, aunque el backend ordene las claves de otra forma.
    expect(saveState()).toHaveTextContent('Guardado')
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeDisabled()
    expect(screen.getByRole('region', { name: 'Lienzo del flujo' })).toBeInTheDocument()
    expect(container.querySelector('.react-flow__controls')).toBeInTheDocument()
    expect(container.querySelector('.react-flow__minimap')).toBeInTheDocument()
  })

  it('suelta un nodo arrastrado desde la paleta en el lienzo', async () => {
    const { nodes } = setup()
    await loaded()
    drop('prompt', screen.getByRole('region', { name: 'Lienzo del flujo' }))
    await waitFor(() => expect(nodes()).toHaveLength(6))
    const added = nodes()[5]
    expect(added.dataset.id).toMatch(/^tmp-/)
    expect(added).toHaveClass('react-flow__node-prompt', 'selected')
    expect(saveState()).toHaveTextContent('Cambios sin guardar')
  })

  it('ignora lo que se suelta y no es un nodo de la paleta', async () => {
    const { nodes } = setup()
    await loaded()
    drop('filtro', screen.getByRole('region', { name: 'Lienzo del flujo' }))
    expect(nodes()).toHaveLength(5)
  })

  it('la paleta es arrastrable y cada nodo se puede añadir también con un botón', async () => {
    const { nodes } = setup()
    const user = userEvent.setup()
    await loaded()
    const palette = screen.getByRole('complementary', { name: 'Paleta de nodos' })
    const sampling = within(palette).getByRole('button', { name: 'Añadir Sampling' })
    expect(sampling).toHaveAttribute('draggable', 'true')
    const data = new Map<string, string>()
    fireEvent.dragStart(sampling, { dataTransfer: { setData: (k: string, v: string) => data.set(k, v), effectAllowed: '' } })
    expect(data.get(NODE_DRAG_TYPE)).toBe('sampling')
    await user.click(within(palette).getByRole('button', { name: 'Añadir Output' }))
    await waitFor(() => expect(nodes()).toHaveLength(6))
    expect(nodes()[5]).toHaveClass('react-flow__node-output', 'selected')
  })

  it('borra el nodo seleccionado con Supr junto con sus conexiones', async () => {
    const { nodes, node, container } = setup()
    const user = userEvent.setup()
    await loaded()
    fireEvent.click(node(nodeId(2)))
    await waitFor(() => expect(node(nodeId(2))).toHaveClass('selected'))
    await user.keyboard('{Delete}')
    await waitFor(() => expect(nodes()).toHaveLength(4))
    expect(container.querySelectorAll('.react-flow__edge')).toHaveLength(1)
  })

  it('guarda el JSON del lienzo y adopta los identificadores del backend', async () => {
    const { puts, nodes } = setup()
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Añadir Sampling' }))
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(saveState()).toHaveTextContent('Guardado'))
    expect(puts).toHaveLength(1)
    expect(puts[0].nodes.slice(0, 5)).toEqual(CHAINED.nodes)
    expect(puts[0].edges).toEqual(CHAINED.edges)
    expect(puts[0].nodes[5]).toMatchObject({ type: 'sampling', config: { method: 'aleatorio', size: 100 } })
    expect(puts[0].nodes[5].id).toMatch(/^tmp-/)
    expect(nodes()[5].dataset.id).toBe(nodeId(100))
    expect(nodes()[5]).toHaveClass('selected')
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeDisabled()
  })

  it('al recargar reconstruye exactamente lo guardado', async () => {
    const first = setup()
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Añadir Output' }))
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(saveState()).toHaveTextContent('Guardado'))
    const saved = first.stored()
    first.unmount()

    const second = setup({ graph: saved })
    await loaded()
    expect(second.nodes().map((n) => n.dataset.id)).toEqual(saved.nodes.map((n) => n.id))
    expect(saveState()).toHaveTextContent('Guardado')
    // Añadir un nodo y borrarlo devuelve el lienzo al JSON guardado: no quedan cambios.
    await user.click(screen.getByRole('button', { name: 'Añadir Prompt' }))
    expect(saveState()).toHaveTextContent('Cambios sin guardar')
    await user.keyboard('{Delete}')
    await waitFor(() => expect(saveState()).toHaveTextContent('Guardado'))
  })

  it('muestra por qué no se ha podido guardar', async () => {
    setup({ saveStatus: 422 })
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Añadir Prompt' }))
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se ha podido guardar el flujo. Conexión no válida')
    expect(saveState()).toHaveTextContent('Cambios sin guardar')
  })

  it('Validar lista los errores, marca sus nodos y selecciona el nodo de un error', async () => {
    const issues: Issue[] = [
      { code: 'missing_output', message: 'El flujo necesita al menos un nodo Output.', node_id: null },
      { code: 'prompt_without_variables', message: 'El prompt no usa ninguna variable.', node_id: nodeId(3) },
      { code: 'node_unconfigured', message: 'Sin configurar: falta modelo.', node_id: nodeId(3) },
    ]
    const { validations, node } = setup({ validate: () => issues })
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Validar' }))
    const list = await screen.findByRole('list', { name: 'Errores de validación' })
    expect(within(list).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'El flujo necesita al menos un nodo Output.',
      'Prompt 2: El prompt no usa ninguna variable.',
      'Prompt 2: Sin configurar: falta modelo.',
    ])
    expect(sameJson(validations[0], CHAINED)).toBe(true)
    expect(within(node(nodeId(3))).getByText('2 errores')).toBeInTheDocument()
    expect(within(node(nodeId(2))).queryByText(/error/)).not.toBeInTheDocument()
    await user.click(within(list).getByRole('button', { name: /no usa ninguna variable/ }))
    await waitFor(() => expect(node(nodeId(3))).toHaveClass('selected'))
    expect(node(nodeId(2))).not.toHaveClass('selected')
  })

  it('revalida tras cada cambio y al cerrar la validación quita las marcas', async () => {
    const { validations, node, nodes } = setup({
      validate: (graph) => graph.nodes.length > 5 ? [] : [{ code: 'x', message: 'Falta algo.', node_id: nodeId(1) }],
    })
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Validar' }))
    expect(await within(node(nodeId(1))).findByText('1 error')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Añadir Output' }))
    await waitFor(() => expect(nodes()).toHaveLength(6))
    expect(await screen.findByText('El flujo es válido.')).toBeInTheDocument()
    expect(validations.at(-1)?.nodes).toHaveLength(6)
    expect(within(node(nodeId(1))).queryByText('1 error')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cerrar validación' }))
    expect(screen.queryByRole('region', { name: 'Validación' })).not.toBeInTheDocument()
  })

  it('Ejecutar guarda los cambios pendientes y abre la ejecución', async () => {
    const { calls, router } = setup()
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Añadir Output' }))
    await user.click(screen.getByRole('button', { name: 'Ejecutar' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/${FLOW_ID}/ejecuciones/${RUN_ID}`))
    expect(calls).toEqual(['PUT', 'RUN'])
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('Ejecutar sin cambios no vuelve a guardar', async () => {
    const { calls, router } = setup()
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Ejecutar' }))
    await waitFor(() => expect(router.state.location.pathname).toMatch(/ejecuciones/))
    expect(calls).toEqual(['RUN'])
  })

  it('un flujo no válido no se ejecuta: muestra sus errores', async () => {
    const issues: Issue[] = [{ code: 'missing_output', message: 'El flujo necesita al menos un nodo Output.', node_id: null }]
    const { router } = setup({
      validate: () => issues,
      run: () => ({ status: 422, body: { detail: issues } }),
    })
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Ejecutar' }))
    expect(await screen.findByText('El flujo tiene errores: corrígelos antes de ejecutarlo.')).toBeInTheDocument()
    expect(await screen.findByText('El flujo necesita al menos un nodo Output.')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe(`/flujos/${FLOW_ID}`)
  })

  it('avisa de que ya hay una ejecución en curso', async () => {
    setup({ run: () => ({ status: 409, body: { detail: 'Ya hay una ejecución en curso de este flujo' } }) })
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Ejecutar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ya hay una ejecución en curso de este flujo.')
  })

  it('avisa de los cambios sin guardar antes de salir', async () => {
    const { router } = setup()
    const user = userEvent.setup()
    await loaded()
    await user.click(screen.getByRole('button', { name: 'Añadir Prompt' }))
    await user.click(screen.getByRole('link', { name: 'Volver a flujos' }))
    const dialog = await screen.findByRole('alertdialog', { name: 'Hay cambios sin guardar' })
    await user.click(within(dialog).getByRole('button', { name: 'Seguir editando' }))
    expect(router.state.location.pathname).toBe(`/flujos/${FLOW_ID}`)
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Volver a flujos' }))
    await user.click(await screen.findByRole('button', { name: 'Salir sin guardar' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/flujos'))
  })

  it('avisa también al cerrar o recargar la pestaña con cambios', async () => {
    setup()
    const user = userEvent.setup()
    await loaded()
    const clean = new Event('beforeunload', { cancelable: true })
    act(() => { window.dispatchEvent(clean) })
    expect(clean.defaultPrevented).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Añadir Prompt' }))
    const dirty = new Event('beforeunload', { cancelable: true })
    act(() => { window.dispatchEvent(dirty) })
    expect(dirty.defaultPrevented).toBe(true)
  })

  it('sin flows:edit el editor es de solo lectura', async () => {
    const { container, node } = setup({ user: USERS.lector })
    const user = userEvent.setup()
    await loaded()
    expect(saveState()).toHaveTextContent('Solo lectura')
    expect(screen.queryByRole('complementary', { name: 'Paleta de nodos' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ejecutar' })).not.toBeInTheDocument()
    expect(container.querySelectorAll('.react-flow__node.draggable')).toHaveLength(0)
    expect(container.querySelectorAll('.react-flow__handle.connectable')).toHaveLength(0)
    drop('prompt', screen.getByRole('region', { name: 'Lienzo del flujo' }))
    fireEvent.click(node(nodeId(2)))
    await user.keyboard('{Delete}')
    expect(container.querySelectorAll('.react-flow__node')).toHaveLength(5)
    expect(screen.getByRole('button', { name: 'Validar' })).toBeInTheDocument()
  })

  it('un flujo inexistente muestra un aviso', async () => {
    setup({ flowStatus: 404 })
    expect(await screen.findByRole('alert')).toHaveTextContent('Flujo no encontrado.')
    expect(screen.getByRole('link', { name: 'Volver a flujos' })).toHaveAttribute('href', '/flujos')
  })
})

import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fakeId } from '../test/fixtures'
import { CATALOG } from '../test/flowFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from '../auth/types'
import type { Flow, FlowSummary } from './types'

const AUTHOR = { id: fakeId('1US', 3), name: 'Analista Demo' }

function summary(n: number, overrides: Partial<FlowSummary> = {}): FlowSummary {
  return {
    id: fakeId('1FL', n), name: `Flujo ${n}`, author: AUTHOR, created_at: '2026-09-20T08:00:00+00:00',
    updated_at: '2026-09-27T10:30:00+00:00', status: 'valido', last_run: null, next_run: null, ...overrides,
  }
}

const FLOWS = [
  summary(1, {
    name: 'Motivos de fraude', last_run: { id: fakeId('1RN', 1), created_at: '2026-09-27T11:00:00+00:00', status: 'ok' },
  }),
  summary(2, { name: 'Borrador de quejas', status: 'con_errores' }),
]

const EMPTY_GRAPH = { version: 1, nodes: [], edges: [] }

type Call = { method: string; path: string; body?: unknown }

function setup(options: {
  user?: User; items?: FlowSummary[]; listStatus?: number; createStatus?: number; listGate?: Promise<void>; catalog?: boolean
} = {}) {
  let items = [...(options.items ?? FLOWS)]
  const calls: Call[] = []
  const record = (method: string, path: string, init: RequestInit) => {
    const body = init.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    return body
  }
  const asFlow = (item: FlowSummary): Flow => {
    const { last_run: _ignored, ...rest } = item
    return { ...rest, graph: EMPTY_GRAPH } as Flow
  }
  type Reply = { status: number; body?: unknown }
  const routes: Record<string, (init: RequestInit & { url: string }) => Reply | Promise<Reply>> = {
    'GET /api/flows': async () => {
      await options.listGate
      return options.listStatus ? { status: options.listStatus } : { status: 200, body: { items } }
    },
    'POST /api/flows': (init) => {
      const { name } = record('POST', '/api/flows', init)
      if (options.createStatus) return { status: options.createStatus, body: { detail: 'No válido' } }
      const created = summary(10, { name, status: 'con_errores' })
      items = [created, ...items]
      return { status: 201, body: asFlow(created) }
    },
    [`GET /api/flows/${fakeId('1FL', 10)}`]: () => ({ status: 200, body: asFlow(items[0]) }),
    [`GET /api/flows/${fakeId('1FL', 1)}`]: () => ({ status: 200, body: asFlow(FLOWS[0]) }),
    'GET /api/flows/catalog': () => (options.catalog ? { status: 200, body: CATALOG } : { status: 404 }),
    'GET /api/download-flows': () => ({ status: 200, body: { items: [] } }),
  }
  for (const item of FLOWS) {
    routes[`POST /api/flows/${item.id}/duplicate`] = (init) => {
      record('POST', `duplicate ${item.id}`, init)
      const copy = summary(20, { name: `Copia de ${item.name}`, author: { id: USERS.analista.id, name: USERS.analista.name } })
      items = [copy, ...items]
      return { status: 201, body: asFlow(copy) }
    }
    routes[`PATCH /api/flows/${item.id}`] = (init) => {
      const { name } = record('PATCH', item.id, init)
      items = items.map((f) => (f.id === item.id ? { ...f, name } : f))
      return { status: 200, body: asFlow(items.find((f) => f.id === item.id)!) }
    }
    routes[`DELETE /api/flows/${item.id}`] = (init) => {
      record('DELETE', item.id, init)
      items = items.filter((f) => f.id !== item.id)
      return { status: 204 }
    }
  }
  signedInAs(options.user ?? USERS.analista, routes)
  return { ...renderApp('/flujos'), calls }
}

const row = (name: string) => screen.getByRole('row', { name: new RegExp(name) })

describe('listado de flujos', () => {
  it('muestra nombre, autor, última modificación, última ejecución y estado', async () => {
    setup()
    expect(await screen.findByRole('heading', { name: 'Flujos de insights' })).toBeInTheDocument()
    const fraud = await screen.findByRole('row', { name: /Motivos de fraude/ })
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    // FE011: el listado incluye los flujos de descarga, con su tipo y su próxima ejecución.
    expect(headers).toEqual(['Nombre', 'Tipo', 'Autor', 'Última modificación', 'Última ejecución', 'Próxima ejecución', 'Estado', 'Acciones'])
    expect(within(fraud).getByText('Analista Demo')).toBeInTheDocument()
    expect(within(fraud).getByText('27 sept, 10:30')).toBeInTheDocument()
    expect(within(fraud).getByText('27 sept, 11:00')).toBeInTheDocument()
    expect(within(fraud).getByText('OK')).toBeInTheDocument()
    expect(within(fraud).getByText('Válido')).toBeInTheDocument()
    const draft = row('Borrador de quejas')
    expect(within(draft).getByText('Sin ejecuciones')).toBeInTheDocument()
    expect(within(draft).getByText('Con errores')).toBeInTheDocument()
  })

  it('el nombre y la fila abren el editor', async () => {
    const { router } = setup()
    const user = userEvent.setup()
    expect(await screen.findByRole('link', { name: 'Motivos de fraude' })).toHaveAttribute('href', `/flujos/${fakeId('1FL', 1)}`)
    await user.click(within(row('Motivos de fraude')).getByText('Analista Demo'))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/${fakeId('1FL', 1)}`))
  })

  it('crea un flujo con nombre y abre su editor', async () => {
    const { calls, router } = setup()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Nuevo flujo' }))
    const name = screen.getByLabelText('Nombre del flujo')
    expect(screen.getByRole('button', { name: 'Crear' })).toBeDisabled()
    await user.type(name, '  Quejas por comisiones  ')
    await user.click(screen.getByRole('button', { name: 'Crear' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/${fakeId('1FL', 10)}`))
    expect(calls).toContainEqual({ method: 'POST', path: '/api/flows', body: { name: 'Quejas por comisiones' } })
  })

  it('crea un flujo desde una plantilla de summary y main topic', async () => {
    const { calls, router } = setup({ catalog: true })
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Nuevo flujo' }))
    const template = await screen.findByLabelText('Plantilla')
    expect(template).toHaveValue('')
    expect([...template.querySelectorAll('option')].map((o) => o.textContent)).toEqual([
      'Vacío', 'Generar summary', 'Generar main topic', 'Generar summary y main topic', 'Generar análisis completo'])
    await user.type(screen.getByLabelText('Nombre del flujo'), 'Summary y main topic')
    await user.selectOptions(template, 'summary_main_topic')
    await user.click(screen.getByRole('button', { name: 'Crear' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/${fakeId('1FL', 10)}`))
    expect(calls).toContainEqual({ method: 'POST', path: '/api/flows',
      body: { name: 'Summary y main topic', template: 'summary_main_topic' } })
  })

  it('crea un flujo desde la plantilla de análisis completo (FE014)', async () => {
    const { calls } = setup({ catalog: true })
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Nuevo flujo' }))
    await user.type(screen.getByLabelText('Nombre del flujo'), 'Análisis completo')
    await user.selectOptions(await screen.findByLabelText('Plantilla'), 'analisis_completo')
    await user.click(screen.getByRole('button', { name: 'Crear' }))
    await waitFor(() => expect(calls).toContainEqual({ method: 'POST', path: '/api/flows',
      body: { name: 'Análisis completo', template: 'analisis_completo' } }))
  })

  it('avisa si no se puede crear el flujo', async () => {
    setup({ createStatus: 422 })
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Nuevo flujo' }))
    await user.type(screen.getByLabelText('Nombre del flujo'), 'X')
    await user.click(screen.getByRole('button', { name: 'Crear' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No se ha podido crear el flujo.')
  })

  it('duplica un flujo', async () => {
    const { calls } = setup()
    const user = userEvent.setup()
    await screen.findByRole('row', { name: /Motivos de fraude/ })
    await user.click(within(row('Motivos de fraude')).getByRole('button', { name: 'Duplicar' }))
    expect(await screen.findByRole('row', { name: /Copia de Motivos de fraude/ })).toBeInTheDocument()
    expect(calls).toContainEqual({ method: 'POST', path: `duplicate ${fakeId('1FL', 1)}`, body: undefined })
  })

  it('renombra un flujo en la propia fila', async () => {
    const { calls } = setup()
    const user = userEvent.setup()
    await screen.findByRole('row', { name: /Motivos de fraude/ })
    await user.click(within(row('Motivos de fraude')).getByRole('button', { name: 'Renombrar' }))
    const input = screen.getByLabelText('Nuevo nombre')
    await user.clear(input)
    await user.type(input, 'Fraude en compras online{Enter}')
    expect(await screen.findByRole('link', { name: 'Fraude en compras online' })).toBeInTheDocument()
    expect(calls).toContainEqual({ method: 'PATCH', path: fakeId('1FL', 1), body: { name: 'Fraude en compras online' } })
  })

  it('borra un flujo tras confirmar', async () => {
    const { calls } = setup()
    const user = userEvent.setup()
    await screen.findByRole('row', { name: /Borrador de quejas/ })
    await user.click(within(row('Borrador de quejas')).getByRole('button', { name: 'Borrar' }))
    expect(calls.filter((c) => c.method === 'DELETE')).toEqual([])
    await user.click(within(row('Borrador de quejas')).getByRole('button', { name: 'Confirmar borrado' }))
    await waitFor(() => expect(screen.queryByRole('row', { name: /Borrador de quejas/ })).not.toBeInTheDocument())
    expect(calls).toContainEqual({ method: 'DELETE', path: fakeId('1FL', 2), body: undefined })
  })

  it('muestra el estado de carga y después el de error', async () => {
    let fail: () => void = () => {}
    setup({ listStatus: 500, listGate: new Promise<void>((resolve) => { fail = resolve }) })
    expect(await screen.findByText('Cargando flujos…')).toHaveAttribute('role', 'status')
    fail()
    expect(await screen.findByRole('alert')).toHaveTextContent('No se han podido cargar los flujos.')
    expect(screen.queryByText('Cargando flujos…')).not.toBeInTheDocument()
  })

  it('invita a crear el primer flujo cuando no hay ninguno', async () => {
    setup({ items: [] })
    expect(await screen.findByText('Todavía no hay flujos.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Nuevo flujo' })).toHaveLength(1)
  })

  it('sin flows:edit no hay acciones', async () => {
    setup({ user: USERS.lector })
    await screen.findByRole('row', { name: /Motivos de fraude/ })
    expect(screen.queryByRole('button', { name: 'Nuevo flujo' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Duplicar|Renombrar|Borrar/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Acciones' })).not.toBeInTheDocument()
    expect(screen.getByText(/solo lectura/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Motivos de fraude' })).toBeInTheDocument()
  })
})

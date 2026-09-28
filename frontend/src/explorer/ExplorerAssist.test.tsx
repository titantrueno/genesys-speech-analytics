import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { explorerRoutes, fakeId } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import { decodeQuery, type ExplorerQuery } from './queryModel'

const INTERPRETED: ExplorerQuery = { root: { op: 'and', conditions: [
  { field: 'channel', operator: 'is', value: 'chat' },
  { field: 'resolution', operator: 'is', value: 'escalada' },
] } }

interface Saved { id: string; name: string; query: ExplorerQuery; created_at: string; updated_at: string }

function setup(options: { interpret?: (text: string) => { status: number; body?: unknown }; saved?: Saved[] } = {}) {
  const bodies: ExplorerQuery[] = []
  const calls: Array<{ method: string; path: string; body?: unknown }> = []
  let saved = [...(options.saved ?? [])]
  const record = (method: string, path: string, init: RequestInit) => {
    const body = init.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    return body
  }
  const itemRoutes = (item: Saved) => ({
    [`PATCH /api/query/saved/${item.id}`]: (init: RequestInit & { url: string }) => {
      const body = record('PATCH', item.id, init)
      saved = saved.map((s) => (s.id === item.id ? { ...s, ...body } : s))
      return { status: 200, body: saved.find((s) => s.id === item.id) }
    },
    [`DELETE /api/query/saved/${item.id}`]: (init: RequestInit & { url: string }) => {
      record('DELETE', item.id, init)
      saved = saved.filter((s) => s.id !== item.id)
      return { status: 204 }
    },
  })
  const routes = {
    ...explorerRoutes(bodies as unknown[]),
    'POST /api/query/interpret': (init: RequestInit & { url: string }) => {
      const { text } = record('POST', 'interpret', init)
      return options.interpret?.(text) ?? { status: 200, body: { query: INTERPRETED, unrecognized: [] } }
    },
    'GET /api/query/saved': () => ({ status: 200, body: { items: saved } }),
    'POST /api/query/saved': (init: RequestInit & { url: string }) => {
      const body = record('POST', 'saved', init)
      const item = { id: fakeId('1QY', saved.length + 10), ...body, created_at: 'x', updated_at: 'x' }
      saved = [item, ...saved]
      Object.assign(routes, itemRoutes(item))
      return { status: 201, body: item }
    },
    ...Object.assign({}, ...(options.saved ?? []).map(itemRoutes)),
  }
  signedInAs(USERS.analista, routes)
  const result = renderApp('/explorador')
  const urlQuery = () => decodeQuery(new URLSearchParams(result.router.state.location.search).get('q')).query
  return { ...result, bodies, calls, urlQuery, last: () => bodies[bodies.length - 1] }
}

async function interpret(phrase: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Describe lo que buscas'), phrase)
  await user.click(screen.getByRole('button', { name: 'Interpretar' }))
}

describe('consulta en lenguaje natural', () => {
  it('carga las condiciones interpretadas en el constructor y las ejecuta', async () => {
    const { calls, last, urlQuery } = setup()
    await interpret('chats escalados')
    expect(calls.find((c) => c.path === 'interpret')?.body).toEqual({ text: 'chats escalados' })
    await screen.findByRole('group', { name: 'Condición 2' })
    expect(within(screen.getByRole('group', { name: 'Condición 1' })).getByLabelText('Campo')).toHaveValue('channel')
    expect(screen.getByText('Canal es Chat Y Resolución es Escalada')).toBeInTheDocument()
    expect(urlQuery()).toEqual(INTERPRETED)
    await waitFor(() => expect(last()).toEqual(INTERPRETED))
    expect(screen.getByRole('status')).toHaveTextContent(/revisa las condiciones/i)
  })

  it('avisa de las palabras que no ha entendido', async () => {
    setup({ interpret: () => ({ status: 200, body: { query: INTERPRETED, unrecognized: ['arcoíris', 'zodiaco'] } }) })
    await interpret('chats escalados con arcoíris y zodiaco')
    expect(await screen.findByRole('alert')).toHaveTextContent('No he entendido: arcoíris, zodiaco')
  })

  it('muestra el error si la frase no es válida', async () => {
    setup({ interpret: () => ({ status: 422, body: { detail: 'Escribe una frase' } }) })
    await interpret('x')
    expect(await screen.findByRole('alert')).toHaveTextContent('Escribe una frase')
  })
})

describe('consultas guardadas', () => {
  const existing: Saved = { id: fakeId('1QY', 1), name: 'Fraude en chat', query: INTERPRETED, created_at: 'x', updated_at: 'x' }

  it('lista las consultas del usuario y carga una en el constructor', async () => {
    const { urlQuery } = setup({ saved: [existing] })
    const panel = await screen.findByRole('region', { name: 'Consultas guardadas' })
    const item = await within(panel).findByRole('listitem')
    expect(item).toHaveTextContent('Fraude en chat')
    await userEvent.setup().click(within(item).getByRole('button', { name: 'Cargar' }))
    await waitFor(() => expect(urlQuery()).toEqual(INTERPRETED))
    expect(screen.getByText('Canal es Chat Y Resolución es Escalada')).toBeInTheDocument()
  })

  it('guarda la consulta actual sin las condiciones incompletas', async () => {
    const { calls } = setup()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Añadir condición' }))
    await user.click(screen.getByRole('button', { name: 'Añadir condición' }))
    await user.selectOptions(within(screen.getByRole('group', { name: 'Condición 2' })).getByLabelText('Campo'), 'transcript')
    const panel = screen.getByRole('region', { name: 'Consultas guardadas' })
    await user.click(within(panel).getByRole('button', { name: 'Guardar consulta actual' }))
    const save = within(panel).getByRole('button', { name: 'Guardar' })
    expect(save).toBeDisabled()
    await user.type(within(panel).getByLabelText('Nombre'), '  Mis llamadas  ')
    await user.click(save)
    await waitFor(() => expect(calls.find((c) => c.path === 'saved')?.body).toEqual({
      name: 'Mis llamadas',
      query: { root: { op: 'and', conditions: [{ field: 'channel', operator: 'is', value: 'voz' }] } },
    }))
    expect(await within(panel).findByText('Mis llamadas')).toBeInTheDocument()
  })

  it('renombra y borra con confirmación', async () => {
    const { calls } = setup({ saved: [existing] })
    const user = userEvent.setup()
    const panel = await screen.findByRole('region', { name: 'Consultas guardadas' })
    const item = await within(panel).findByRole('listitem')
    await user.click(within(item).getByRole('button', { name: 'Renombrar' }))
    const input = within(item).getByLabelText('Nuevo nombre')
    await user.clear(input)
    await user.type(input, 'Fraude escalado{Enter}')
    await waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ name: 'Fraude escalado' }))
    expect(await within(panel).findByText('Fraude escalado')).toBeInTheDocument()

    await user.click(within(panel).getByRole('button', { name: 'Borrar' }))
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await user.click(within(panel).getByRole('button', { name: 'Confirmar borrado' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
    expect(await within(panel).findByText(/no tienes consultas guardadas/i)).toBeInTheDocument()
  })
})

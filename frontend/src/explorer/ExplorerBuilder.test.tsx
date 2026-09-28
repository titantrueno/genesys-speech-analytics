import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { explorerRoutes, QUEUE } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import { decodeQuery, encodeQuery, type ExplorerQuery } from './queryModel'

type Body = ExplorerQuery

async function openExplorer(path = '/explorador', run?: Parameters<typeof explorerRoutes>[1]) {
  const bodies: Body[] = []
  signedInAs(USERS.analista, explorerRoutes(bodies as unknown[], run))
  const result = renderApp(path)
  await screen.findByRole('heading', { level: 1, name: 'Explorador' })
  await screen.findByRole('button', { name: 'Añadir condición' })
  const last = () => bodies[bodies.length - 1]
  const urlQuery = () => decodeQuery(new URLSearchParams(result.router.state.location.search).get('q')).query
  return { ...result, bodies, last, urlQuery }
}

function row(n: string) {
  return screen.getByRole('group', { name: `Condición ${n}` })
}

async function addCondition(user = userEvent.setup(), container: HTMLElement = document.body) {
  await user.click(within(container).getAllByRole('button', { name: 'Añadir condición' })[0])
}

describe('constructor de consultas', () => {
  it('sin consulta muestra todas las conversaciones y ejecuta la consulta vacía', async () => {
    const { last } = await openExplorer()
    expect(screen.getByText('Todas las conversaciones del periodo')).toBeInTheDocument()
    await waitFor(() => expect(last()).toEqual({ root: { op: 'and', conditions: [] } }))
  })

  it('añadir una condición la ejecuta, la describe y la guarda en la URL', async () => {
    const { last, urlQuery } = await openExplorer()
    await addCondition()
    expect(within(row('1')).getByLabelText('Campo')).toHaveValue('channel')
    await waitFor(() => expect(last().root.conditions).toEqual([{ field: 'channel', operator: 'is', value: 'voz' }]))
    expect(screen.getByText('Canal es Voz')).toBeInTheDocument()
    expect(urlQuery().root.conditions).toHaveLength(1)
  })

  it('los valores categóricos muestran sugerencias con recuento', async () => {
    await openExplorer()
    await addCondition()
    const value = within(row('1')).getByLabelText('Valor')
    await waitFor(() => expect(within(value).getByRole('option', { name: 'Chat (127)' })).toBeInTheDocument())
    await userEvent.setup().selectOptions(value, 'chat')
    expect(screen.getByText('Canal es Chat')).toBeInTheDocument()
  })

  it('solo ofrece los operadores del tipo de campo y adapta el control de valor', async () => {
    const { last } = await openExplorer()
    const user = userEvent.setup()
    await addCondition(user)
    await user.selectOptions(within(row('1')).getByLabelText('Campo'), 'sentiment')
    const operators = within(within(row('1')).getByLabelText('Operador')).getAllByRole('option').map((o) => o.textContent)
    expect(operators).toEqual(['=', '≠', '>', '≥', '<', '≤', 'entre'])
    await user.selectOptions(within(row('1')).getByLabelText('Operador'), 'lt')
    const value = within(row('1')).getByLabelText('Valor')
    await user.clear(value)
    await user.type(value, '-0.3')
    await waitFor(() => expect(last().root.conditions).toEqual([{ field: 'sentiment', operator: 'lt', value: -0.3 }]))

    await user.selectOptions(within(row('1')).getByLabelText('Operador'), 'between')
    expect(within(row('1')).getByLabelText('Mínimo')).toBeInTheDocument()
    expect(within(row('1')).getByLabelText('Máximo')).toBeInTheDocument()

    await user.selectOptions(within(row('1')).getByLabelText('Campo'), 'check:verificacion_identidad')
    expect(within(row('1')).queryByLabelText('Valor')).toBeNull()
    await user.selectOptions(within(row('1')).getByLabelText('Operador'), 'fails')
    await waitFor(() => expect(last().root.conditions).toEqual([{ field: 'check:verificacion_identidad', operator: 'fails' }]))

    await user.selectOptions(within(row('1')).getByLabelText('Campo'), 'repeat_contact')
    expect(within(within(row('1')).getByLabelText('Valor')).getAllByRole('option').map((o) => o.textContent)).toEqual(['Sí', 'No'])
  })

  it('una condición de texto vacía no se envía y se pide completarla', async () => {
    const { last } = await openExplorer()
    const user = userEvent.setup()
    await addCondition(user)
    await user.selectOptions(within(row('1')).getByLabelText('Campo'), 'transcript')
    expect(within(row('1')).getByText('Escribe el texto a buscar')).toBeInTheDocument()
    await waitFor(() => expect(last().root.conditions).toEqual([]))
    await user.selectOptions(within(row('1')).getByLabelText('Hablante'), 'cliente')
    await user.type(within(row('1')).getByLabelText('Valor'), 'no reconozco')
    await waitFor(() => expect(last().root.conditions).toEqual([
      { field: 'transcript', operator: 'contains', value: 'no reconozco', speaker: 'cliente' },
    ]))
  })

  it('«es alguno de» permite elegir varios valores', async () => {
    const { last } = await openExplorer()
    const user = userEvent.setup()
    await addCondition(user)
    await user.selectOptions(within(row('1')).getByLabelText('Campo'), 'resolution')
    await user.selectOptions(within(row('1')).getByLabelText('Operador'), 'in')
    await user.click(within(row('1')).getByRole('button', { name: /valores/i }))
    await user.click(await screen.findByRole('checkbox', { name: 'Escalada (51)' }))
    await waitFor(() => expect(last().root.conditions[0]).toMatchObject({ field: 'resolution', operator: 'in' }))
    expect((last().root.conditions[0] as { value: string[] }).value.sort()).toEqual(['escalada', 'resuelta'])
  })

  it('agrupa condiciones con Y/O y limita el anidamiento a dos niveles', async () => {
    const { last, urlQuery } = await openExplorer()
    const user = userEvent.setup()
    await addCondition(user)
    await user.click(screen.getByRole('button', { name: 'Añadir grupo' }))
    const subgroup = screen.getByRole('region', { name: 'Subgrupo 2' })
    expect(within(subgroup).queryByRole('button', { name: 'Añadir grupo' })).toBeNull()
    await user.click(within(subgroup).getByRole('button', { name: 'O' }))
    await addCondition(user, subgroup)
    await addCondition(user, subgroup)
    await user.selectOptions(within(row('2.2')).getByLabelText('Campo'), 'resolution')
    await user.selectOptions(within(row('2.2')).getByLabelText('Valor'), 'escalada')
    await waitFor(() => expect(last().root.conditions[1]).toEqual({ op: 'or', conditions: [
      { field: 'channel', operator: 'is', value: 'voz' },
      { field: 'resolution', operator: 'is', value: 'escalada' },
    ] }))
    expect(screen.getByText('Canal es Voz Y (Canal es Voz O Resolución es Escalada)')).toBeInTheDocument()

    await user.click(within(row('1')).getByRole('button', { name: 'Quitar condición' }))
    await waitFor(() => expect(last().root.conditions).toHaveLength(1))
    await user.click(screen.getByRole('button', { name: 'Quitar grupo' }))
    expect(urlQuery().root.conditions).toEqual([])
    expect(screen.getByText('Todas las conversaciones del periodo')).toBeInTheDocument()
  })

  it('el periodo forma parte de la consulta', async () => {
    const { last } = await openExplorer()
    expect(screen.getByLabelText('Desde')).toHaveValue('2026-08-28')
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-09-01' } })
    await waitFor(() => expect(last()).toMatchObject({ from: '2026-09-01', to: '2026-09-26' }))
  })

  it('al abrir un enlace con consulta restaura el constructor', async () => {
    const query: ExplorerQuery = { from: '2026-09-01', to: '2026-09-20', root: { op: 'and', conditions: [
      { field: 'queue', operator: 'is', value: QUEUE.tarjetas.id },
      { field: 'duration', operator: 'between', value: [60, 300] },
    ] } }
    const { last } = await openExplorer(`/explorador?q=${encodeQuery(query)}`)
    expect(screen.getByText('Cola es Tarjetas Y Duración (s) entre 60 y 300')).toBeInTheDocument()
    expect(within(row('2')).getByLabelText('Mínimo')).toHaveValue(60)
    await waitFor(() => expect(last()).toEqual(query))
  })

  it('un enlace corrupto avisa y carga la consulta por defecto', async () => {
    await openExplorer('/explorador?q=corrupto!!')
    expect(screen.getByRole('alert')).toHaveTextContent(/enlace de la consulta no es válido/i)
    expect(screen.getByText('Todas las conversaciones del periodo')).toBeInTheDocument()
  })

  it('los errores de validación de la API se muestran en su condición', async () => {
    await openExplorer('/explorador', (body) => {
      const conditions = (body as Body).root.conditions
      return conditions.length
        ? { status: 422, body: { detail: [{ path: 'root.conditions[0]', message: 'Valor no válido para Canal: fax' }] } }
        : { status: 200, body: { total: 0, items: [], kpis: [], page: 1, page_size: 25, pages: 0, period: { from: '', to: '' } } }
    })
    await addCondition()
    expect(await within(row('1')).findByRole('alert')).toHaveTextContent('Valor no válido para Canal: fax')
  })
})

describe('errores de validación sin condición asociada', () => {
  it('se muestran como aviso general', async () => {
    await openExplorer('/explorador', () => ({
      status: 422, body: { detail: [{ path: 'from', message: "'from' debe ser anterior o igual a 'to'" }] },
    }))
    expect(await screen.findByRole('alert')).toHaveTextContent("'from' debe ser anterior o igual a 'to'")
  })
})

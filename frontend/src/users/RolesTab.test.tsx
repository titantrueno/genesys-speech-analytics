import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { PERMISSION_OPTIONS, ROLES } from '../test/userFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

type Call = { method: string; path: string; body?: unknown }
type Reply = { status: number; body?: unknown }

function setup(reply: Record<string, (body: unknown) => Reply> = {}, roles = ROLES) {
  const calls: Call[] = []
  const record = (method: string, path: string, fallback: (body: unknown) => Reply) => (init: RequestInit) => {
    const body = init.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    return (reply[`${method} ${path}`] ?? fallback)(body)
  }
  const routes: Record<string, (init: RequestInit) => Reply> = {
    'GET /api/roles': () => ({ status: 200, body: { items: roles, permissions: PERMISSION_OPTIONS } }),
    'GET /api/users/audit': () => ({ status: 200, body: { items: [] } }),
    'POST /api/roles': record('POST', 'roles', (body) => ({ status: 201, body })),
  }
  for (const r of roles) {
    routes[`PUT /api/roles/${r.id}`] = record('PUT', r.code, (body) => ({ status: 200, body }))
    routes[`DELETE /api/roles/${r.id}`] = record('DELETE', r.code, () => ({ status: 204 }))
  }
  signedInAs(USERS.admin, routes)
  renderApp('/usuarios?tab=roles')
  return { calls }
}

const rolesTable = async () => screen.findByRole('table', { name: 'Roles' })
const matrix = async () => screen.findByRole('table', { name: 'Permisos por rol' })
const roleRow = async (name: string) =>
  within(await rolesTable()).getAllByRole('row').find((r) => r.querySelector('th, td')?.textContent === name) as HTMLElement

describe('Usuarios y roles: pestaña Roles', () => {
  it('lista los roles con su tipo y su nº de usuarios', async () => {
    setup()
    const header = within(await rolesTable()).getAllByRole('columnheader').map((h) => h.textContent)
    expect(header).toEqual(['Rol', 'Código', 'Tipo', 'Usuarios', 'Acciones'])
    expect(await roleRow('Consulta')).toHaveTextContent(/viewer\s*Base\s*1/)
    expect(await roleRow('Auditor')).toHaveTextContent(/auditor\s*Personalizado\s*0/)
  })

  it('solo se pueden borrar los roles personalizados sin usuarios, con confirmación', async () => {
    const roles = [...ROLES, { ...ROLES[4], id: '1RO-00000006-0000-5000-8000-000000000006', code: 'en_uso', name: 'En uso', users: 2 }]
    const { calls } = setup({}, roles)
    for (const name of ['Administrador', 'Supervisor', 'Analista', 'Consulta', 'En uso']) {
      expect(within(await roleRow(name)).queryByRole('button', { name: 'Borrar' }), name).not.toBeInTheDocument()
    }
    const auditor = await roleRow('Auditor')
    await userEvent.click(within(auditor).getByRole('button', { name: 'Borrar' }))
    expect(calls).toEqual([])
    await userEvent.click(within(auditor).getByRole('button', { name: 'Confirmar' }))
    await waitFor(() => expect(calls).toEqual([{ method: 'DELETE', path: 'auditor', body: undefined }]))
  })

  it('crea un rol personalizado, sin permisos hasta marcarlos en la matriz', async () => {
    const { calls } = setup()
    await rolesTable()
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo rol' }))
    const form = screen.getByRole('form', { name: 'Nuevo rol' })
    await userEvent.type(within(form).getByLabelText('Código'), 'lector_flujos')
    await userEvent.type(within(form).getByLabelText('Nombre'), 'Lector de flujos')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toEqual([{ method: 'POST', path: 'roles', body: {
      code: 'lector_flujos', name: 'Lector de flujos', permissions: [],
    } }]))
  })

  it('un código duplicado (409) se muestra junto al campo', async () => {
    setup({ 'POST roles': () => ({ status: 409, body: { detail: [
      { loc: ['body', 'code'], msg: 'Ya existe un rol con ese código', type: 'value_error' }] } }) })
    await rolesTable()
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo rol' }))
    const form = screen.getByRole('form', { name: 'Nuevo rol' })
    await userEvent.type(within(form).getByLabelText('Código'), 'admin')
    await userEvent.type(within(form).getByLabelText('Nombre'), 'Otro')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(within(form).getByLabelText('Código')).toHaveAccessibleDescription(/Ya existe un rol con ese código/))
  })

  it('la matriz tiene los permisos en filas y los roles en columnas, marcados según sus permisos', async () => {
    setup()
    const table = await matrix()
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent))
      .toEqual(['Permiso', 'Administrador', 'Supervisor', 'Analista', 'Consulta', 'Auditor'])
    expect(within(table).getAllByRole('rowheader').map((h) => h.textContent)).toEqual(PERMISSION_OPTIONS.map((p) => p.label))
    expect(within(table).getByRole('checkbox', { name: 'Usar la búsqueda semántica · Analista' })).toBeChecked()
    expect(within(table).getByRole('checkbox', { name: 'Usar la búsqueda semántica · Consulta' })).not.toBeChecked()
    expect(within(table).getByRole('checkbox', { name: 'Ver configuración · Auditor' })).toBeChecked()
  })

  it('al cambiar una casilla guarda los permisos del rol en el orden del catálogo', async () => {
    const { calls } = setup()
    const table = await matrix()
    await userEvent.click(within(table).getByRole('checkbox', { name: 'Usar la búsqueda semántica · Analista' }))
    await userEvent.click(within(table).getByRole('checkbox', { name: 'Ver dashboards · Auditor' }))
    await waitFor(() => expect(calls).toEqual([
      { method: 'PUT', path: 'analista', body: { name: 'Analista', permissions: [
        'dashboards:view', 'conversations:view', 'explorer:use', 'flows:view', 'flows:edit'] } },
      { method: 'PUT', path: 'auditor', body: { name: 'Auditor', permissions: ['dashboards:view', 'config:view'] } },
    ]))
  })

  it('muestra el motivo cuando una protección rechaza el cambio de permisos', async () => {
    setup({ 'PUT admin': () => ({ status: 409, body: {
      detail: 'No puedes quitarte a ti mismo el permiso de administrar usuarios y roles' } }) })
    await userEvent.click(within(await matrix()).getByRole('checkbox', { name: 'Administrar usuarios y roles · Administrador' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No puedes quitarte a ti mismo')
  })
})

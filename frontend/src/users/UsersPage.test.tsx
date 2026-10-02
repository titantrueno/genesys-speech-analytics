import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MANAGED_USERS, PERMISSION_OPTIONS, ROLES } from '../test/userFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

type Call = { method: string; path: string; body?: unknown; query?: Record<string, string[]> }
type Reply = { status: number; body?: unknown }

function setup(options: { path?: string; reply?: Record<string, (body: unknown) => Reply>; users?: () => Reply } = {}) {
  const calls: Call[] = []
  const record = (method: string, path: string, fallback: (body: unknown) => Reply) => (init: RequestInit & { url: string }) => {
    const body = init.body ? JSON.parse(String(init.body)) : undefined
    const params = new URL(init.url, 'http://localhost').searchParams
    const query: Record<string, string[]> = {}
    params.forEach((value, key) => { query[key] = [...(query[key] ?? []), value] })
    calls.push({ method, path, body, query })
    return (options.reply?.[`${method} ${path}`] ?? fallback)(body)
  }
  const routes: Record<string, (init: RequestInit & { url: string }) => Reply> = {
    'GET /api/users': record('GET', 'users', () => options.users?.() ?? { status: 200, body: { items: MANAGED_USERS } }),
    'GET /api/roles': () => ({ status: 200, body: { items: ROLES, permissions: PERMISSION_OPTIONS } }),
    'GET /api/users/audit': () => ({ status: 200, body: { items: [{
      id: '1AU-00000001-0000-4000-8000-000000000001', user: { id: USERS.admin.id, name: 'Admin Demo' }, at: '2026-10-01T09:00:00+00:00',
      section: 'usuarios', element: 'Usuario «Bea Baja»', before: { active: true }, after: { active: false },
    }] } }),
    'POST /api/users': record('POST', 'users', (body) => ({ status: 201, body })),
  }
  for (const u of MANAGED_USERS) routes[`PUT /api/users/${u.id}`] = record('PUT', u.email, (body) => ({ status: 200, body }))
  signedInAs(USERS.admin, routes)
  const { router } = renderApp(options.path ?? '/usuarios')
  return { calls, router, writes: () => calls.filter((c) => c.method !== 'GET') }
}

const usersTable = async () => screen.findByRole('table', { name: 'Usuarios' })
const rowOf = async (name: string) =>
  within(await usersTable()).getAllByRole('row').find((r) => r.textContent?.includes(name)) as HTMLElement

describe('Usuarios y roles: sección', () => {
  it('tiene las pestañas Usuarios y Roles y la pestaña vive en la URL', async () => {
    const { router } = setup()
    const tabs = await screen.findAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Usuarios', 'Roles'])
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    await userEvent.click(tabs[1])
    expect(await screen.findByRole('tab', { name: 'Roles' })).toHaveAttribute('aria-selected', 'true')
    expect(router.state.location.search).toBe('?tab=roles')
  })

  it('sin `users:admin` no aparece en el menú y por URL muestra "Sin acceso"', async () => {
    signedInAs(USERS.supervisor)
    renderApp('/usuarios')
    expect(await screen.findByRole('heading', { name: /sin acceso/i })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: /principal/i })
    expect(within(nav).queryByRole('link', { name: 'Usuarios y roles' })).not.toBeInTheDocument()
  })
})

describe('Usuarios y roles: pestaña Usuarios', () => {
  it('lista nombre, email, rol, estado y último acceso', async () => {
    setup()
    const header = within(await usersTable()).getAllByRole('columnheader').map((h) => h.textContent)
    expect(header).toEqual(['Nombre', 'Email', 'Rol', 'Estado', 'Último acceso', 'Acciones'])
    const bea = await rowOf('Bea Baja')
    expect(bea).toHaveTextContent('bea@bancohorizonte.demo')
    expect(bea).toHaveTextContent('Consulta')
    expect(bea).toHaveTextContent('Inactivo')
    expect(bea).toHaveTextContent('20 sept')
    expect(await rowOf('Analista Demo')).toHaveTextContent('Nunca')
  })

  it('busca por nombre o email y filtra por rol y estado', async () => {
    const { calls } = setup()
    await usersTable()
    await userEvent.type(screen.getByLabelText('Buscar'), 'bea')
    await userEvent.selectOptions(screen.getByLabelText('Rol'), 'viewer')
    await userEvent.selectOptions(screen.getByLabelText('Estado'), 'false')
    await waitFor(() => expect(calls.at(-1)?.query).toEqual({ q: ['bea'], role: ['viewer'], active: ['false'] }))
    expect(within(screen.getByLabelText('Rol')).getAllByRole('option').map((o) => o.textContent))
      .toEqual(['Todos', 'Administrador', 'Supervisor', 'Analista', 'Consulta', 'Auditor'])
  })

  it('crea un usuario', async () => {
    const { writes } = setup()
    await usersTable()
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo usuario' }))
    const form = screen.getByRole('form', { name: 'Nuevo usuario' })
    await userEvent.type(within(form).getByLabelText('Nombre'), 'Lucía Pérez')
    await userEvent.type(within(form).getByLabelText('Email'), 'lucia@bancohorizonte.demo')
    await userEvent.selectOptions(within(form).getByLabelText('Rol'), 'auditor')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(writes()).toEqual([expect.objectContaining({ method: 'POST', body: {
      name: 'Lucía Pérez', email: 'lucia@bancohorizonte.demo', role: 'auditor', active: true,
    } })]))
    await waitFor(() => expect(screen.queryByRole('form', { name: 'Nuevo usuario' })).not.toBeInTheDocument())
  })

  it('un email duplicado (409) se muestra junto al campo sin perder lo escrito', async () => {
    setup({ reply: { 'POST users': () => ({ status: 409, body: { detail: [
      { loc: ['body', 'email'], msg: 'Ya existe un usuario con ese email', type: 'value_error' }] } }) } })
    await usersTable()
    await userEvent.click(screen.getByRole('button', { name: 'Nuevo usuario' }))
    const form = screen.getByRole('form', { name: 'Nuevo usuario' })
    await userEvent.type(within(form).getByLabelText('Nombre'), 'Otra Admin')
    await userEvent.type(within(form).getByLabelText('Email'), 'admin@bancohorizonte.demo')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    const email = within(form).getByLabelText('Email')
    await waitFor(() => expect(email).toHaveAccessibleDescription('Ya existe un usuario con ese email'))
    expect(email).toHaveAttribute('aria-invalid', 'true')
    expect(email).toHaveValue('admin@bancohorizonte.demo')
    expect(within(form).getByLabelText('Nombre')).toHaveValue('Otra Admin')
  })

  it('edita nombre y rol de un usuario', async () => {
    const { writes } = setup()
    await userEvent.click(within(await rowOf('Analista Demo')).getByRole('button', { name: 'Editar Analista Demo' }))
    const form = screen.getByRole('form', { name: 'Editar usuario «Analista Demo»' })
    const name = within(form).getByLabelText('Nombre')
    await userEvent.clear(name)
    await userEvent.type(name, 'Ana Lista')
    await userEvent.selectOptions(within(form).getByLabelText('Rol'), 'viewer')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(writes()).toEqual([expect.objectContaining({ method: 'PUT', path: 'analista@bancohorizonte.demo', body: {
      name: 'Ana Lista', email: 'analista@bancohorizonte.demo', role: 'viewer', active: true,
    } })]))
  })

  it('desactiva con confirmación y reactiva', async () => {
    const { writes } = setup()
    const analista = await rowOf('Analista Demo')
    await userEvent.click(within(analista).getByRole('button', { name: 'Desactivar' }))
    expect(writes()).toEqual([])
    await userEvent.click(within(analista).getByRole('button', { name: 'Confirmar' }))
    await userEvent.click(within(await rowOf('Bea Baja')).getByRole('button', { name: 'Reactivar' }))
    await waitFor(() => expect(writes().map((c) => [c.path, (c.body as { active: boolean }).active])).toEqual([
      ['analista@bancohorizonte.demo', false], ['bea@bancohorizonte.demo', true],
    ]))
  })

  it('muestra el motivo cuando una protección rechaza el cambio', async () => {
    setup({ reply: { 'PUT admin@bancohorizonte.demo': () => ({ status: 409, body: {
      detail: 'No puedes quitarte a ti mismo el permiso de administrar usuarios y roles' } }) } })
    const admin = await rowOf('Admin Demo')
    await userEvent.click(within(admin).getByRole('button', { name: 'Desactivar' }))
    await userEvent.click(within(admin).getByRole('button', { name: 'Confirmar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No puedes quitarte a ti mismo el permiso')
  })

  it('muestra el registro de cambios de usuarios y roles', async () => {
    setup()
    const log = await screen.findByRole('region', { name: 'Registro de cambios' })
    expect(await within(log).findByText('Usuario «Bea Baja»')).toBeInTheDocument()
    expect(within(log).getByText('active: no')).toBeInTheDocument()
  })

  it('muestra cargando y error', async () => {
    setup({ users: () => ({ status: 500 }) })
    expect(screen.getByText(/cargando/i)).toBeInTheDocument()
    expect(await screen.findByText('No se han podido cargar los usuarios.')).toBeInTheDocument()
  })
})

import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MANAGED_USERS, PERMISSION_OPTIONS, ROLES } from '../test/userFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

const english = { 'GET /api/config/public': () => ({ status: 200, body: { platform_name: 'Speech & Text Analytics', timezone: 'UTC', language: 'en-US' } }) }

function setup(path: string) {
  signedInAs(USERS.admin, {
    ...english,
    'GET /api/users': () => ({ status: 200, body: { items: MANAGED_USERS } }),
    'GET /api/roles': () => ({ status: 200, body: { items: ROLES, permissions: PERMISSION_OPTIONS } }),
    'GET /api/users/audit': () => ({ status: 200, body: { items: [] } }),
  })
  return renderApp(path)
}

describe('Usuarios y roles con la interfaz en inglés (FE016, T6)', () => {
  it('usuarios: cabeceras, estados y acciones en inglés; nombres, emails y roles son datos', async () => {
    setup('/usuarios')
    expect(await screen.findByRole('heading', { level: 1, name: 'Users and roles' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Users' })).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Users' })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(
      ['Name', 'Email', 'Role', 'Status', 'Last sign-in', 'Actions'])
    const active = within(table).getAllByRole('row').find((r) => r.textContent?.includes('Admin Demo')) as HTMLElement
    expect(within(active).getByText('Active')).toBeInTheDocument()
    expect(within(active).getByText('Administrador')).toBeInTheDocument()
    expect(within(active).getByRole('button', { name: 'Edit Admin Demo' })).toBeInTheDocument()
    const never = within(table).getAllByRole('row').find((r) => r.textContent?.includes('Analista Demo')) as HTMLElement
    expect(within(never).getByText('Never')).toBeInTheDocument()
    const inactive = within(table).getAllByRole('row').find((r) => r.textContent?.includes('Bea Baja')) as HTMLElement
    expect(within(inactive).getByText('Inactive')).toBeInTheDocument()
    expect(within(inactive).getByRole('button', { name: 'Reactivate' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New user' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'New user' }))
    const form = await screen.findByRole('form', { name: 'New user' })
    for (const label of ['Name', 'Email', 'Role']) expect(within(form).getByLabelText(label)).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: 'Save' })).toBeInTheDocument()
  })

  it('roles: tipos y matriz de permisos en inglés; los nombres de los roles son datos', async () => {
    setup('/usuarios?tab=roles')
    const roles = await screen.findByRole('table', { name: 'Roles' })
    expect(within(roles).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Role', 'Code', 'Type', 'Users', 'Actions'])
    expect(within(roles).getAllByText('Built-in').length).toBe(4)
    expect(within(roles).getByText('Custom')).toBeInTheDocument()
    expect(within(roles).getByText('Administrador')).toBeInTheDocument()
    expect(screen.getByText(/The base roles cannot be deleted/)).toBeInTheDocument()

    const matrix = await screen.findByRole('table', { name: 'Permissions by role' })
    expect(within(matrix).getByRole('columnheader', { name: 'Permission' })).toBeInTheDocument()
    expect(within(matrix).getByRole('rowheader', { name: 'View dashboards' })).toBeInTheDocument()
    expect(within(matrix).getByRole('rowheader', { name: 'Manage users and roles' })).toBeInTheDocument()
    expect(within(matrix).getByRole('checkbox', { name: 'Edit and run flows · Analista' })).toBeChecked()
  })
})

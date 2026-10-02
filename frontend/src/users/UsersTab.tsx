import { useDeferredValue, useState } from 'react'
import { fieldErrors } from '../config/api'
import { Card, ConfigField, ConfirmAction, input, smallButton } from '../config/controls'
import { formatDateTimeWithYear } from '../lib/format'
import { useRoles, useUsers, userRequests, useUsersMutation } from './api'
import { actionError } from './errors'
import type { ManagedUser, RoleItem, UserFilters, UserInput } from './types'

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'true', label: 'Activos' },
  { value: 'false', label: 'Inactivos' },
]

const editable = ({ name, email, role, active }: ManagedUser): UserInput => ({ name, email, role, active })

function UserForm({ user, roles, onDone }: { user?: ManagedUser; roles: RoleItem[]; onDone: () => void }) {
  const defaultRole = roles.find((r) => r.code === 'viewer')?.code ?? roles[0]?.code ?? ''
  const [draft, setDraft] = useState<UserInput>(user ? editable(user) : { name: '', email: '', role: defaultRole, active: true })
  const save = useUsersMutation((body: UserInput) => user ? userRequests.updateUser({ id: user.id, body }) : userRequests.createUser(body))
  const errors = fieldErrors(save.error)
  const generic = save.isError && Object.keys(errors).length === 0
  const title = user ? `Editar usuario «${user.name}»` : 'Nuevo usuario'
  return (
    <form aria-label={title} className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4"
      onSubmit={(e) => { e.preventDefault(); save.mutate(draft, { onSuccess: onDone }) }}>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <div className="grid gap-3 sm:grid-cols-3">
        <ConfigField label="Nombre" error={errors.name}>
          <input className={input} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </ConfigField>
        <ConfigField label="Email" error={errors.email}>
          <input className={input} type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
        </ConfigField>
        <ConfigField label="Rol" error={errors.role}>
          <select className={input} value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })}>
            {roles.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
          </select>
        </ConfigField>
      </div>
      {generic && <p role="alert" className="text-sm text-red-700">{actionError(save.error)}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={save.isPending}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">Guardar</button>
        <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={onDone}>Cancelar</button>
      </div>
    </form>
  )
}

export function UsersTab() {
  const [filters, setFilters] = useState<UserFilters>({ q: '', role: '', active: '' })
  const q = useDeferredValue(filters.q.trim())
  const users = useUsers({ ...filters, q })
  const roles = useRoles()
  const [editing, setEditing] = useState<ManagedUser | 'new' | null>(null)
  const update = useUsersMutation(userRequests.updateUser)
  const roleItems = roles.data?.items ?? []
  const setActive = (user: ManagedUser, active: boolean) => update.mutate({ id: user.id, body: { ...editable(user), active } })

  return (
    <Card title="Usuarios" description="Un usuario desactivado no puede iniciar sesión y su sesión abierta deja de valer.">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-64">
          <ConfigField label="Buscar">
            <input className={input} type="search" placeholder="Nombre o email" value={filters.q}
              onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
          </ConfigField>
        </div>
        <div className="w-44">
          <ConfigField label="Rol">
            <select className={input} value={filters.role} onChange={(e) => setFilters({ ...filters, role: e.target.value })}>
              <option value="">Todos</option>
              {roleItems.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
            </select>
          </ConfigField>
        </div>
        <div className="w-36">
          <ConfigField label="Estado">
            <select className={input} value={filters.active}
              onChange={(e) => setFilters({ ...filters, active: e.target.value as UserFilters['active'] })}>
              {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </ConfigField>
        </div>
        {editing === null && roles.data && (
          <button type="button" className={`${smallButton} ml-auto`} onClick={() => setEditing('new')}>Nuevo usuario</button>
        )}
      </div>
      {editing !== null && roles.data && (
        <UserForm key={editing === 'new' ? 'new' : editing.id} user={editing === 'new' ? undefined : editing}
          roles={roleItems} onDone={() => setEditing(null)} />
      )}
      {users.isPending && <p className="text-sm text-slate-500">Cargando usuarios…</p>}
      {users.isError && <p role="alert" className="text-sm text-red-700">No se han podido cargar los usuarios.</p>}
      {users.data && users.data.items.length === 0 && <p className="text-sm text-slate-500">Ningún usuario coincide con los filtros.</p>}
      {users.data && users.data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table aria-label="Usuarios" className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {['Nombre', 'Email', 'Rol', 'Estado', 'Último acceso', 'Acciones'].map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((user) => (
                <tr key={user.id} className="border-b border-slate-100 align-top last:border-0">
                  <td className="px-2 py-2 font-medium text-slate-800">{user.name}</td>
                  <td className="px-2 py-2 text-slate-600">{user.email}</td>
                  <td className="px-2 py-2">{user.role_name}</td>
                  <td className="px-2 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${user.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                      {user.active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-2 py-2 whitespace-nowrap text-slate-600">
                    {user.last_login ? formatDateTimeWithYear(user.last_login) : 'Nunca'}
                  </td>
                  <td className="px-2 py-2">
                    <span className="inline-flex flex-wrap gap-1">
                      <button type="button" className={smallButton} aria-label={`Editar ${user.name}`} disabled={!roles.data}
                        onClick={() => setEditing(user)}>Editar</button>
                      {user.active ? (
                        <ConfirmAction label="Desactivar" question="¿No podrá iniciar sesión?" onConfirm={() => setActive(user, false)} />
                      ) : (
                        <button type="button" className={smallButton} onClick={() => setActive(user, true)}>Reactivar</button>
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {update.isError && <p role="alert" className="text-sm text-red-700">{actionError(update.error)}</p>}
    </Card>
  )
}

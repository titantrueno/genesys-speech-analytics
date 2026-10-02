import { useState } from 'react'
import { fieldErrors } from '../config/api'
import { Card, ConfigField, ConfirmAction, input, smallButton } from '../config/controls'
import { formatInteger } from '../lib/format'
import { useRoles, userRequests, useUsersMutation } from './api'
import { actionError } from './errors'
import type { PermissionOption, RoleItem } from './types'

function RoleForm({ onDone }: { onDone: () => void }) {
  const [draft, setDraft] = useState({ code: '', name: '' })
  const save = useUsersMutation(userRequests.createRole)
  const errors = fieldErrors(save.error)
  return (
    <form aria-label="Nuevo rol" className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4"
      onSubmit={(e) => { e.preventDefault(); save.mutate({ ...draft, permissions: [] }, { onSuccess: onDone }) }}>
      <h3 className="text-sm font-semibold text-slate-800">Nuevo rol</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <ConfigField label="Código" error={errors.code}
          hint="Minúsculas, números y guiones bajos (por ejemplo, lector_flujos). No se puede cambiar.">
          <input className={input} value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} />
        </ConfigField>
        <ConfigField label="Nombre" error={errors.name}>
          <input className={input} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </ConfigField>
      </div>
      <p className="text-xs text-slate-500">El rol se crea sin permisos: márcalos después en la matriz.</p>
      <div className="flex gap-2">
        <button type="submit" disabled={save.isPending}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">Guardar</button>
        <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={onDone}>Cancelar</button>
      </div>
    </form>
  )
}

function PermissionMatrix({ roles, permissions }: { roles: RoleItem[]; permissions: PermissionOption[] }) {
  const update = useUsersMutation(userRequests.updateRole)
  // Mientras se guarda un rol (hasta que termina la recarga), su columna muestra lo pulsado, no lo que había.
  const pending = update.isPending ? update.variables : undefined
  const shown = (role: RoleItem): string[] => (pending?.id === role.id ? pending.body.permissions : role.permissions)

  function toggle(role: RoleItem, permission: PermissionOption, granted: boolean) {
    const next = permissions.map((p) => p.value)
      .filter((p) => (p === permission.value ? granted : shown(role).includes(p)))
    update.mutate({ id: role.id, body: { name: role.name, permissions: next } })
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-slate-800">Permisos</h3>
      <p className="text-xs text-slate-500">Cada casilla se guarda al cambiarla y se aplica en la siguiente petición de los usuarios del rol.</p>
      <div className="overflow-x-auto">
        <table aria-label="Permisos por rol" className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs text-slate-500">
              <th scope="col" className="px-2 py-1.5 text-left font-medium">Permiso</th>
              {roles.map((role) => <th key={role.id} scope="col" className="px-2 py-1.5 text-center font-medium">{role.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {permissions.map((permission) => (
              <tr key={permission.value} className="border-b border-slate-100 last:border-0">
                <th scope="row" className="px-2 py-1.5 text-left font-normal text-slate-700">{permission.label}</th>
                {roles.map((role) => (
                  <td key={role.id} className="px-2 py-1.5 text-center">
                    <input type="checkbox" className="size-4 accent-brand-600"
                      aria-label={`${permission.label} · ${role.name}`}
                      checked={shown(role).includes(permission.value)} disabled={pending?.id === role.id}
                      onChange={(e) => toggle(role, permission, e.target.checked)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {update.isError && <p role="alert" className="text-sm text-red-700">{actionError(update.error)}</p>}
    </div>
  )
}

export function RolesTab() {
  const { data, isError, isPending } = useRoles()
  const [creating, setCreating] = useState(false)
  const remove = useUsersMutation(userRequests.deleteRole)
  return (
    <Card title="Roles"
      description="Los roles base (Administrador, Supervisor, Analista y Consulta) no se pueden borrar. Un rol personalizado solo se borra si no tiene usuarios.">
      {isPending && <p className="text-sm text-slate-500">Cargando roles…</p>}
      {isError && <p role="alert" className="text-sm text-red-700">No se han podido cargar los roles.</p>}
      {data && (
        <>
          <div className="flex justify-end">
            {!creating && <button type="button" className={smallButton} onClick={() => setCreating(true)}>Nuevo rol</button>}
          </div>
          {creating && <RoleForm onDone={() => setCreating(false)} />}
          <div className="overflow-x-auto">
            <table aria-label="Roles" className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  {['Rol', 'Código', 'Tipo', 'Usuarios', 'Acciones'].map((label) => (
                    <th key={label} scope="col" className="px-2 py-1.5 font-medium">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((role) => (
                  <tr key={role.id} className="border-b border-slate-100 align-top last:border-0">
                    <th scope="row" className="px-2 py-2 text-left font-medium text-slate-800">{role.name}</th>
                    <td className="px-2 py-2 font-mono text-xs text-slate-600">{role.code}</td>
                    <td className="px-2 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${role.builtin ? 'bg-brand-50 text-brand-700' : 'bg-slate-100 text-slate-600'}`}>
                        {role.builtin ? 'Base' : 'Personalizado'}
                      </span>
                    </td>
                    <td className="px-2 py-2 tabular-nums">{formatInteger(role.users)}</td>
                    <td className="px-2 py-2">
                      {!role.builtin && role.users === 0 && (
                        <ConfirmAction label="Borrar" question="¿Borrar el rol?" onConfirm={() => remove.mutate(role.id)} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {remove.isError && <p role="alert" className="text-sm text-red-700">{actionError(remove.error)}</p>}
          <PermissionMatrix roles={data.items} permissions={data.permissions} />
        </>
      )}
    </Card>
  )
}

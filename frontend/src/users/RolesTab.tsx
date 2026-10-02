import { Card } from '../config/controls'
import { formatInteger } from '../lib/format'
import { useRoles } from './api'

export function RolesTab() {
  const { data, isError, isPending } = useRoles()
  return (
    <Card title="Roles">
      {isPending && <p className="text-sm text-slate-500">Cargando roles…</p>}
      {isError && <p role="alert" className="text-sm text-red-700">No se han podido cargar los roles.</p>}
      {data && (
        <table aria-label="Roles" className="w-full text-sm">
          <tbody>
            {data.items.map((role) => (
              <tr key={role.id}><td>{role.name}</td><td>{formatInteger(role.users)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}

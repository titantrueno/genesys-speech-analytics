import { Tabs } from '../components/Tabs'
import { useTabParam } from '../components/useTabParam'
import { AuditLog } from '../config/AuditLog'
import { useUsersAudit } from './api'
import { RolesTab } from './RolesTab'
import { UsersTab } from './UsersTab'

const TABS = [
  { code: 'usuarios' as const, label: 'Usuarios', render: () => <UsersTab /> },
  { code: 'roles' as const, label: 'Roles', render: () => <RolesTab /> },
]

export function UsersPage() {
  const [current, select] = useTabParam(TABS)
  const audit = useUsersAudit()
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Usuarios y roles</h1>
        <p className="text-sm text-slate-500">
          Quién accede a la plataforma y qué puede hacer. Los cambios de permisos se aplican en la siguiente petición de cada usuario.
        </p>
      </header>
      <Tabs label="Usuarios y roles" idPrefix="users" tabs={TABS} current={current} onSelect={select} />
      <div role="tabpanel" id={`users-panel-${current.code}`} aria-labelledby={`users-tab-${current.code}`} className="space-y-4">
        {current.render()}
        <AuditLog query={audit} />
      </div>
    </div>
  )
}

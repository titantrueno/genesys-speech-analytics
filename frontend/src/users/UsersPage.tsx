import { Tabs } from '../components/Tabs'
import { useTabParam } from '../components/useTabParam'
import { AuditLog } from '../config/AuditLog'
import type { TKey } from '../i18n/dictionaries'
import { useI18n } from '../i18n/useI18n'
import { useUsersAudit } from './api'
import { RolesTab } from './RolesTab'
import { UsersTab } from './UsersTab'

const TABS = [
  { code: 'usuarios' as const, labelKey: 'usr.tab.users' as TKey, render: () => <UsersTab /> },
  { code: 'roles' as const, labelKey: 'usr.tab.roles' as TKey, render: () => <RolesTab /> },
]

export function UsersPage() {
  const { t } = useI18n()
  const tabs = TABS.map((tab) => ({ ...tab, label: t(tab.labelKey) }))
  const [current, select] = useTabParam(tabs)
  const audit = useUsersAudit()
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">{t('usr.title')}</h1>
        <p className="text-sm text-slate-500">
          {t('usr.subtitle')}
        </p>
      </header>
      <Tabs label={t('usr.title')} idPrefix="users" tabs={tabs} current={current} onSelect={select} />
      <div role="tabpanel" id={`users-panel-${current.code}`} aria-labelledby={`users-tab-${current.code}`} className="space-y-4">
        {current.render()}
        <AuditLog query={audit} />
      </div>
    </div>
  )
}

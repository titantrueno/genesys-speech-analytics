import { lazy, Suspense, type ReactNode } from 'react'
import { useAuth } from '../auth/useAuth'
import { Tabs } from '../components/Tabs'
import type { TKey } from '../i18n/dictionaries'
import { useI18n } from '../i18n/useI18n'
import { useTabParam } from '../components/useTabParam'
import { useAudit, useConfig } from './api'
import { AuditLog } from './AuditLog'
import { SpecLoading } from './openapi/SpecLoading'
import { AiTab } from './tabs/AiTab'
import { ComplianceTab } from './tabs/ComplianceTab'
import { GeneralTab } from './tabs/GeneralTab'
import { KpisTab } from './tabs/KpisTab'
import { PrivacyTab } from './tabs/PrivacyTab'
import { SourcesTab } from './tabs/SourcesTab'
import { TaxonomyTab } from './tabs/TaxonomyTab'
import type { ConfigTabCode, PlatformConfig } from './types'

// Swagger UI pesa: su chunk solo se descarga al abrir la pestaña «API» (FE010).
const ApiTab = lazy(async () => ({ default: (await import('./tabs/ApiTab')).ApiTab }))

type TabProps = { config: PlatformConfig; canEdit: boolean }

const TABS: Array<{ code: ConfigTabCode; labelKey: TKey; render: (props: TabProps) => ReactNode }> = [
  { code: 'general', labelKey: 'cfg.tab.general', render: (p) => <GeneralTab {...p} /> },
  { code: 'fuentes', labelKey: 'cfg.tab.fuentes', render: (p) => <SourcesTab {...p} /> },
  { code: 'taxonomia', labelKey: 'cfg.tab.taxonomia', render: (p) => <TaxonomyTab canEdit={p.canEdit} /> },
  { code: 'kpis', labelKey: 'cfg.tab.kpis', render: (p) => <KpisTab {...p} /> },
  { code: 'cumplimiento', labelKey: 'cfg.tab.cumplimiento', render: (p) => <ComplianceTab canEdit={p.canEdit} /> },
  { code: 'privacidad', labelKey: 'cfg.tab.privacidad', render: (p) => <PrivacyTab {...p} /> },
  { code: 'modelos', labelKey: 'cfg.tab.modelos', render: (p) => <AiTab {...p} /> },
  {
    code: 'api', labelKey: 'cfg.tab.api',
    render: () => <Suspense fallback={<SpecLoading />}><ApiTab /></Suspense>,
  },
]

export function ConfigPage() {
  const { t } = useI18n()
  const { can } = useAuth()
  const canEdit = can('config:edit')
  const { data, isError, isPending } = useConfig()
  const tabs = TABS.map((tab) => ({ ...tab, label: t(tab.labelKey) }))
  const [current, select] = useTabParam(tabs)
  // La pestaña «API» no es una sección de la configuración: no tiene registro de cambios.
  const section = current.code === 'api' ? null : current.code
  const audit = useAudit(section, Boolean(data))

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">{t('cfg.title')}</h1>
        <p className="text-sm text-slate-500">
          {t('cfg.subtitle')}
          {!canEdit && ` ${t('cfg.readOnly')}`}
        </p>
      </header>
      {isPending && <p role="status" className="text-sm text-slate-500">{t('cfg.loading')}</p>}
      {isError && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{t('cfg.loadError')}</p>}
      {data && (
        <>
          <Tabs label={t('cfg.sections')} idPrefix="config" tabs={tabs} current={current} onSelect={select} />
          <div role="tabpanel" id={`config-panel-${current.code}`} aria-labelledby={`config-tab-${current.code}`}
            className="space-y-4">
            {current.render({ config: data, canEdit })}
            {section && <AuditLog query={audit} />}
          </div>
        </>
      )}
    </div>
  )
}

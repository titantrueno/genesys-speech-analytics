import { lazy, Suspense, type ReactNode } from 'react'
import { useAuth } from '../auth/useAuth'
import { Tabs } from '../components/Tabs'
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

const TABS: Array<{ code: ConfigTabCode; label: string; render: (props: TabProps) => ReactNode }> = [
  { code: 'general', label: 'General', render: (p) => <GeneralTab {...p} /> },
  { code: 'fuentes', label: 'Fuentes de datos', render: (p) => <SourcesTab canEdit={p.canEdit} /> },
  { code: 'taxonomia', label: 'Taxonomía', render: (p) => <TaxonomyTab canEdit={p.canEdit} /> },
  { code: 'kpis', label: 'KPIs y objetivos', render: (p) => <KpisTab {...p} /> },
  { code: 'cumplimiento', label: 'Cumplimiento', render: (p) => <ComplianceTab canEdit={p.canEdit} /> },
  { code: 'privacidad', label: 'Privacidad', render: (p) => <PrivacyTab {...p} /> },
  { code: 'modelos', label: 'Modelos de IA', render: (p) => <AiTab {...p} /> },
  {
    code: 'api', label: 'API',
    render: () => <Suspense fallback={<SpecLoading />}><ApiTab /></Suspense>,
  },
]

export function ConfigPage() {
  const { can } = useAuth()
  const canEdit = can('config:edit')
  const { data, isError, isPending } = useConfig()
  const [current, select] = useTabParam(TABS)
  // La pestaña «API» no es una sección de la configuración: no tiene registro de cambios.
  const section = current.code === 'api' ? null : current.code
  const audit = useAudit(section, Boolean(data))

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Configuración</h1>
        <p className="text-sm text-slate-500">
          Configuración global de la plataforma; los cambios se aplican al resto de secciones.
          {!canEdit && ' Tienes acceso de solo lectura.'}
        </p>
      </header>
      {isPending && <p role="status" className="text-sm text-slate-500">Cargando configuración…</p>}
      {isError && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">No se ha podido cargar la configuración.</p>}
      {data && (
        <>
          <Tabs label="Secciones de la configuración" idPrefix="config" tabs={TABS} current={current} onSelect={select} />
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

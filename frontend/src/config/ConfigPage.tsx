import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'
import { useAuth } from '../auth/useAuth'
import { useConfig } from './api'
import { AuditLog } from './AuditLog'
import { AiTab } from './tabs/AiTab'
import { GeneralTab } from './tabs/GeneralTab'
import { PrivacyTab } from './tabs/PrivacyTab'
import { SourcesTab } from './tabs/SourcesTab'
import type { PlatformConfig, SectionCode } from './types'

type TabProps = { config: PlatformConfig; canEdit: boolean }

const TABS: Array<{ code: SectionCode; label: string; render: (props: TabProps) => ReactNode }> = [
  { code: 'general', label: 'General', render: (p) => <GeneralTab {...p} /> },
  { code: 'fuentes', label: 'Fuentes de datos', render: (p) => <SourcesTab canEdit={p.canEdit} /> },
  { code: 'taxonomia', label: 'Taxonomía', render: () => null },
  { code: 'kpis', label: 'KPIs y objetivos', render: () => null },
  { code: 'cumplimiento', label: 'Cumplimiento', render: () => null },
  { code: 'privacidad', label: 'Privacidad', render: (p) => <PrivacyTab {...p} /> },
  { code: 'modelos', label: 'Modelos de IA', render: (p) => <AiTab {...p} /> },
]

export function ConfigPage() {
  const { can } = useAuth()
  const canEdit = can('config:edit')
  const { data, isError, isPending } = useConfig()
  const [params, setParams] = useSearchParams()
  const current = TABS.find((t) => t.code === params.get('tab')) ?? TABS[0]
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  function select(code: SectionCode) {
    setParams(code === TABS[0].code ? {} : { tab: code }, { replace: true })
  }

  function onKeyDown(event: KeyboardEvent) {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!delta) return
    event.preventDefault()
    const next = TABS[(TABS.indexOf(current) + delta + TABS.length) % TABS.length]
    select(next.code)
    tabRefs.current[next.code]?.focus()
  }

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
          <div role="tablist" aria-label="Secciones de la configuración" onKeyDown={onKeyDown}
            className="flex flex-wrap gap-1 border-b border-slate-200">
            {TABS.map((tab) => {
              const selected = tab === current
              return (
                <button key={tab.code} ref={(el) => { tabRefs.current[tab.code] = el }} id={`config-tab-${tab.code}`}
                  type="button" role="tab" aria-selected={selected} aria-controls={`config-panel-${tab.code}`}
                  tabIndex={selected ? 0 : -1} onClick={() => select(tab.code)}
                  className={`-mb-px rounded-t-md border px-3 py-1.5 text-sm ${selected ? 'border-slate-200 border-b-white bg-white font-medium text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
                  {tab.label}
                </button>
              )
            })}
          </div>
          <div role="tabpanel" id={`config-panel-${current.code}`} aria-labelledby={`config-tab-${current.code}`}
            className="space-y-4">
            {current.render({ config: data, canEdit })}
            <AuditLog section={current.code} />
          </div>
        </>
      )}
    </div>
  )
}

import { useState } from 'react'
import { configRequests, fieldErrors, useConfigMutation } from '../api'
import { Card, ConfigField, input } from '../controls'
import type { KpiConfig, PlatformConfig } from '../types'

type Draft = { target: string; green: string; amber: string; dashboards: string[] }

const toText = (value: number | null) => (value === null ? '' : String(value))
const toNumber = (text: string) => (text.trim() === '' ? null : Number(text.replace(',', '.')))

function KpiEditor({ kpi, dashboards, canEdit }: { kpi: KpiConfig; dashboards: PlatformConfig['options']['dashboards']; canEdit: boolean }) {
  const initial: Draft = { target: toText(kpi.target), green: toText(kpi.green), amber: toText(kpi.amber), dashboards: kpi.dashboards }
  const [draft, setDraft] = useState(initial)
  const save = useConfigMutation(configRequests.kpi)
  const errors = fieldErrors(save.error)
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial)
  const direction = kpi.higher_is_better
    ? 'Más es mejor: verde si el valor es mayor o igual que el umbral verde.'
    : 'Más es peor: verde si el valor es menor o igual que el umbral verde.'
  const toggle = (slug: string) => setDraft((d) => ({
    ...d,
    dashboards: d.dashboards.includes(slug)
      ? d.dashboards.filter((s) => s !== slug)
      : dashboards.map((o) => o.value).filter((s) => s === slug || d.dashboards.includes(s)),
  }))
  return (
    <fieldset disabled={!canEdit} className="space-y-3 rounded-lg border border-slate-200 p-4">
      <legend className="px-1 text-sm font-semibold text-slate-800">{kpi.label}</legend>
      <p className="text-xs text-slate-500">{direction} Unidad: {kpi.unit}.</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {(['target', 'green', 'amber'] as const).map((field) => (
          <ConfigField key={field} label={{ target: 'Objetivo', green: 'Umbral verde', amber: 'Umbral ámbar' }[field]} error={errors[field]}>
            <input className={input} inputMode="decimal" value={draft[field]}
              onChange={(e) => setDraft({ ...draft, [field]: e.target.value })} />
          </ConfigField>
        ))}
      </div>
      <div className="flex flex-wrap gap-4 text-sm text-slate-700">
        <span className="text-xs font-medium text-slate-600">Se muestra en:</span>
        {dashboards.map((d) => (
          <label key={d.value} className="inline-flex items-center gap-1.5">
            <input type="checkbox" checked={draft.dashboards.includes(d.value)} onChange={() => toggle(d.value)} />
            {d.label}
          </label>
        ))}
      </div>
      {errors.dashboards && <p className="text-xs text-red-700">{errors.dashboards}</p>}
      {canEdit && (
        <div className="flex items-center gap-3">
          <button type="button" disabled={!dirty || save.isPending}
            onClick={() => save.mutate({ code: kpi.code, target: toNumber(draft.target), green: toNumber(draft.green),
              amber: toNumber(draft.amber), dashboards: draft.dashboards })}
            className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50">
            Guardar
          </button>
          {save.isSuccess && !dirty && <p role="status" className="text-sm text-emerald-700">Cambios guardados.</p>}
        </div>
      )}
    </fieldset>
  )
}

export function KpisTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  return (
    <Card title="KPIs y objetivos"
      description="Objetivo y umbrales de cada KPI (las tarjetas se colorean en verde, ámbar o rojo) y dashboards donde se muestra. Sin umbrales, la tarjeta no se colorea.">
      <div className="space-y-3">
        {config.kpis.map((kpi) => (
          <KpiEditor key={kpi.code} kpi={kpi} dashboards={config.options.dashboards} canEdit={canEdit} />
        ))}
      </div>
    </Card>
  )
}

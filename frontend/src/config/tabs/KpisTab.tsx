import { useState } from 'react'
import { useI18n } from '../../i18n/useI18n'
import { configRequests, fieldErrors, useConfigMutation } from '../api'
import { Card, ConfigField, input } from '../controls'
import type { KpiConfig, PlatformConfig } from '../types'

type Draft = { target: string; green: string; amber: string; dashboards: string[] }

const toText = (value: number | null) => (value === null ? '' : String(value))
const toNumber = (text: string) => (text.trim() === '' ? null : Number(text.replace(',', '.')))

function KpiEditor({ kpi, dashboards, canEdit }: { kpi: KpiConfig; dashboards: PlatformConfig['options']['dashboards']; canEdit: boolean }) {
  const { t, tOr } = useI18n()
  const initial: Draft = { target: toText(kpi.target), green: toText(kpi.green), amber: toText(kpi.amber), dashboards: kpi.dashboards }
  const [draft, setDraft] = useState(initial)
  const save = useConfigMutation(configRequests.kpi)
  const errors = fieldErrors(save.error)
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial)
  const direction = t(kpi.higher_is_better ? 'cfg.kpis.higher' : 'cfg.kpis.lower')
  const toggle = (slug: string) => setDraft((d) => ({
    ...d,
    dashboards: d.dashboards.includes(slug)
      ? d.dashboards.filter((s) => s !== slug)
      : dashboards.map((o) => o.value).filter((s) => s === slug || d.dashboards.includes(s)),
  }))
  return (
    <fieldset disabled={!canEdit} className="space-y-3 rounded-lg border border-slate-200 p-4">
      <legend className="px-1 text-sm font-semibold text-slate-800">{tOr(`kpi.${kpi.code}.label`, kpi.label)}</legend>
      <p className="text-xs text-slate-500">{t('cfg.kpis.unitLine', { direction, unit: tOr(`cfg.unit.${kpi.unit}`, kpi.unit) })}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {(['target', 'green', 'amber'] as const).map((field) => (
          <ConfigField key={field} label={t({ target: 'cfg.kpis.target', green: 'cfg.kpis.green', amber: 'cfg.kpis.amber' }[field] as 'cfg.kpis.target')} error={errors[field]}>
            <input className={input} inputMode="decimal" value={draft[field]}
              onChange={(e) => setDraft({ ...draft, [field]: e.target.value })} />
          </ConfigField>
        ))}
      </div>
      <div className="flex flex-wrap gap-4 text-sm text-slate-700">
        <span className="text-xs font-medium text-slate-600">{t('cfg.kpis.shownIn')}</span>
        {dashboards.map((d) => (
          <label key={d.value} className="inline-flex items-center gap-1.5">
            <input type="checkbox" checked={draft.dashboards.includes(d.value)} onChange={() => toggle(d.value)} />
            {tOr(`cfg.dashboard.${d.value}`, d.label)}
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
            {t('cfg.save')}
          </button>
          {save.isSuccess && !dirty && <p role="status" className="text-sm text-emerald-700">{t('cfg.saved')}</p>}
        </div>
      )}
    </fieldset>
  )
}

export function KpisTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const { t } = useI18n()
  return (
    <Card title={t('cfg.kpis.title')}
      description={t('cfg.kpis.description')}>
      <div className="space-y-3">
        {config.kpis.map((kpi) => (
          <KpiEditor key={kpi.code} kpi={kpi} dashboards={config.options.dashboards} canEdit={canEdit} />
        ))}
      </div>
    </Card>
  )
}

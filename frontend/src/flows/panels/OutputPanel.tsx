import { Plus, X } from 'lucide-react'
import type { TKey } from '../../i18n/dictionaries'
import { useI18n } from '../../i18n/useI18n'
import { catalogLabel, useCatalog } from '../catalog'
import type { FieldMapping, FieldType, OutputConfig, OutputKind, PromptConfig, TargetField, TargetGroup, TargetOption } from '../types'
import { control, Field, Section, Select } from './controls'

const small = 'inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50'
const GROUPS: Record<TargetGroup, TKey> = {
  analisis: 'flows.output.group.analisis', cumplimiento: 'flows.output.group.cumplimiento', entidades: 'flows.output.group.entidades',
}

/** Tipo de campo del JSON que alimenta cada destino (FE014); los valores permitidos los comprueba la validación. */
function sourceType(target: TargetField): FieldType {
  if (target === 'csat' || target === 'effort' || target === 'sentiment') return 'numero'
  if (target === 'secondary_topics' || target === 'keywords') return 'lista'
  return 'texto'
}

/** Configuración al cambiar de tipo: cada tipo conserva solo sus campos. */
function withKind(kind: OutputKind, config: OutputConfig, firstTarget: TargetField): OutputConfig {
  if (kind === 'campo') return { kind, overwrite: config.overwrite ?? false, mappings: config.mappings?.length ? config.mappings : [{ target: firstTarget }] }
  return { kind, destination: config.destination ?? '', ...(kind === 'metrica' ? { aggregation: config.aggregation ?? 'recuento' } : {}) }
}

/** Asignaciones de un Output «campo» (FE013): campo destino y, con un Prompt JSON, el campo de texto del que sale. */
function FieldMappings({ config, prompt, onChange }: { config: OutputConfig; prompt?: PromptConfig; onChange: (config: OutputConfig) => void }) {
  const catalog = useCatalog()
  const i18n = useI18n()
  const { t } = i18n
  const mappings = config.mappings ?? []
  const json = prompt?.output?.type === 'json'
  const sources = (target: TargetField) => (prompt?.output?.fields ?? []).filter((f) => f.type === sourceType(target) && f.name.trim())
  const free = catalog.target_fields.filter((t) => !mappings.some((m) => m.target === t.value))
  const groups = (Object.keys(GROUPS) as TargetGroup[])
    .map((group) => [group, catalog.target_fields.filter((t) => t.group === group)] as [TargetGroup, TargetOption[]])
    .filter(([, options]) => options.length > 0)
  const set = (next: FieldMapping[]) => onChange({ ...config, mappings: next })
  return (
    <div role="group" aria-label={t('flows.output.targets')} className="space-y-1.5">
      <p className="text-xs font-medium text-slate-600">{t('flows.output.targets')}</p>
      {mappings.map((mapping, i) => (
        <div key={i} className="flex items-center gap-1">
          <select aria-label={t('flows.output.target', { n: i + 1 })} className={control} value={mapping.target}
            onChange={(e) => set(mappings.map((m, j) => (j === i ? { ...m, target: e.target.value as TargetField } : m)))}>
            {groups.map(([group, options]) => (
              <optgroup key={group} label={t(GROUPS[group])}>
                {options.map((opt) => (
                  <option key={opt.value} value={opt.value} disabled={opt.value !== mapping.target && mappings.some((m) => m.target === opt.value)}>{catalogLabel(i18n, 'target_fields', opt)}</option>
                ))}
              </optgroup>
            ))}
          </select>
          {json && (
            <select aria-label={t('flows.output.jsonField', { n: i + 1 })} className={`${control} font-mono`} value={mapping.source ?? ''}
              onChange={(e) => set(mappings.map((m, j) => (j === i ? { ...m, source: e.target.value || undefined } : m)))}>
              <option value="" disabled>{t('flows.output.jsonFieldPlaceholder')}</option>
              {sources(mapping.target).map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
            </select>
          )}
          {mappings.length > 1 && (
            <button type="button" aria-label={t('flows.output.removeTarget', { n: i + 1 })} onClick={() => set(mappings.filter((_, j) => j !== i))}
              className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="size-4" aria-hidden /></button>
          )}
        </div>
      ))}
      {json ? (
        <button type="button" className={small} disabled={free.length === 0} onClick={() => set([...mappings, { target: free[0].value }])}>
          <Plus className="size-3.5" aria-hidden />{t('flows.output.addTarget')}
        </button>
      ) : (
        <p className="text-xs text-slate-500">
          {t('flows.output.wholeAnswer')}
        </p>
      )}
      <label className="flex items-center gap-2 pt-1 text-sm text-slate-700">
        <input type="checkbox" checked={config.overwrite ?? false} onChange={(e) => onChange({ ...config, overwrite: e.target.checked })} />
        {t('flows.output.overwrite')}
      </label>
      <p className="text-xs text-slate-500">{t('flows.output.overwriteHint')}</p>
    </div>
  )
}

export function OutputPanel({ config, prompt, onChange }: {
  config: OutputConfig; prompt?: PromptConfig; onChange: (config: OutputConfig) => void
}) {
  const catalog = useCatalog()
  const i18n = useI18n()
  const { t } = i18n
  const realData = catalog.origin === 'real'
  return (
    <Section title={t('flows.output.result')}>
      <Field label={t('flows.output.kind')} hint={realData ? undefined : t('flows.output.realOnly')}>
        <select className={control} value={config.kind ?? ''}
          onChange={(e) => onChange(withKind(e.target.value as OutputKind, config, catalog.target_fields[0].value))}>
          {config.kind === undefined && <option value="" disabled>{t('flows.chooseOption')}</option>}
          {catalog.output_kinds.map((o) => (
            <option key={o.value} value={o.value} disabled={o.value === 'campo' && !realData && config.kind !== 'campo'}>{catalogLabel(i18n, 'output_kinds', o)}</option>
          ))}
        </select>
      </Field>
      {config.kind === 'metrica' && (
        <>
          <Select label={t('flows.output.aggregation')} group="aggregations" value={config.aggregation} options={catalog.aggregations}
            onChange={(aggregation) => onChange({ ...config, aggregation })} />
          <p className="text-xs text-slate-500">{t('flows.output.metricHint')}</p>
        </>
      )}
      {config.kind === 'campo' ? <FieldMappings config={config} prompt={prompt} onChange={onChange} /> : (
        <Field label={t('flows.output.destination')} hint={t('flows.output.destinationHint')}>
          <input className={control} value={config.destination ?? ''} maxLength={catalog.limits.max_destination}
            placeholder={t('flows.output.destinationPlaceholder')} onChange={(e) => onChange({ ...config, destination: e.target.value })} />
        </Field>
      )}
    </Section>
  )
}

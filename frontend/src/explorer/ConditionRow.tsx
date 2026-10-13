import { X } from 'lucide-react'
import { useState } from 'react'
import { MultiSelect } from '../components/MultiSelect'
import { useI18n } from '../i18n/useI18n'
import { useSuggestions } from './api'
import { fieldLabel, operatorLabel, valueLabel } from './labels'
import { changeOperator, isComplete, isEmptyOperator, newCondition, type Condition, type FieldSchema, type QuerySchema, type Speaker } from './queryModel'

const control = 'h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700'

function NumberInput({ label, value, min, max, onChange }: {
  label: string; value: unknown; min?: number; max?: number; onChange: (value: number | null) => void
}) {
  const external = typeof value === 'number' ? String(value) : ''
  const [draft, setDraft] = useState(external)
  const [previous, setPrevious] = useState(value)
  if (value !== previous) {
    setPrevious(value)
    if (Number(draft) !== value) setDraft(external)
  }
  return (
    <input type="number" step="any" aria-label={label} className={`${control} w-28`} value={draft} min={min} max={max}
      onChange={(e) => {
        setDraft(e.target.value)
        const parsed = e.target.value === '' ? NaN : Number(e.target.value)
        onChange(Number.isFinite(parsed) ? parsed : null)
      }} />
  )
}

function CategoricalValue({ cond, field, from, to, onChange }: {
  cond: Condition; field: FieldSchema; from?: string; to?: string; onChange: (value: string | string[]) => void
}) {
  const i18n = useI18n()
  const { t } = i18n
  const { data } = useSuggestions(field.key, from, to, true)
  const counts = new Map(data?.values.map((s) => [s.value, s.count]))
  const options = (field.values ?? [])
    .map((v) => ({ value: v.value, label: `${valueLabel(i18n, field.key, v)} (${counts.get(v.value) ?? 0})`, count: counts.get(v.value) ?? 0 }))
    .sort((a, b) => b.count - a.count)
  if (cond.operator === 'in' || cond.operator === 'not_in') {
    return (
      <MultiSelect label={t('exp.cond.values')} allLabel={t('exp.cond.none')} options={options}
        selected={Array.isArray(cond.value) ? (cond.value as string[]) : []} onChange={onChange} />
    )
  }
  return (
    <select aria-label={t('exp.cond.value')} className={`${control} max-w-64`} value={String(cond.value ?? '')} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

interface Props {
  label: string
  cond: Condition
  schema: QuerySchema
  from?: string
  to?: string
  error?: string
  onChange: (cond: Condition) => void
  onRemove: () => void
}

export function ConditionRow({ label, cond, schema, from, to, error, onChange, onRemove }: Props) {
  const i18n = useI18n()
  const { t } = i18n
  const field = schema.fields.find((f) => f.key === cond.field)
  const setValue = (value: Condition['value']) => onChange({ ...cond, value })
  const hasValue = !isEmptyOperator(cond.operator)

  return (
    <div role="group" aria-label={t('exp.cond.group', { label })} className="rounded-lg border border-slate-200 bg-white p-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label={t('exp.cond.field')} className={`${control} w-56`} value={cond.field}
          onChange={(e) => {
            const next = schema.fields.find((f) => f.key === e.target.value)
            if (next) onChange(newCondition(next))
          }}>
          {schema.fields.map((f) => <option key={f.key} value={f.key}>{fieldLabel(i18n, f)}</option>)}
        </select>
        {field?.speakers && (
          <select aria-label={t('exp.cond.speaker')} className={control} value={cond.speaker ?? ''}
            onChange={(e) => onChange({ ...cond, speaker: (e.target.value || undefined) as Speaker | undefined })}>
            <option value="">{t('exp.cond.anySpeaker')}</option>
            {field.speakers.map((s) => <option key={s} value={s}>{t(`exp.speaker.${s}`)}</option>)}
          </select>
        )}
        <select aria-label={t('exp.cond.operator')} className={control} value={cond.operator}
          onChange={(e) => field && onChange(changeOperator(cond, e.target.value, field))}>
          {field?.operators.map((o) => <option key={o.key} value={o.key}>{operatorLabel(i18n, o)}</option>)}
        </select>
        {hasValue && field?.type === 'categorical' && <CategoricalValue cond={cond} field={field} from={from} to={to} onChange={setValue} />}
        {hasValue && field?.type === 'numeric' && cond.operator === 'between' && (
          <>
            <NumberInput label={t('exp.cond.min')} value={(cond.value as number[] | undefined)?.[0]} min={field.min} max={field.max}
              onChange={(v) => setValue([v as number, (cond.value as number[] | undefined)?.[1] as number])} />
            <span className="text-sm text-slate-500">{t('exp.cond.between')}</span>
            <NumberInput label={t('exp.cond.max')} value={(cond.value as number[] | undefined)?.[1]} min={field.min} max={field.max}
              onChange={(v) => setValue([(cond.value as number[] | undefined)?.[0] as number, v as number])} />
          </>
        )}
        {hasValue && field?.type === 'numeric' && cond.operator !== 'between' && (
          <NumberInput label={t('exp.cond.value')} value={cond.value} min={field.min} max={field.max} onChange={setValue} />
        )}
        {hasValue && field?.type === 'text' && (
          <input type="text" aria-label={t('exp.cond.value')} className={`${control} min-w-56 flex-1`} value={String(cond.value ?? '')}
            placeholder={t('exp.cond.textPlaceholder')} onChange={(e) => setValue(e.target.value)} />
        )}
        {hasValue && field?.type === 'boolean' && (
          <select aria-label={t('exp.cond.value')} className={control} value={String(cond.value ?? true)} onChange={(e) => setValue(e.target.value === 'true')}>
            <option value="true">{t('domain.yes')}</option>
            <option value="false">{t('domain.no')}</option>
          </select>
        )}
        <button type="button" onClick={onRemove} aria-label={t('exp.cond.remove')}
          className="ml-auto rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
          <X className="size-4" aria-hidden />
        </button>
      </div>
      {!isComplete(cond, field) && (
        <p className="mt-1.5 text-xs text-amber-700">{field?.type === 'text' ? t('exp.cond.needText') : t('exp.cond.needValue')}</p>
      )}
      {error && <p role="alert" className="mt-1.5 text-xs text-red-700">{error}</p>}
    </div>
  )
}

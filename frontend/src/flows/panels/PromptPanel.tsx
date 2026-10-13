import { Plus, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { useI18n } from '../../i18n/useI18n'
import { catalogLabel, useCatalog } from '../catalog'
import type { FieldType, OutputFormat, PromptConfig } from '../types'
import { control, Field, Section, Select } from './controls'

const PREVIOUS_RESULT = 'resultado_anterior'
const small = 'inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50'

function LabelsEditor({ labels, onChange }: { labels: string[]; onChange: (labels: string[]) => void }) {
  const { limits } = useCatalog()
  const { t } = useI18n()
  return (
    <div role="group" aria-label={t('flows.prompt.labels')} className="space-y-1.5">
      <p className="text-xs font-medium text-slate-600">{t('flows.prompt.labelsRange', { max: limits.max_labels })}</p>
      {labels.map((label, i) => (
        <div key={i} className="flex items-center gap-1">
          <input aria-label={t('flows.prompt.label', { n: i + 1 })} className={control} value={label} maxLength={limits.max_label}
            onChange={(e) => onChange(labels.map((l, j) => (j === i ? e.target.value : l)))} />
          <button type="button" aria-label={t('flows.prompt.removeLabel', { n: i + 1 })} onClick={() => onChange(labels.filter((_, j) => j !== i))}
            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="size-4" aria-hidden /></button>
        </div>
      ))}
      <button type="button" className={small} disabled={labels.length >= limits.max_labels} onClick={() => onChange([...labels, ''])}>
        <Plus className="size-3.5" aria-hidden />{t('flows.prompt.addLabel')}
      </button>
    </div>
  )
}

/** Valores permitidos de un campo de texto (FE013) o de cada elemento de una lista (FE014), uno por línea; el LLM los
 *  recibe como `enum`. */
function AllowedValues({ index, options, onChange }: { index: number; options: string[]; onChange: (options: string[]) => void }) {
  const { t } = useI18n()
  const [text, setText] = useState(options.join('\n'))
  return (
    <textarea aria-label={t('flows.prompt.allowedValues', { n: index })} className={`${control} h-20 py-1 text-xs`} value={text}
      placeholder={t('flows.prompt.onePerLine')} onChange={(e) => {
        setText(e.target.value)
        onChange(e.target.value.split('\n').map((v) => v.trim()).filter(Boolean))
      }} />
  )
}

function SchemaEditor({ fields, onChange }: { fields: NonNullable<OutputFormat['fields']>; onChange: (fields: NonNullable<OutputFormat['fields']>) => void }) {
  const { limits, field_types: types } = useCatalog()
  const i18n = useI18n()
  const { t } = i18n
  return (
    <div role="group" aria-label={t('flows.prompt.schema')} className="space-y-1.5">
      <p className="text-xs font-medium text-slate-600">{t('flows.prompt.fieldsRange', { max: limits.max_fields })}</p>
      {fields.map((field, i) => (
        <div key={i} className="space-y-1">
          <div className="flex items-center gap-1">
            <input aria-label={t('flows.prompt.fieldName', { n: i + 1 })} className={`${control} font-mono`} value={field.name} maxLength={limits.max_field_name}
              placeholder={t('flows.prompt.fieldNamePlaceholder')} onChange={(e) => onChange(fields.map((f, j) => (j === i ? { ...f, name: e.target.value } : f)))} />
            <select aria-label={t('flows.prompt.fieldType', { n: i + 1 })} className={`${control} w-32`} value={field.type}
              onChange={(e) => onChange(fields.map((f, j) => (j === i ? { name: f.name, type: e.target.value as FieldType } : f)))}>
              {types.map((type) => <option key={type.value} value={type.value}>{catalogLabel(i18n, 'field_types', type)}</option>)}
            </select>
            <button type="button" aria-label={t('flows.prompt.removeField', { n: i + 1 })} onClick={() => onChange(fields.filter((_, j) => j !== i))}
              className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="size-4" aria-hidden /></button>
          </div>
          {(field.type === 'texto' || field.type === 'lista') && (
            <label className="flex items-center gap-1.5 text-xs text-slate-600">
              <input type="checkbox" aria-label={t('flows.prompt.limitField', { n: i + 1 })} checked={field.options !== undefined}
                onChange={(e) => onChange(fields.map((f, j) => (j === i ? (e.target.checked ? { ...f, options: [] } : { name: f.name, type: f.type }) : f)))} />
              {t('flows.prompt.limit')}
            </label>
          )}
          {(field.type === 'texto' || field.type === 'lista') && field.options !== undefined && (
            <AllowedValues index={i + 1} options={field.options}
              onChange={(options) => onChange(fields.map((f, j) => (j === i ? { ...f, options } : f)))} />
          )}
        </div>
      ))}
      <button type="button" className={small} disabled={fields.length >= limits.max_fields}
        onClick={() => onChange([...fields, { name: '', type: 'texto' }])}>
        <Plus className="size-3.5" aria-hidden />{t('flows.prompt.addField')}
      </button>
    </div>
  )
}

function withFormat(type: OutputFormat['type'], current: OutputFormat | undefined): OutputFormat {
  if (type === 'etiqueta') return { type, labels: current?.labels ?? ['', ''] }
  if (type === 'json') return { type, fields: current?.fields ?? [{ name: '', type: 'texto' }] }
  return { type }
}

export function PromptPanel({ config, chained, onChange }: {
  config: PromptConfig; chained: boolean; onChange: (config: PromptConfig) => void
}) {
  const catalog = useCatalog()
  const i18n = useI18n()
  const { t } = i18n
  const templateRef = useRef<HTMLTextAreaElement>(null)
  const template = config.template ?? ''
  // Un nodo sin proveedor es simulado: así se leen los flujos guardados antes de FE013.
  const providerValue = config.provider ?? 'simulado'
  const provider = catalog.providers.find((p) => p.value === providerValue)
  const withTemperature = provider?.models.find((m) => m.value === config.model)?.temperature ?? true

  function insertVariable(name: string) {
    const textarea = templateRef.current
    const token = `{{${name}}}`
    const start = textarea?.selectionStart ?? template.length
    const end = textarea?.selectionEnd ?? template.length
    onChange({ ...config, template: template.slice(0, start) + token + template.slice(end) })
    requestAnimationFrame(() => {
      textarea?.focus()
      textarea?.setSelectionRange(start + token.length, start + token.length)
    })
  }

  return (
    <div className="space-y-3">
      <Section title={t('flows.prompt.template')}>
        <Field label={t('flows.prompt.text')} hint={t('flows.prompt.chars', { n: template.length, max: catalog.limits.max_template })}>
          <textarea ref={templateRef} className={`${control} h-36 py-1.5 font-mono text-xs`} value={template}
            maxLength={catalog.limits.max_template} placeholder={t('flows.prompt.placeholder')}
            onChange={(e) => onChange({ ...config, template: e.target.value })} />
        </Field>
        <div role="group" aria-label={t('flows.prompt.insertVariable')} className="flex flex-wrap gap-1">
          {catalog.variables.map((v) => {
            const unavailable = v.value === PREVIOUS_RESULT && !chained
            return (
              <button key={v.value} type="button" className={`${small} font-mono`} disabled={unavailable}
                title={unavailable ? t('flows.prompt.chainedOnly') : catalogLabel(i18n, 'variables', v)} onClick={() => insertVariable(v.value)}>
                {`{{${v.value}}}`}
              </button>
            )
          })}
        </div>
      </Section>
      <Section title={t('flows.prompt.modelAndTemperature')}>
        <Select label={t('flows.prompt.provider')} group="providers" value={providerValue} options={catalog.providers}
          onChange={(value) => onChange({ ...config, provider: value, model: catalog.providers.find((p) => p.value === value)?.models[0]?.value })} />
        <Select label={t('flows.prompt.model')} group="models" value={config.model} options={provider?.models ?? []} onChange={(model) => onChange({ ...config, model })} />
        <Field label={t('flows.prompt.temperature', { value: (config.temperature ?? 0).toFixed(1) })}
          hint={withTemperature ? t('flows.prompt.temperatureHint') : t('flows.prompt.noTemperature')}>
          <input type="range" className="w-full accent-brand-600 disabled:opacity-50" min={0} max={1} step={0.1} value={config.temperature ?? 0}
            disabled={!withTemperature} onChange={(e) => onChange({ ...config, temperature: Number(e.target.value) })} />
        </Field>
      </Section>
      <Section title={t('flows.prompt.outputFormat')}>
        <Select label={t('flows.prompt.format')} group="output_formats" value={config.output?.type} options={catalog.output_formats}
          onChange={(type) => onChange({ ...config, output: withFormat(type, config.output) })} />
        {config.output?.type === 'etiqueta' && (
          <LabelsEditor labels={config.output.labels ?? []} onChange={(labels) => onChange({ ...config, output: { type: 'etiqueta', labels } })} />
        )}
        {config.output?.type === 'json' && (
          <SchemaEditor fields={config.output.fields ?? []} onChange={(fields) => onChange({ ...config, output: { type: 'json', fields } })} />
        )}
      </Section>
    </div>
  )
}

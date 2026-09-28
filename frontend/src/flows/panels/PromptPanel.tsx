import { Plus, X } from 'lucide-react'
import { useRef } from 'react'
import { useCatalog } from '../catalog'
import type { FieldType, OutputFormat, PromptConfig } from '../types'
import { control, Field, Section, Select } from './controls'

const PREVIOUS_RESULT = 'resultado_anterior'
const small = 'inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50'

function LabelsEditor({ labels, onChange }: { labels: string[]; onChange: (labels: string[]) => void }) {
  const { limits } = useCatalog()
  return (
    <div role="group" aria-label="Etiquetas" className="space-y-1.5">
      <p className="text-xs font-medium text-slate-600">Etiquetas (de 2 a {limits.max_labels})</p>
      {labels.map((label, i) => (
        <div key={i} className="flex items-center gap-1">
          <input aria-label={`Etiqueta ${i + 1}`} className={control} value={label} maxLength={limits.max_label}
            onChange={(e) => onChange(labels.map((l, j) => (j === i ? e.target.value : l)))} />
          <button type="button" aria-label={`Quitar etiqueta ${i + 1}`} onClick={() => onChange(labels.filter((_, j) => j !== i))}
            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="size-4" aria-hidden /></button>
        </div>
      ))}
      <button type="button" className={small} disabled={labels.length >= limits.max_labels} onClick={() => onChange([...labels, ''])}>
        <Plus className="size-3.5" aria-hidden />Añadir etiqueta
      </button>
    </div>
  )
}

function SchemaEditor({ fields, onChange }: { fields: NonNullable<OutputFormat['fields']>; onChange: (fields: NonNullable<OutputFormat['fields']>) => void }) {
  const { limits, field_types: types } = useCatalog()
  return (
    <div role="group" aria-label="Esquema JSON" className="space-y-1.5">
      <p className="text-xs font-medium text-slate-600">Campos del JSON (de 1 a {limits.max_fields})</p>
      {fields.map((field, i) => (
        <div key={i} className="flex items-center gap-1">
          <input aria-label={`Nombre del campo ${i + 1}`} className={`${control} font-mono`} value={field.name} maxLength={limits.max_field_name}
            placeholder="nombre_del_campo" onChange={(e) => onChange(fields.map((f, j) => (j === i ? { ...f, name: e.target.value } : f)))} />
          <select aria-label={`Tipo del campo ${i + 1}`} className={`${control} w-32`} value={field.type}
            onChange={(e) => onChange(fields.map((f, j) => (j === i ? { ...f, type: e.target.value as FieldType } : f)))}>
            {types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <button type="button" aria-label={`Quitar campo ${i + 1}`} onClick={() => onChange(fields.filter((_, j) => j !== i))}
            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="size-4" aria-hidden /></button>
        </div>
      ))}
      <button type="button" className={small} disabled={fields.length >= limits.max_fields}
        onClick={() => onChange([...fields, { name: '', type: 'texto' }])}>
        <Plus className="size-3.5" aria-hidden />Añadir campo
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
  const templateRef = useRef<HTMLTextAreaElement>(null)
  const template = config.template ?? ''

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
      <Section title="Plantilla">
        <Field label="Texto del prompt" hint={`${template.length} de ${catalog.limits.max_template} caracteres.`}>
          <textarea ref={templateRef} className={`${control} h-36 py-1.5 font-mono text-xs`} value={template}
            maxLength={catalog.limits.max_template} placeholder="Clasifica el motivo de la queja: {{summary}}"
            onChange={(e) => onChange({ ...config, template: e.target.value })} />
        </Field>
        <div role="group" aria-label="Insertar variable" className="flex flex-wrap gap-1">
          {catalog.variables.map((v) => {
            const unavailable = v.value === PREVIOUS_RESULT && !chained
            return (
              <button key={v.value} type="button" className={`${small} font-mono`} disabled={unavailable}
                title={unavailable ? 'Solo en un prompt conectado a otro prompt' : v.label} onClick={() => insertVariable(v.value)}>
                {`{{${v.value}}}`}
              </button>
            )
          })}
        </div>
      </Section>
      <Section title="Modelo y temperatura">
        <Select label="Modelo" value={config.model} options={catalog.models} onChange={(model) => onChange({ ...config, model })} />
        <Field label={`Temperatura: ${(config.temperature ?? 0).toFixed(1)}`} hint="0 = respuestas más estables; 1 = más variadas.">
          <input type="range" className="w-full accent-brand-600" min={0} max={1} step={0.1} value={config.temperature ?? 0}
            onChange={(e) => onChange({ ...config, temperature: Number(e.target.value) })} />
        </Field>
      </Section>
      <Section title="Formato de salida">
        <Select label="Formato" value={config.output?.type} options={catalog.output_formats}
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

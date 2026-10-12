import { Plus, X } from 'lucide-react'
import { useCatalog } from '../catalog'
import type { FieldMapping, OutputConfig, OutputKind, PromptConfig, TargetField } from '../types'
import { control, Field, Section, Select } from './controls'

const small = 'inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50'
const REAL_DATA_ONLY = 'Guardar en campos solo funciona con datos reales: cambia el origen en Configuración › Fuentes de datos.'

/** Configuración al cambiar de tipo: cada tipo conserva solo sus campos. */
function withKind(kind: OutputKind, config: OutputConfig, firstTarget: TargetField): OutputConfig {
  if (kind === 'campo') return { kind, overwrite: config.overwrite ?? false, mappings: config.mappings?.length ? config.mappings : [{ target: firstTarget }] }
  return { kind, destination: config.destination ?? '', ...(kind === 'metrica' ? { aggregation: config.aggregation ?? 'recuento' } : {}) }
}

/** Asignaciones de un Output «campo» (FE013): campo destino y, con un Prompt JSON, el campo de texto del que sale. */
function FieldMappings({ config, prompt, onChange }: { config: OutputConfig; prompt?: PromptConfig; onChange: (config: OutputConfig) => void }) {
  const catalog = useCatalog()
  const mappings = config.mappings ?? []
  const json = prompt?.output?.type === 'json'
  const textFields = (prompt?.output?.fields ?? []).filter((f) => f.type === 'texto' && f.name.trim())
  const free = catalog.target_fields.filter((t) => !mappings.some((m) => m.target === t.value))
  const set = (next: FieldMapping[]) => onChange({ ...config, mappings: next })
  return (
    <div role="group" aria-label="Campos destino" className="space-y-1.5">
      <p className="text-xs font-medium text-slate-600">Campos destino</p>
      {mappings.map((mapping, i) => (
        <div key={i} className="flex items-center gap-1">
          <select aria-label={`Campo destino ${i + 1}`} className={control} value={mapping.target}
            onChange={(e) => set(mappings.map((m, j) => (j === i ? { ...m, target: e.target.value as TargetField } : m)))}>
            {catalog.target_fields.map((t) => (
              <option key={t.value} value={t.value} disabled={t.value !== mapping.target && mappings.some((m) => m.target === t.value)}>{t.label}</option>
            ))}
          </select>
          {json && (
            <select aria-label={`Campo del JSON ${i + 1}`} className={`${control} font-mono`} value={mapping.source ?? ''}
              onChange={(e) => set(mappings.map((m, j) => (j === i ? { ...m, source: e.target.value || undefined } : m)))}>
              <option value="" disabled>Campo del JSON</option>
              {textFields.map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
            </select>
          )}
          {mappings.length > 1 && (
            <button type="button" aria-label={`Quitar campo destino ${i + 1}`} onClick={() => set(mappings.filter((_, j) => j !== i))}
              className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="size-4" aria-hidden /></button>
          )}
        </div>
      ))}
      {json ? (
        <button type="button" className={small} disabled={free.length === 0} onClick={() => set([...mappings, { target: free[0].value }])}>
          <Plus className="size-3.5" aria-hidden />Añadir campo destino
        </button>
      ) : (
        <p className="text-xs text-slate-500">
          Se guarda la respuesta completa del Prompt. Para guardar summary y main topic con una sola llamada al LLM, usa un
          Prompt JSON con los dos campos.
        </p>
      )}
      <label className="flex items-center gap-2 pt-1 text-sm text-slate-700">
        <input type="checkbox" checked={config.overwrite ?? false} onChange={(e) => onChange({ ...config, overwrite: e.target.checked })} />
        Sobrescribir valores existentes
      </label>
      <p className="text-xs text-slate-500">Sin marcar, solo se rellenan las conversaciones que aún no tienen ese campo.</p>
    </div>
  )
}

export function OutputPanel({ config, prompt, onChange }: {
  config: OutputConfig; prompt?: PromptConfig; onChange: (config: OutputConfig) => void
}) {
  const catalog = useCatalog()
  const realData = catalog.origin === 'real'
  return (
    <Section title="Resultado">
      <Field label="Tipo de output" hint={realData ? undefined : REAL_DATA_ONLY}>
        <select className={control} value={config.kind ?? ''}
          onChange={(e) => onChange(withKind(e.target.value as OutputKind, config, catalog.target_fields[0].value))}>
          {config.kind === undefined && <option value="" disabled>Elige una opción</option>}
          {catalog.output_kinds.map((o) => (
            <option key={o.value} value={o.value} disabled={o.value === 'campo' && !realData && config.kind !== 'campo'}>{o.label}</option>
          ))}
        </select>
      </Field>
      {config.kind === 'metrica' && (
        <>
          <Select label="Agregación" value={config.aggregation} options={catalog.aggregations}
            onChange={(aggregation) => onChange({ ...config, aggregation })} />
          <p className="text-xs text-slate-500">La métrica cuenta las etiquetas del prompt de entrada, que debe tener formato «etiqueta».</p>
        </>
      )}
      {config.kind === 'campo' ? <FieldMappings config={config} prompt={prompt} onChange={onChange} /> : (
        <Field label="Nombre de destino" hint="Identifica el resultado en la pestaña de la ejecución.">
          <input className={control} value={config.destination ?? ''} maxLength={catalog.limits.max_destination}
            placeholder="motivos_de_queja" onChange={(e) => onChange({ ...config, destination: e.target.value })} />
        </Field>
      )}
    </Section>
  )
}

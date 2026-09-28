import { useCatalog } from '../catalog'
import type { OutputConfig } from '../types'
import { control, Field, Section, Select } from './controls'

export function OutputPanel({ config, onChange }: { config: OutputConfig; onChange: (config: OutputConfig) => void }) {
  const catalog = useCatalog()
  return (
    <Section title="Resultado">
      <Select label="Tipo de output" value={config.kind} options={catalog.output_kinds}
        onChange={(kind) => onChange({ ...config, kind, aggregation: kind === 'metrica' ? config.aggregation ?? 'recuento' : undefined })} />
      {config.kind === 'metrica' && (
        <>
          <Select label="Agregación" value={config.aggregation} options={catalog.aggregations}
            onChange={(aggregation) => onChange({ ...config, aggregation })} />
          <p className="text-xs text-slate-500">La métrica cuenta las etiquetas del prompt de entrada, que debe tener formato «etiqueta».</p>
        </>
      )}
      <Field label="Nombre de destino" hint="Identifica el resultado en la pestaña de la ejecución.">
        <input className={control} value={config.destination ?? ''} maxLength={catalog.limits.max_destination}
          placeholder="motivos_de_queja" onChange={(e) => onChange({ ...config, destination: e.target.value })} />
      </Field>
    </Section>
  )
}

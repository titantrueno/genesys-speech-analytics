import { configRequests } from '../api'
import { Card, ConfigField, input, SaveBar } from '../controls'
import type { AiConfig, PlatformConfig } from '../types'
import { useSectionForm } from '../useSectionForm'

export function AiTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const form = useSectionForm<AiConfig>({ provider: config.ai.provider, model: config.ai.model }, configRequests.ai)
  const provider = config.options.providers.find((p) => p.value === form.draft.provider)
  return (
    <Card title="Modelos de IA" description="Proveedor y modelo que toman los nodos Prompt nuevos de los flujos de insights.">
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
        La ejecución es simulada: los prompts no llaman a ningún LLM y no hace falta ninguna clave.
      </p>
      <fieldset disabled={!canEdit} className="grid gap-4 sm:grid-cols-2">
        <ConfigField label="Proveedor" error={form.errors.provider}>
          <select className={input} value={form.draft.provider} onChange={(e) => {
            const next = config.options.providers.find((p) => p.value === e.target.value)
            form.set('provider', e.target.value)
            if (next) form.set('model', next.models[0]?.value ?? '')
          }}>
            {config.options.providers.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </ConfigField>
        <ConfigField label="Modelo por defecto" error={form.errors.model}
          hint="Los nodos Prompt existentes conservan su modelo.">
          <select className={input} value={form.draft.model} onChange={(e) => form.set('model', e.target.value)}>
            {(provider?.models ?? []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </ConfigField>
      </fieldset>
      {canEdit && <SaveBar {...form.bar} />}
    </Card>
  )
}

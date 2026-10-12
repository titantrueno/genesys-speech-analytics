import { ApiError } from '../../api/client'
import { configRequests, useAiStatus, useAiTest } from '../api'
import { Card, ConfigField, input, SaveBar } from '../controls'
import type { AiConfig, AiStatus, PlatformConfig } from '../types'
import { useSectionForm } from '../useSectionForm'

const SIMULATED = 'simulado'

/** Un proveedor del servicio de LLM: si tiene clave (nunca la clave) y «Probar» con el modelo que se usaría. */
function ProviderRow({ provider, model, canEdit }: {
  provider: AiStatus['providers'][number]; model: string | undefined; canEdit: boolean
}) {
  const test = useAiTest()
  const result = test.data
  const simulated = provider.value === SIMULATED
  return (
    <li className="flex flex-wrap items-center gap-3 py-2">
      <span className="min-w-40 text-sm font-medium text-slate-800">{provider.label}</span>
      {simulated ? (
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">No necesita clave</span>
      ) : provider.key_configured ? (
        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">Clave configurada</span>
      ) : (
        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800">Sin clave</span>
      )}
      {canEdit && !simulated && model && (
        <button type="button" aria-label={`Probar ${provider.label}`} disabled={test.isPending}
          onClick={() => test.mutate({ provider: provider.value, model })}
          className="rounded-md border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-50 disabled:opacity-50">
          {test.isPending ? 'Probando…' : 'Probar'}
        </button>
      )}
      {result?.ok && <p role="status" className="text-sm text-emerald-700">{result.message}</p>}
      {result && !result.ok && <p role="alert" className="text-sm text-red-700">{result.message}</p>}
      {test.isError && (
        <p role="alert" className="text-sm text-red-700">
          {test.error instanceof ApiError && test.error.status === 503
            ? 'El servicio de LLM no está disponible' : 'No se ha podido probar el proveedor.'}
        </p>
      )}
    </li>
  )
}

function ServiceStatus({ config, draft, canEdit }: { config: PlatformConfig; draft: AiConfig; canEdit: boolean }) {
  const status = useAiStatus()
  // Se prueba con el modelo elegido si es de ese proveedor; si no, con el primero del proveedor.
  const modelFor = (provider: string) => draft.provider === provider
    ? draft.model : config.options.providers.find((p) => p.value === provider)?.models[0]?.value
  return (
    <section aria-label="Estado del servicio de LLM" className="space-y-2 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-semibold text-slate-900">Estado del servicio de LLM</h3>
      {status.isPending && <p className="text-sm text-slate-500">Comprobando el servicio de LLM…</p>}
      {status.isError && (
        <p role="alert" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          El servicio de LLM no está disponible: los prompts con un proveedor real no se pueden ejecutar hasta que
          responda.
        </p>
      )}
      {status.data && (
        <>
          <ul className="divide-y divide-slate-100">
            {status.data.providers.map((p) => (
              <ProviderRow key={p.value} provider={p} model={modelFor(p.value)} canEdit={canEdit} />
            ))}
          </ul>
          <p className="text-xs text-slate-500">
            Las claves se configuran en el .env del servicio de LLM; la plataforma nunca las muestra.
          </p>
        </>
      )}
    </section>
  )
}

export function AiTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const form = useSectionForm<AiConfig>({ provider: config.ai.provider, model: config.ai.model }, configRequests.ai)
  const provider = config.options.providers.find((p) => p.value === form.draft.provider)
  return (
    <Card title="Modelos de IA" description="Proveedor y modelo que toman los nodos Prompt nuevos de los flujos de insights.">
      {form.draft.provider === SIMULATED && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Con «Simulado», los prompts no llaman a ningún LLM: los resultados se derivan del análisis de cada conversación.
        </p>
      )}
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
          hint="Los nodos Prompt existentes conservan su proveedor y su modelo.">
          <select className={input} value={form.draft.model} onChange={(e) => form.set('model', e.target.value)}>
            {(provider?.models ?? []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </ConfigField>
      </fieldset>
      {canEdit && <SaveBar {...form.bar} />}
      <ServiceStatus config={config} draft={form.draft} canEdit={canEdit} />
    </Card>
  )
}

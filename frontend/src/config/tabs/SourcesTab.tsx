import { formatDateTime, formatInteger } from '../../lib/format'
import { configRequests, useConfigMutation, useConnectors } from '../api'
import { Card } from '../controls'

const STATUS: Record<string, string> = { conectado: 'Conectado' }

export function SourcesTab({ canEdit }: { canEdit: boolean }) {
  const { data, isError, isPending } = useConnectors()
  const sync = useConfigMutation(configRequests.sync)
  return (
    <Card title="Fuentes de datos"
      description="Conectores simulados de Genesys Cloud: no hay integración real y sincronizar no cambia las conversaciones.">
      {isPending && <p className="text-sm text-slate-500">Cargando conectores…</p>}
      {isError && <p role="alert" className="text-sm text-red-700">No se han podido cargar los conectores.</p>}
      {data && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {['Conector', 'Estado', 'Última sincronización', 'Conversaciones', ...(canEdit ? ['Acciones'] : [])].map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((connector) => (
                <tr key={connector.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-2 py-2 font-medium text-slate-800">{connector.name}</td>
                  <td className="px-2 py-2">
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
                      {STATUS[connector.status] ?? connector.status}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-slate-600">{formatDateTime(connector.last_sync)}</td>
                  <td className="px-2 py-2 tabular-nums">{formatInteger(connector.conversations)}</td>
                  {canEdit && (
                    <td className="px-2 py-2">
                      <button type="button" disabled={sync.isPending} onClick={() => sync.mutate(connector.id)}
                        aria-label={`Sincronizar ${connector.name}`}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50">
                        Sincronizar
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {sync.isError && <p role="alert" className="text-sm text-red-700">No se ha podido sincronizar.</p>}
    </Card>
  )
}

import type { ReactNode } from 'react'
import { ApiError } from '../../api/client'
import { useGenesysConnector, useTestGenesys } from '../../downloads/api'
import { CHANNEL_LABELS, DOWNLOAD_STATUS, QUALITY_LABELS } from '../../downloads/labels'
import { StatusBadge } from '../../flows/StatusBadge'
import { formatDateTime, formatInteger } from '../../lib/format'
import { configRequests, useConfigMutation, useConnectors } from '../api'
import { Card } from '../controls'

const STATUS: Record<string, string> = { conectado: 'Conectado' }

function MockConnectors({ canEdit }: { canEdit: boolean }) {
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

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[12rem_1fr] gap-2 border-b border-slate-100 py-1.5 last:border-0">
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-800">{children}</dd>
    </div>
  )
}

const split = (values: Record<string, number>, labels: Record<string, string>) =>
  Object.entries(labels).map(([key, label]) => `${label} ${formatInteger(values[key] ?? 0)}`).join(' · ')

/** Conector real (FE011): estado del servicio de ingesta, credenciales, última descarga y conversaciones guardadas. */
function GenesysCard({ canEdit }: { canEdit: boolean }) {
  const { data, isError, isPending } = useGenesysConnector()
  const test = useTestGenesys()
  const result = test.data
  return (
    <Card title="Genesys Cloud · datos reales"
      description="Conversaciones reales que descarga el servicio de ingesta. Las descargas se crean y se lanzan en Flujos de insights.">
      {isPending && <p className="text-sm text-slate-500">Cargando el estado de Genesys…</p>}
      {isError && <p role="alert" className="text-sm text-red-700">No se ha podido cargar el estado de Genesys.</p>}
      {data && data.service === 'no_disponible' && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          El servicio de ingesta no responde: arráncalo para descargar conversaciones de Genesys.
        </p>
      )}
      {data && data.service === 'disponible' && (
        <dl>
          <Item label="Servicio de ingesta">
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">Disponible</span>
          </Item>
          <Item label="Región">{data.region ?? '—'}</Item>
          <Item label="Credenciales">{data.credentials_configured ? 'Configuradas' : 'No configuradas en el .env'}</Item>
          <Item label="Última prueba">
            {data.last_test
              ? `${data.last_test.ok ? 'Correcta' : 'Fallida'} · ${formatDateTime(data.last_test.at)}`
                + (data.last_test.organization ? ` · ${data.last_test.organization}` : '')
              : 'Sin probar'}
          </Item>
          <Item label="Última descarga">
            {data.last_download?.finished_at ? (
              <span className="inline-flex items-center gap-2">
                {formatDateTime(data.last_download.finished_at)}
                <StatusBadge {...DOWNLOAD_STATUS[data.last_download.status]} />
              </span>
            ) : 'Ninguna'}
          </Item>
          {data.conversations && (
            <>
              <Item label="Conversaciones guardadas">{formatInteger(data.conversations.total)}</Item>
              <Item label="Por canal">{split(data.conversations.by_channel, CHANNEL_LABELS)}</Item>
              <Item label="Por calidad de la transcripción">{split(data.conversations.by_quality, QUALITY_LABELS)}</Item>
            </>
          )}
        </dl>
      )}
      {canEdit && (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" disabled={test.isPending} onClick={() => test.mutate()}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50">
            Probar conexión
          </button>
          {result?.ok && (
            <p role="status" className="text-sm text-emerald-700">
              {result.message}: {result.organization} ({result.region})
            </p>
          )}
          {result && !result.ok && <p role="alert" className="text-sm text-red-700">{result.message}</p>}
          {test.isError && (
            <p role="alert" className="text-sm text-red-700">
              {test.error instanceof ApiError && test.error.status === 503
                ? 'El servicio de ingesta no está disponible' : 'No se ha podido probar la conexión.'}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

export function SourcesTab({ canEdit }: { canEdit: boolean }) {
  return (
    <div className="space-y-4">
      <MockConnectors canEdit={canEdit} />
      <GenesysCard canEdit={canEdit} />
    </div>
  )
}

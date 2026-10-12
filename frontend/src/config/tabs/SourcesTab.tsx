import { useState, type ReactNode } from 'react'
import { ApiError } from '../../api/client'
import { useGenesysConnector, useTestGenesys } from '../../downloads/api'
import { CHANNEL_LABELS, DOWNLOAD_STATUS, QUALITY_LABELS } from '../../downloads/labels'
import { StatusBadge } from '../../flows/StatusBadge'
import { formatDateTime, formatInteger } from '../../lib/format'
import { configRequests, useConfigMutation, useConnectors } from '../api'
import { Card } from '../controls'
import type { DataOrigin, PlatformConfig } from '../types'

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

const ORIGINS: Array<{ value: DataOrigin; label: string; description: string }> = [
  { value: 'sintetico', label: 'Sintético', description: 'El dataset generado de demostración (1.000 conversaciones de los últimos 90 días).' },
  { value: 'real', label: 'Real (Genesys Cloud)', description: 'Las conversaciones que ha descargado el servicio de ingesta y guarda PostgreSQL.' },
]

/** Origen de datos de toda la plataforma (FE012): al cambiarlo, dashboards, listado, explorador, búsqueda y flujos lo siguen. */
function OriginCard({ origin, canEdit }: { origin: DataOrigin; canEdit: boolean }) {
  const [pending, setPending] = useState<DataOrigin | null>(null)
  const change = useConfigMutation(configRequests.sources)
  const target = ORIGINS.find((o) => o.value === pending)
  return (
    <Card title="Origen de datos"
      description="Toda la plataforma trabaja con un único origen a la vez. Se pierde al reiniciar la API y vuelve a sintético.">
      <fieldset disabled={!canEdit || change.isPending} className="space-y-2">
        <legend className="sr-only">Origen de datos</legend>
        {ORIGINS.map((option) => (
          <label key={option.value} className="flex items-start gap-3 text-sm text-slate-700">
            <input type="radio" name="data-origin" className="mt-0.5 size-4" checked={(pending ?? origin) === option.value}
              onChange={() => { change.reset(); setPending(option.value === origin ? null : option.value) }} />
            <span>
              <span className="font-medium">{option.label}</span>
              <span className="block text-slate-500">{option.description}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {canEdit && target && (
        <div role="alertdialog" aria-label="Confirmar cambio de origen"
          className="space-y-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p>
            {target.value === 'real'
              ? 'Todas las secciones pasarán a trabajar con las conversaciones reales de Genesys. El análisis de la plataforma (summary, main topic, CSAT…) aparecerá como pendiente.'
              : 'Todas las secciones volverán a trabajar con el dataset sintético.'}
          </p>
          <div className="flex gap-2">
            <button type="button" disabled={change.isPending}
              onClick={() => change.mutate({ origin: target.value }, { onSuccess: () => setPending(null) })}
              className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
              Confirmar cambio
            </button>
            <button type="button" onClick={() => { change.reset(); setPending(null) }}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">
              Cancelar
            </button>
          </div>
        </div>
      )}
      {change.isError && <p role="alert" className="text-sm text-red-700">No se ha podido cambiar el origen de datos.</p>}
    </Card>
  )
}

export function SourcesTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const origin = config.sources.origin
  return (
    <div className="space-y-4">
      <OriginCard origin={origin} canEdit={canEdit} />
      {/* Con el origen real, el estado del conector de Genesys sustituye a los conectores simulados. */}
      {origin === 'sintetico' && <MockConnectors canEdit={canEdit} />}
      <GenesysCard canEdit={canEdit} />
    </div>
  )
}

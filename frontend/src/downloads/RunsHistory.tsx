import { useRowNavigation } from '../conversations/useRowNavigation'
import { StatusBadge } from '../flows/StatusBadge'
import { formatDateTime, formatInteger } from '../lib/format'
import { useDownloadRuns } from './api'
import { DOWNLOAD_STATUS, formatSeconds, ORIGIN_LABELS } from './labels'
import type { DownloadRun } from './types'

function RunRow({ run }: { run: DownloadRun }) {
  const { onClick, onAuxClick } = useRowNavigation(`/flujos/descargas/${run.flow_id}/ejecuciones/${run.id}`)
  const { counters } = run
  return (
    <tr onClick={onClick} onAuxClick={onAuxClick} className="cursor-pointer border-b border-slate-100 hover:bg-brand-50/60">
      <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(run.created_at)}</td>
      <td className="px-3 py-2">{ORIGIN_LABELS[run.origin]}{run.started_by && ` · ${run.started_by.name}`}</td>
      <td className="px-3 py-2 whitespace-nowrap text-slate-600">
        {formatDateTime(run.interval.from)} – {formatDateTime(run.interval.to)}
      </td>
      <td className="px-3 py-2 text-slate-600">
        {formatInteger(counters.inserted)} insertadas · {formatInteger(counters.updated)} actualizadas
        {counters.errors > 0 && ` · ${formatInteger(counters.errors)} con error`}
      </td>
      <td className="px-3 py-2 tabular-nums">{formatSeconds(run.duration_s)}</td>
      <td className="px-3 py-2"><StatusBadge {...DOWNLOAD_STATUS[run.status]} /></td>
    </tr>
  )
}

/** Historial de un flujo de descarga (las 200 más recientes); cada fila abre su ejecución. */
export function RunsHistory({ flowId }: { flowId: string }) {
  const { data, isError, isPending } = useDownloadRuns(flowId)
  return (
    <section aria-label="Historial de descargas" className="space-y-2 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900">Historial de descargas</h2>
      {isPending && <p role="status" className="text-sm text-slate-500">Cargando historial…</p>}
      {isError && <p role="alert" className="text-sm text-red-700">No se ha podido cargar el historial.</p>}
      {data && data.items.length === 0 && <p className="text-sm text-slate-500">Todavía no se ha ejecutado.</p>}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {['Fecha', 'Origen', 'Intervalo', 'Conversaciones', 'Duración', 'Estado'].map((label) => (
                  <th key={label} scope="col" className="px-3 py-1.5 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>{data.items.map((run) => <RunRow key={run.id} run={run} />)}</tbody>
          </table>
        </div>
      )}
    </section>
  )
}

import { useRowNavigation } from '../conversations/useRowNavigation'
import { StatusBadge } from '../flows/StatusBadge'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime, formatInteger } from '../lib/format'
import { useDownloadRuns } from './api'
import { DOWNLOAD_STATUS, formatSeconds, ORIGIN_KEYS } from './labels'
import type { DownloadRun } from './types'

function RunRow({ run }: { run: DownloadRun }) {
  const { t } = useI18n()
  const { onClick, onAuxClick } = useRowNavigation(`/flujos/descargas/${run.flow_id}/ejecuciones/${run.id}`)
  const { counters } = run
  return (
    <tr onClick={onClick} onAuxClick={onAuxClick} className="cursor-pointer border-b border-slate-100 hover:bg-brand-50/60">
      <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(run.created_at)}</td>
      <td className="px-3 py-2">{t(ORIGIN_KEYS[run.origin])}{run.started_by && ` · ${run.started_by.name}`}</td>
      <td className="px-3 py-2 whitespace-nowrap text-slate-600">
        {formatDateTime(run.interval.from)} – {formatDateTime(run.interval.to)}
      </td>
      <td className="px-3 py-2 text-slate-600">
        {t('dl.hist.saved', { inserted: formatInteger(counters.inserted), updated: formatInteger(counters.updated) })}
        {counters.errors > 0 && t('dl.hist.withErrors', { n: formatInteger(counters.errors) })}
      </td>
      <td className="px-3 py-2 tabular-nums">{formatSeconds(run.duration_s)}</td>
      <td className="px-3 py-2"><StatusBadge label={t(DOWNLOAD_STATUS[run.status].label)} className={DOWNLOAD_STATUS[run.status].className} /></td>
    </tr>
  )
}

/** Historial de un flujo de descarga (las 200 más recientes); cada fila abre su ejecución. */
export function RunsHistory({ flowId }: { flowId: string }) {
  const { t } = useI18n()
  const { data, isError, isPending } = useDownloadRuns(flowId)
  return (
    <section aria-label={t('dl.hist.title')} className="space-y-2 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900">{t('dl.hist.title')}</h2>
      {isPending && <p role="status" className="text-sm text-slate-500">{t('dl.hist.loading')}</p>}
      {isError && <p role="alert" className="text-sm text-red-700">{t('dl.hist.error')}</p>}
      {data && data.items.length === 0 && <p className="text-sm text-slate-500">{t('dl.hist.empty')}</p>}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {(['dl.hist.col.date', 'dl.hist.col.origin', 'dl.hist.col.interval', 'dl.hist.col.conversations', 'dl.hist.col.duration', 'dl.hist.col.status'] as const).map((label) => (
                  <th key={label} scope="col" className="px-3 py-1.5 font-medium">{t(label)}</th>
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

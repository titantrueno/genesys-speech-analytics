import { Download } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime } from '../lib/format'
import { downloadLogFile, useDownloadLog } from './api'
import { LEVEL_KEYS } from './labels'
import type { LogLevel } from './types'

const LEVEL_CLASS: Record<LogLevel, string> = {
  info: 'text-slate-500', aviso: 'text-amber-800', error: 'text-[var(--status-critical)]',
}

/**
 * Log de una descarga: el de un flujo de descarga (FE011) o el de la caja «Genesys download» de una ejecución de insights
 * (FE017). `basePath` es la ruta de la descarga en la API; el log está en `<basePath>/log`.
 */
export function DownloadLog({ basePath, runId, active }: { basePath: string; runId: string; active: boolean }) {
  const { t } = useI18n()
  const [level, setLevel] = useState<LogLevel | null>(null)
  const log = useDownloadLog(basePath, level, active)
  const [downloading, setDownloading] = useState(false)
  const [downloadFailed, setDownloadFailed] = useState(false)
  const wasActive = useRef(active)
  const { refetch } = log
  useEffect(() => {
    // Al terminar, una última lectura recoge las entradas escritas después del último polling.
    if (wasActive.current && !active) void refetch()
    wasActive.current = active
  }, [active, refetch])

  async function download() {
    setDownloading(true)
    setDownloadFailed(false)
    try {
      await downloadLogFile(basePath, runId)
    } catch {
      setDownloadFailed(true)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <section aria-label={t('dl.log.title')} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-900">{t('dl.log.title')}</h2>
        <div className="flex items-end gap-2">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
            {t('dl.log.level')}
            <select className="h-8 rounded-md border border-slate-300 px-2 text-sm" value={level ?? ''}
              onChange={(e) => setLevel((e.target.value || null) as LogLevel | null)}>
              <option value="">{t('dl.log.all')}</option>
              {Object.entries(LEVEL_KEYS).map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}
            </select>
          </label>
          <button type="button" onClick={download} disabled={downloading}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <Download className="size-4" aria-hidden />{t('dl.log.download')}
          </button>
        </div>
      </header>
      {downloadFailed && <p role="alert" className="text-sm text-red-700">{t('dl.log.downloadError')}</p>}
      {log.isPending && <p role="status" className="text-sm text-slate-500">{t('dl.log.loading')}</p>}
      {log.isError && <p role="alert" className="text-sm text-red-700">{t('dl.log.loadError')}</p>}
      {log.data && log.data.length === 0 && <p className="text-sm text-slate-500">{t('dl.log.empty')}</p>}
      {log.data && log.data.length > 0 && (
        <div className="max-h-[28rem] overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {(['dl.log.col.time', 'dl.log.col.level', 'dl.log.col.stage', 'dl.log.col.message', 'dl.log.col.conversation'] as const).map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 font-medium">{t(label)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {log.data.map((entry) => (
                <tr key={entry.id} className="border-b border-slate-100 align-top">
                  <td className="px-2 py-1.5 whitespace-nowrap text-slate-500">{formatDateTime(entry.at)}</td>
                  <td className={`px-2 py-1.5 font-medium ${LEVEL_CLASS[entry.level]}`}>{t(LEVEL_KEYS[entry.level])}</td>
                  <td className="px-2 py-1.5 text-slate-600">{entry.stage}</td>
                  <td className="px-2 py-1.5 text-slate-800">{entry.message}</td>
                  <td className="px-2 py-1.5 font-mono text-xs text-slate-500">{entry.genesys_id ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

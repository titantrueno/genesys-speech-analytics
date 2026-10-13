import { ArrowLeft, Download } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { StatusBadge } from '../flows/StatusBadge'
import { useI18n } from '../i18n/useI18n'
import { LoadingScreen } from '../layout/LoadingScreen'
import { formatDateTime, formatInteger } from '../lib/format'
import { downloadLogFile, isActive, useDownloadFlow, useDownloadLog, useDownloadRun } from './api'
import { CHANNEL_KEYS, DOWNLOAD_STATUS, formatSeconds, LEVEL_KEYS, ORIGIN_KEYS, QUALITY_KEYS, splitCounts } from './labels'
import type { DownloadRun, LogLevel } from './types'

const link = 'inline-flex items-center gap-1 text-sm text-brand-700 hover:underline'
const LEVEL_CLASS: Record<LogLevel, string> = {
  info: 'text-slate-500', aviso: 'text-amber-800', error: 'text-[var(--status-critical)]',
}

function Counter({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 px-3 py-2">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm font-medium text-slate-900">{value}</dd>
    </div>
  )
}

function Counters({ run }: { run: DownloadRun }) {
  const { t } = useI18n()
  const c = run.counters
  return (
    <section aria-label={t('dl.counters')} className="rounded-xl border border-slate-200 bg-white p-5">
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Counter label={t('dl.counter.downloaded')} value={t('dl.counter.downloadedValue', { downloaded: formatInteger(c.downloaded), found: formatInteger(c.found) })} />
        <Counter label={t('dl.counter.saved')} value={t('dl.counter.savedValue', { inserted: formatInteger(c.inserted), updated: formatInteger(c.updated) })} />
        <Counter label={t('dl.counter.skipped')} value={t('dl.counter.skippedValue', {
          skipped: formatInteger(c.skipped), inProgress: formatInteger(c.skipped_in_progress), otherChannel: formatInteger(c.skipped_other_channel) })} />
        <Counter label={t('dl.counter.existing')} value={formatInteger(c.skipped_existing)} />
        <Counter label={t('dl.counter.errors')} value={formatInteger(c.errors)} />
        <Counter label={t('dl.counter.byChannel')} value={splitCounts(t, c.by_channel, CHANNEL_KEYS)} />
        <Counter label={t('dl.counter.byQuality')} value={splitCounts(t, c.by_quality, QUALITY_KEYS)} />
        <Counter label={t('dl.counter.undelivered')} value={formatInteger(c.undelivered_messages)} />
        <Counter label={t('dl.counter.duration')} value={formatSeconds(run.duration_s)} />
      </dl>
    </section>
  )
}

function Log({ flowId, run }: { flowId: string; run: DownloadRun }) {
  const { t } = useI18n()
  const [level, setLevel] = useState<LogLevel | null>(null)
  const active = isActive(run.status)
  const log = useDownloadLog(flowId, run.id, level, active)
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
      await downloadLogFile(flowId, run.id)
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

export function DownloadRunPage() {
  const { t } = useI18n()
  const { flowId = '', runId = '' } = useParams()
  const flow = useDownloadFlow(flowId)
  const run = useDownloadRun(flowId, runId)
  const back = <Link to={`/flujos/descargas/${flowId}`} className={link}><ArrowLeft className="size-4" aria-hidden />{t('dl.run.back')}</Link>

  if (run.isPending) return <LoadingScreen />
  if (run.isError) {
    const message = run.error instanceof ApiError && run.error.status === 404 ? t('dl.run.notFound')
      : t('dl.run.loadError')
    return <div className="space-y-3">{back}<p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p></div>
  }
  const data = run.data
  return (
    <div className="space-y-4">
      {back}
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">{t('dl.run.title', { date: formatDateTime(data.created_at) })}</h1>
          <StatusBadge label={t(DOWNLOAD_STATUS[data.status].label)} className={DOWNLOAD_STATUS[data.status].className} />
        </div>
        <p className="text-sm text-slate-500">
          {flow.data?.name ?? t('dl.run.defaultName')} · {t(ORIGIN_KEYS[data.origin])}
          {data.started_by && t('dl.run.startedBy', { name: data.started_by.name })}
          {t('dl.run.interval', { from: formatDateTime(data.interval.from), to: formatDateTime(data.interval.to) })} · {data.channels.map((c) => t(CHANNEL_KEYS[c])).join(t('dl.run.and'))}
          {data.overwrite !== null && t(data.overwrite ? 'dl.run.overwrites' : 'dl.run.skips')}
        </p>
      </header>
      {data.status === 'error' && data.error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{data.error}</p>
      )}
      <Counters run={data} />
      <Log flowId={flowId} run={data} />
    </div>
  )
}

import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { StatusBadge } from '../flows/StatusBadge'
import { useI18n } from '../i18n/useI18n'
import { LoadingScreen } from '../layout/LoadingScreen'
import { formatDateTime, formatInteger } from '../lib/format'
import { isActive, useDownloadFlow, useDownloadRun } from './api'
import { DownloadLog } from './DownloadLog'
import { CHANNEL_KEYS, DOWNLOAD_STATUS, formatSeconds, ORIGIN_KEYS, QUALITY_KEYS, splitCounts } from './labels'
import type { DownloadRun } from './types'

const link = 'inline-flex items-center gap-1 text-sm text-brand-700 hover:underline'

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
      <DownloadLog basePath={`/api/download-flows/${flowId}/runs/${data.id}`} runId={data.id} active={isActive(data.status)} />
    </div>
  )
}

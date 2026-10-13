import { ReactFlowProvider } from '@xyflow/react'
import { ArrowLeft, History } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { DownloadLog } from '../downloads/DownloadLog'
import { DOWNLOAD_STATUS, ORIGIN_KEYS } from '../downloads/labels'
import { useI18n } from '../i18n/useI18n'
import { LoadingScreen } from '../layout/LoadingScreen'
import { formatDateTime, formatInteger, formatUpToOneDecimal } from '../lib/format'
import { useFlow, useFlowCatalog, useRun, useRuns } from './api'
import { CatalogContext } from './catalog'
import { FlowCanvas } from './FlowCanvas'
import { toCanvasEdges, toCanvasNodes } from './graph'
import { RUN_STATUS } from './labels'
import { NODE_LABELS } from './rules'
import { RunOutputs } from './RunOutputs'
import { StatusBadge } from './StatusBadge'
import type { Run, RunDownload, RunOutput, RunSummary } from './types'

const link = 'inline-flex items-center gap-1 text-sm text-brand-700 hover:underline'
const secondary = 'inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50'

function formatRunDuration(ms: number | null): string {
  if (ms === null) return '—'
  return ms < 1000 ? `${ms} ms` : `${formatUpToOneDecimal(ms / 1000)} s`
}

function Failure({ message }: { message: string }) {
  return <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>
}

function RunCanvas({ run }: { run: Run }) {
  const { t } = useI18n()
  const nodes = useMemo(() => toCanvasNodes(run.graph).map((n) => ({ ...n, data: { ...n.data, state: run.nodes[n.id] } })), [run])
  const edges = useMemo(() => toCanvasEdges(run.graph), [run.graph])
  return (
    <div className="h-[26rem] overflow-hidden rounded-xl border border-slate-200 bg-white">
      <ReactFlowProvider>
        <FlowCanvas nodes={nodes} edges={edges} editable={false} label={t('flows.run.graph')} />
      </ReactFlowProvider>
    </div>
  )
}

/** Descarga de la caja «Genesys download» (FE017): estado, contadores y, a petición, su log. */
function DownloadSection({ flowId, runId, download }: { flowId: string; runId: string; download: RunDownload }) {
  const { t } = useI18n()
  const [showLog, setShowLog] = useState(false)
  const c = download.counters
  const status = DOWNLOAD_STATUS[download.status]
  const active = download.status === 'pendiente' || download.status === 'en_curso'
  const counters: Array<[string, number]> = [
    [t('flows.run.download.found'), c.found], [t('flows.run.download.saved'), c.inserted + c.updated],
    [t('flows.run.download.existing'), c.skipped_existing + c.skipped], [t('flows.run.download.errors'), c.errors],
  ]
  return (
    <section aria-label={t('flows.run.download.title')} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          {t('flows.run.download.title')}<StatusBadge label={t(status.label)} className={status.className} />
        </h2>
        <button type="button" className={secondary} aria-expanded={showLog} onClick={() => setShowLog((v) => !v)}>
          {showLog ? t('flows.run.download.hideLog') : t('flows.run.download.showLog')}
        </button>
      </header>
      {download.error && <p role="alert" className="text-sm text-red-700">{download.error}</p>}
      <dl className="grid gap-2 sm:grid-cols-4">
        {counters.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-slate-200 px-3 py-2">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="text-sm font-medium text-slate-900 tabular-nums">{formatInteger(value)}</dd>
          </div>
        ))}
      </dl>
      {showLog && <DownloadLog basePath={`/api/flows/${flowId}/runs/${runId}/download`} runId={download.run_id} active={active} />}
    </section>
  )
}

export function RunPage() {
  const { t } = useI18n()
  const { flowId = '', runId = '' } = useParams()
  const flow = useFlow(flowId)
  const catalog = useFlowCatalog()
  const run = useRun(flowId, runId)
  const back = <Link to={`/flujos/${flowId}`} className={link}><ArrowLeft className="size-4" aria-hidden />{t('flows.run.back')}</Link>

  if (run.isError || catalog.isError) {
    const notFound = run.error instanceof ApiError && run.error.status === 404
    return <div className="space-y-3">{back}<Failure message={notFound ? t('flows.run.notFound') : t('flows.run.loadError')} /></div>
  }
  if (!run.data || !catalog.data) return <LoadingScreen />

  const data = run.data
  const active = data.status === 'pendiente' || data.status === 'en_curso'
  const outputs = data.graph.nodes.map((n) => data.outputs[n.id]).filter((o): o is RunOutput => Boolean(o))
  const failures = data.graph.nodes.filter((n) => data.nodes[n.id]?.status === 'error')

  return (
    <CatalogContext.Provider value={catalog.data}>
      <div className="space-y-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            {back}
            <h1 className="text-2xl font-semibold text-slate-900">
              {t('flows.run.title', { name: flow.data?.name ?? t('flows.run.defaultName') })}
            </h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600">
              <StatusBadge label={t(RUN_STATUS[data.status].label)} className={RUN_STATUS[data.status].className} />
              <span>{formatDateTime(data.created_at)}</span>
              <span>{t(ORIGIN_KEYS[data.origin])}</span>
              <span>{data.user.name}</span>
              <span>{t('flows.run.sample', { value: data.sample_size === null ? '—' : formatInteger(data.sample_size) })}</span>
              <span>{t('flows.run.duration', { value: formatRunDuration(data.duration_ms) })}</span>
            </p>
          </div>
          <Link to={`/flujos/${flowId}/ejecuciones`} className={secondary}><History className="size-4" aria-hidden />{t('flows.run.history')}</Link>
        </header>
        {active && <p role="status" className="text-sm text-slate-500">{t('flows.run.running')}</p>}
        {data.notes.length > 0 && (
          <ul role="note" className="space-y-1 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {data.notes.map((note) => <li key={note}>{note}</li>)}
          </ul>
        )}
        {data.download && <DownloadSection flowId={flowId} runId={data.id} download={data.download} />}
        {failures.map((n) => (
          <Failure key={n.id} message={`${NODE_LABELS[n.type]}: ${data.nodes[n.id].message ?? t('flows.run.error')}`} />
        ))}
        <RunCanvas run={data} />
        {outputs.length > 0 ? <RunOutputs outputs={outputs} /> : (
          <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-500">
            {active ? t('flows.run.resultsLater') : t('flows.run.noResults')}
          </p>
        )}
      </div>
    </CatalogContext.Provider>
  )
}

function RunRow({ flowId, run }: { flowId: string; run: RunSummary }) {
  const { t } = useI18n()
  return (
    <tr className="border-b border-slate-100">
      <td className="px-3 py-2.5 whitespace-nowrap">
        <Link to={`/flujos/${flowId}/ejecuciones/${run.id}`} className="font-medium text-brand-700 hover:underline">
          {formatDateTime(run.created_at)}
        </Link>
      </td>
      <td className="px-3 py-2.5 text-slate-700">{t(ORIGIN_KEYS[run.origin])}</td>
      <td className="px-3 py-2.5 text-slate-700">{run.user.name}</td>
      <td className="px-3 py-2.5 text-right text-slate-700 tabular-nums">{run.sample_size === null ? '—' : formatInteger(run.sample_size)}</td>
      <td className="px-3 py-2.5 text-right text-slate-700 tabular-nums">{formatRunDuration(run.duration_ms)}</td>
      <td className="px-3 py-2.5"><StatusBadge label={t(RUN_STATUS[run.status].label)} className={RUN_STATUS[run.status].className} /></td>
    </tr>
  )
}

export function RunsPage() {
  const { t } = useI18n()
  const { flowId = '' } = useParams()
  const flow = useFlow(flowId)
  const runs = useRuns(flowId)
  const back = <Link to={`/flujos/${flowId}`} className={link}><ArrowLeft className="size-4" aria-hidden />{t('flows.run.back')}</Link>
  if (runs.isError) {
    const notFound = runs.error instanceof ApiError && runs.error.status === 404
    return <div className="space-y-3">{back}<Failure message={notFound ? t('flows.runs.flowNotFound') : t('flows.runs.loadError')} /></div>
  }
  return (
    <div className="space-y-4">
      <header>
        {back}
        <h1 className="text-2xl font-semibold text-slate-900">{t('flows.runs.title')}{flow.data && ` · ${flow.data.name}`}</h1>
      </header>
      {runs.isPending && <p role="status" className="text-sm text-slate-500">{t('flows.runs.loading')}</p>}
      {runs.data?.items.length === 0 && <p className="text-sm text-slate-500">{t('flows.runs.empty')}</p>}
      {runs.data && runs.data.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {(['flows.runs.col.date', 'flows.runs.col.origin', 'flows.runs.col.user', 'flows.runs.col.sample', 'flows.runs.col.duration', 'flows.runs.col.status'] as const).map((c, i) => (
                  <th key={c} scope="col" className={`px-3 py-2 font-medium ${i === 3 || i === 4 ? 'text-right' : ''}`}>{t(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody>{runs.data.items.map((run) => <RunRow key={run.id} flowId={flowId} run={run} />)}</tbody>
          </table>
        </div>
      )}
    </div>
  )
}

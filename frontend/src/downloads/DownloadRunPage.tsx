import { ArrowLeft, Download } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { StatusBadge } from '../flows/StatusBadge'
import { LoadingScreen } from '../layout/LoadingScreen'
import { formatDateTime, formatInteger } from '../lib/format'
import { downloadLogFile, isActive, useDownloadFlow, useDownloadLog, useDownloadRun } from './api'
import { CHANNEL_LABELS, DOWNLOAD_STATUS, formatSeconds, LEVEL_LABELS, ORIGIN_LABELS, QUALITY_LABELS } from './labels'
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
  const c = run.counters
  const split = (values: Record<string, number>, labels: Record<string, string>) =>
    Object.entries(labels).map(([key, label]) => `${label} ${formatInteger(values[key] ?? 0)}`).join(' · ')
  return (
    <section aria-label="Contadores" className="rounded-xl border border-slate-200 bg-white p-5">
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Counter label="Descargadas" value={`${formatInteger(c.downloaded)} de ${formatInteger(c.found)} descargadas`} />
        <Counter label="Guardadas" value={`${formatInteger(c.inserted)} insertadas · ${formatInteger(c.updated)} actualizadas`} />
        <Counter label="Omitidas" value={`${formatInteger(c.skipped)} (${formatInteger(c.skipped_in_progress)} en curso, `
          + `${formatInteger(c.skipped_other_channel)} de otro canal)`} />
        <Counter label="Ya existentes (no descargadas)" value={formatInteger(c.skipped_existing)} />
        <Counter label="Con error" value={formatInteger(c.errors)} />
        <Counter label="Por canal" value={split(c.by_channel, CHANNEL_LABELS)} />
        <Counter label="Calidad de la transcripción" value={split(c.by_quality, QUALITY_LABELS)} />
        <Counter label="Mensajes no entregados" value={formatInteger(c.undelivered_messages)} />
        <Counter label="Duración" value={formatSeconds(run.duration_s)} />
      </dl>
    </section>
  )
}

function Log({ flowId, run }: { flowId: string; run: DownloadRun }) {
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
    <section aria-label="Log" className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-900">Log</h2>
        <div className="flex items-end gap-2">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
            Nivel
            <select className="h-8 rounded-md border border-slate-300 px-2 text-sm" value={level ?? ''}
              onChange={(e) => setLevel((e.target.value || null) as LogLevel | null)}>
              <option value="">Todos</option>
              {Object.entries(LEVEL_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <button type="button" onClick={download} disabled={downloading}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            <Download className="size-4" aria-hidden />Descargar log
          </button>
        </div>
      </header>
      {downloadFailed && <p role="alert" className="text-sm text-red-700">No se ha podido descargar el log.</p>}
      {log.isPending && <p role="status" className="text-sm text-slate-500">Cargando log…</p>}
      {log.isError && <p role="alert" className="text-sm text-red-700">No se ha podido cargar el log.</p>}
      {log.data && log.data.length === 0 && <p className="text-sm text-slate-500">Sin entradas.</p>}
      {log.data && log.data.length > 0 && (
        <div className="max-h-[28rem] overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {['Hora', 'Nivel', 'Etapa', 'Mensaje', 'Conversación'].map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {log.data.map((entry) => (
                <tr key={entry.id} className="border-b border-slate-100 align-top">
                  <td className="px-2 py-1.5 whitespace-nowrap text-slate-500">{formatDateTime(entry.at)}</td>
                  <td className={`px-2 py-1.5 font-medium ${LEVEL_CLASS[entry.level]}`}>{LEVEL_LABELS[entry.level]}</td>
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
  const { flowId = '', runId = '' } = useParams()
  const flow = useDownloadFlow(flowId)
  const run = useDownloadRun(flowId, runId)
  const back = <Link to={`/flujos/descargas/${flowId}`} className={link}><ArrowLeft className="size-4" aria-hidden />Volver al flujo</Link>

  if (run.isPending) return <LoadingScreen />
  if (run.isError) {
    const message = run.error instanceof ApiError && run.error.status === 404 ? 'La ejecución no existe.'
      : 'No se ha podido cargar la ejecución.'
    return <div className="space-y-3">{back}<p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p></div>
  }
  const data = run.data
  return (
    <div className="space-y-4">
      {back}
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">Descarga {formatDateTime(data.created_at)}</h1>
          <StatusBadge {...DOWNLOAD_STATUS[data.status]} />
        </div>
        <p className="text-sm text-slate-500">
          {flow.data?.name ?? 'Flujo de descarga'} · {ORIGIN_LABELS[data.origin]}
          {data.started_by && ` · lanzada por ${data.started_by.name}`} · intervalo {formatDateTime(data.interval.from)} –{' '}
          {formatDateTime(data.interval.to)} · {data.channels.map((c) => CHANNEL_LABELS[c]).join(' y ')}
          {data.overwrite !== null && ` · ${data.overwrite ? 'sobrescribe' : 'omite'} las conversaciones que ya existen`}
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

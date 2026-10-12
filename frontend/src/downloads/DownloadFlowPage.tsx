import { ArrowLeft, Play } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { LoadingScreen } from '../layout/LoadingScreen'
import { formatDateTime } from '../lib/format'
import { useDownloadFlow, useDownloadMutations, useStartDownload } from './api'
import { DownloadFlowForm } from './DownloadFlowForm'
import { describeSchedule } from './labels'
import { RunsHistory } from './RunsHistory'

const link = 'inline-flex items-center gap-1 text-sm text-brand-700 hover:underline'

export function DownloadFlowPage() {
  const { flowId = '' } = useParams()
  const { can } = useAuth()
  const canEdit = can('flows:edit')
  const flow = useDownloadFlow(flowId)
  const { update } = useDownloadMutations()
  const start = useStartDownload(flowId)
  const navigate = useNavigate()

  if (flow.isPending) return <LoadingScreen />
  if (flow.isError) {
    const message = flow.error instanceof ApiError && flow.error.status === 404
      ? 'El flujo de descarga no existe.'
      : flow.error instanceof ApiError && flow.error.status === 503
        ? 'El servicio de ingesta no está disponible.'
        : 'No se ha podido cargar el flujo de descarga.'
    return (
      <div className="space-y-3">
        <Link to="/flujos" className={link}><ArrowLeft className="size-4" aria-hidden />Volver a los flujos</Link>
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>
      </div>
    )
  }
  const data = flow.data
  return (
    <div className="space-y-4">
      <Link to="/flujos" className={link}><ArrowLeft className="size-4" aria-hidden />Volver a los flujos</Link>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold text-slate-900">{data.name}</h1>
          <p className="text-sm text-slate-500">
            Descarga de transcripciones de Genesys Cloud · {describeSchedule(data.schedule)}
            {data.next_run_at && ` · próxima ejecución: ${formatDateTime(data.next_run_at)}`}
            {!canEdit && ' · Tienes acceso de solo lectura.'}
          </p>
        </div>
        {canEdit && (
          <button type="button" disabled={start.isPending}
            onClick={() => start.mutate(undefined, { onSuccess: (run) => navigate(`/flujos/descargas/${data.id}/ejecuciones/${run.id}`) })}
            className="inline-flex items-center gap-1.5 rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            <Play className="size-4" aria-hidden />Ejecutar ahora
          </button>
        )}
      </header>
      {start.isError && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {start.error instanceof ApiError && start.error.status === 409
            ? 'Ya hay una descarga en curso de este flujo: espera a que termine.'
            : start.error instanceof ApiError && start.error.status === 503
              ? 'El servicio de ingesta no está disponible.' : 'No se ha podido lanzar la descarga.'}
        </p>
      )}
      <section aria-label="Configuración de la descarga" className="rounded-xl border border-slate-200 bg-white p-5">
        <DownloadFlowForm key={data.updated_at} flow={data} canEdit={canEdit} pending={update.isPending}
          error={update.error} saved={update.isSuccess}
          onSave={(body) => update.mutate({ id: data.id, body })} />
      </section>
      <RunsHistory flowId={data.id} />
    </div>
  )
}

import { Check, Copy, Pencil, Plus, Trash2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { useRowNavigation } from '../conversations/useRowNavigation'
import { useDownloadFlows, useDownloadMutations } from '../downloads/api'
import { DOWNLOAD_STATUS, describeSchedule } from '../downloads/labels'
import type { DownloadFlow } from '../downloads/types'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime } from '../lib/format'
import { useFlowCatalog, useFlowMutations, useFlows } from './api'
import { catalogLabel } from './catalog'
import { FLOW_STATUS, RUN_STATUS } from './labels'
import { StatusBadge } from './StatusBadge'
import type { FlowSummary } from './types'

const MAX_NAME = 80
const input = 'h-8 min-w-0 rounded-md border border-slate-300 px-2 text-sm'
const small = 'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-600 hover:bg-slate-100'
const none = <span className="text-slate-400">—</span>

type FlowKind = 'insights' | 'descarga'
const KIND_LABELS = { insights: 'flows.kind.insights', descarga: 'flows.kind.descarga' } as const

// Un flujo de descarga nuevo descarga «hoy» de voz y chat a mano; se ajusta después en su formulario.
const NEW_DOWNLOAD = {
  interval: { type: 'relativo' as const, unit: 'hoy' as const }, channels: ['voz' as const, 'chat' as const],
  schedule: { type: 'desactivada' as const }, active: true, overwrite: false,
}

function NewFlowForm({ onCancel }: { onCancel: () => void }) {
  const i18n = useI18n()
  const { t } = i18n
  const { create } = useFlowMutations()
  const downloads = useDownloadMutations()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [kind, setKind] = useState<FlowKind>('insights')
  const [template, setTemplate] = useState('')
  // Plantillas de summary y main topic (FE013); si el catálogo no carga, se crea vacío como siempre.
  const templates = useFlowCatalog().data?.templates ?? []
  const pending = create.isPending || downloads.create.isPending

  function submit(event: FormEvent) {
    event.preventDefault()
    if (kind === 'insights') {
      create.mutate({ name: name.trim(), ...(template ? { template } : {}) }, { onSuccess: (flow) => navigate(`/flujos/${flow.id}`) })
    } else {
      downloads.create.mutate({ name: name.trim(), ...NEW_DOWNLOAD },
        { onSuccess: (flow) => navigate(`/flujos/descargas/${flow.id}`) })
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
        {t('flows.form.name')}
        <input className={`${input} w-80`} value={name} maxLength={MAX_NAME} autoFocus onChange={(e) => setName(e.target.value)} />
      </label>
      <fieldset className="flex flex-col gap-1">
        <legend className="text-xs font-medium text-slate-500">{t('flows.form.kind')}</legend>
        <div className="flex h-8 items-center gap-3 text-sm text-slate-700">
          {(Object.keys(KIND_LABELS) as FlowKind[]).map((value) => (
            <label key={value} className="inline-flex items-center gap-1.5">
              <input type="radio" name="flow-kind" checked={kind === value} onChange={() => setKind(value)} />
              {t(KIND_LABELS[value])}
            </label>
          ))}
        </div>
      </fieldset>
      {kind === 'insights' && templates.length > 0 && (
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
          {t('flows.form.template')}
          <select className={`${input} w-64`} value={template} onChange={(e) => setTemplate(e.target.value)}>
            <option value="">{t('flows.form.empty')}</option>
            {templates.map((tpl) => <option key={tpl.value} value={tpl.value}>{catalogLabel(i18n, 'templates', tpl)}</option>)}
          </select>
        </label>
      )}
      <button type="submit" disabled={!name.trim() || pending}
        className="h-8 rounded-md bg-brand-600 px-3 text-sm text-white disabled:opacity-50">{t('flows.form.create')}</button>
      <button type="button" className={`${small} h-8`} onClick={onCancel}>{t('flows.cancel')}</button>
      {(create.isError || downloads.create.isError) && (
        <p role="alert" className="w-full text-xs text-red-700">{t('flows.form.error')}</p>
      )}
    </form>
  )
}

function DeleteConfirm({ question, onConfirm, onCancel }: { question: string; onConfirm: () => void; onCancel: () => void }) {
  const { t } = useI18n()
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-600">
      {question}
      <button type="button" className={`${small} text-red-700`} onClick={onConfirm}>{t('flows.confirmDelete')}</button>
      <button type="button" className={small} onClick={onCancel}>{t('flows.no')}</button>
    </span>
  )
}

function FlowRow({ flow, canEdit }: { flow: FlowSummary; canEdit: boolean }) {
  const { t } = useI18n()
  const href = `/flujos/${flow.id}`
  const { onClick, onAuxClick, linkState } = useRowNavigation(href)
  const { duplicate, rename, remove } = useFlowMutations()
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [name, setName] = useState(flow.name)
  const status = FLOW_STATUS[flow.status]

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    rename.mutate({ id: flow.id, name: name.trim() }, { onSuccess: () => setEditing(false) })
  }

  return (
    <tr onClick={editing ? undefined : onClick} onAuxClick={onAuxClick}
      className="cursor-pointer border-b border-slate-100 align-middle hover:bg-brand-50/60">
      <td className="px-3 py-2.5">
        {editing ? (
          <form onSubmit={submit} className="flex items-center gap-1">
            <input aria-label={t('flows.newName')} className={`${input} w-64`} value={name} maxLength={MAX_NAME} autoFocus
              onChange={(e) => setName(e.target.value)} />
            <button type="submit" aria-label={t('flows.saveName')} className={small}><Check className="size-4" aria-hidden /></button>
            <button type="button" aria-label={t('flows.cancel')} className={small} onClick={() => setEditing(false)}><X className="size-4" aria-hidden /></button>
          </form>
        ) : (
          <Link to={href} state={linkState} className="font-medium text-brand-700 hover:underline">{flow.name}</Link>
        )}
      </td>
      <td className="px-3 py-2.5 text-slate-700">{t(KIND_LABELS.insights)}</td>
      <td className="px-3 py-2.5 text-slate-700">{flow.author.name}</td>
      <td className="px-3 py-2.5 whitespace-nowrap text-slate-700">{formatDateTime(flow.updated_at)}</td>
      <td className="px-3 py-2.5 whitespace-nowrap">
        {flow.last_run ? (
          <span className="inline-flex items-center gap-2 text-slate-700">
            {formatDateTime(flow.last_run.created_at)}
            <StatusBadge label={t(RUN_STATUS[flow.last_run.status].label)} className={RUN_STATUS[flow.last_run.status].className} />
          </span>
        ) : <span className="text-slate-400">{t('flows.noRuns')}</span>}
      </td>
      <td className="px-3 py-2.5">{none}</td>
      <td className="px-3 py-2.5"><StatusBadge label={t(status.label)} className={status.className} /></td>
      {canEdit && (
        <td className="px-3 py-2.5">
          {confirming ? (
            <DeleteConfirm question={t('flows.deleteFlow')} onConfirm={() => remove.mutate(flow.id)}
              onCancel={() => setConfirming(false)} />
          ) : (
            <span className="inline-flex gap-1">
              <button type="button" className={small} disabled={duplicate.isPending} onClick={() => duplicate.mutate(flow.id)}>
                <Copy className="size-3" aria-hidden />{t('flows.duplicate')}
              </button>
              <button type="button" className={small} onClick={() => { setName(flow.name); setEditing(true) }}>
                <Pencil className="size-3" aria-hidden />{t('flows.rename')}
              </button>
              <button type="button" className={small} onClick={() => setConfirming(true)}>
                <Trash2 className="size-3" aria-hidden />{t('flows.delete')}
              </button>
            </span>
          )}
          {(duplicate.isError || rename.isError || remove.isError) && (
            <p role="alert" className="mt-1 text-xs text-red-700">{t('flows.actionError')}</p>
          )}
        </td>
      )}
    </tr>
  )
}

function DownloadRow({ flow, canEdit }: { flow: DownloadFlow; canEdit: boolean }) {
  const { t } = useI18n()
  const href = `/flujos/descargas/${flow.id}`
  const { onClick, onAuxClick, linkState } = useRowNavigation(href)
  const { remove } = useDownloadMutations()
  const [confirming, setConfirming] = useState(false)
  const state = flow.active
    ? { label: describeSchedule(t, flow.schedule), className: 'bg-brand-50 text-brand-700' }
    : { label: t('flows.inactive'), className: 'bg-slate-100 text-slate-600' }

  return (
    <tr onClick={onClick} onAuxClick={onAuxClick}
      className="cursor-pointer border-b border-slate-100 align-middle hover:bg-brand-50/60">
      <td className="px-3 py-2.5">
        <Link to={href} state={linkState} className="font-medium text-brand-700 hover:underline">{flow.name}</Link>
      </td>
      <td className="px-3 py-2.5 text-slate-700">{t(KIND_LABELS.descarga)}</td>
      <td className="px-3 py-2.5 text-slate-700">{flow.author.name}</td>
      <td className="px-3 py-2.5 whitespace-nowrap text-slate-700">{formatDateTime(flow.updated_at)}</td>
      <td className="px-3 py-2.5 whitespace-nowrap">
        {flow.last_run ? (
          <span className="inline-flex items-center gap-2 text-slate-700">
            {formatDateTime(flow.last_run.created_at)}
            <StatusBadge label={t(DOWNLOAD_STATUS[flow.last_run.status].label)} className={DOWNLOAD_STATUS[flow.last_run.status].className} />
          </span>
        ) : <span className="text-slate-400">{t('flows.noRuns')}</span>}
      </td>
      <td className="px-3 py-2.5 whitespace-nowrap text-slate-700">
        {flow.next_run_at ? formatDateTime(flow.next_run_at) : none}
      </td>
      <td className="px-3 py-2.5"><StatusBadge {...state} /></td>
      {canEdit && (
        <td className="px-3 py-2.5">
          {confirming ? (
            <DeleteConfirm question={t('flows.deleteDownload')} onConfirm={() => remove.mutate(flow.id)}
              onCancel={() => setConfirming(false)} />
          ) : (
            <button type="button" className={small} onClick={() => setConfirming(true)}>
              <Trash2 className="size-3" aria-hidden />{t('flows.delete')}
            </button>
          )}
          {remove.isError && (
            <p role="alert" className="mt-1 text-xs text-red-700">
              {remove.error instanceof ApiError && remove.error.status === 409
                ? t('flows.downloadRunning') : t('flows.actionError')}
            </p>
          )}
        </td>
      )}
    </tr>
  )
}

type Row = { kind: 'insights'; flow: FlowSummary } | { kind: 'descarga'; flow: DownloadFlow }

export function FlowsPage() {
  const { t } = useI18n()
  const { can } = useAuth()
  const canEdit = can('flows:edit')
  const { data, isError, isPending } = useFlows()
  const downloads = useDownloadFlows()
  const [creating, setCreating] = useState(false)
  const rows: Row[] = [
    ...(data?.items ?? []).map((flow) => ({ kind: 'insights' as const, flow })),
    ...(downloads.data?.items ?? []).map((flow) => ({ kind: 'descarga' as const, flow })),
  ].sort((a, b) => b.flow.updated_at.localeCompare(a.flow.updated_at))
  const newButton = canEdit && !creating && (
    <button type="button" onClick={() => setCreating(true)}
      className="inline-flex items-center gap-1.5 rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700">
      <Plus className="size-4" aria-hidden />{t('flows.new')}
    </button>
  )

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{t('flows.title')}</h1>
          <p className="text-sm text-slate-500">
            {t('flows.subtitle')}
            {!canEdit && ` ${t('flows.readOnly')}`}
          </p>
        </div>
        {data && rows.length > 0 && newButton}
      </header>
      {creating && <NewFlowForm onCancel={() => setCreating(false)} />}
      {isPending && <p role="status" className="text-sm text-slate-500">{t('flows.loading')}</p>}
      {isError && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{t('flows.loadError')}</p>}
      {downloads.isError && (
        <p role="alert" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {downloads.error instanceof ApiError && downloads.error.status === 503
            ? t('flows.downloadsUnavailable')
            : t('flows.downloadsError')}
        </p>
      )}
      {data && rows.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-600">
          <p>{t('flows.empty')}</p>
          {newButton}
        </div>
      )}
      {data && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {(['flows.col.name', 'flows.col.type', 'flows.col.author', 'flows.col.modified', 'flows.col.lastRun', 'flows.col.nextRun', 'flows.col.status',
                  ...(canEdit ? ['flows.col.actions' as const] : [])] as const).map((label) => (
                  <th key={label} scope="col" className="px-3 py-2 font-medium">{t(label)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => row.kind === 'insights'
                ? <FlowRow key={row.flow.id} flow={row.flow} canEdit={canEdit} />
                : <DownloadRow key={row.flow.id} flow={row.flow} canEdit={canEdit} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

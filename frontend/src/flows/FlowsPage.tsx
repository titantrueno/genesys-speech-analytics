import { Check, Copy, Pencil, Plus, Trash2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useAuth } from '../auth/useAuth'
import { useRowNavigation } from '../conversations/useRowNavigation'
import { formatDateTime } from '../lib/format'
import { useFlowMutations, useFlows } from './api'
import { FLOW_STATUS, RUN_STATUS } from './labels'
import { StatusBadge } from './StatusBadge'
import type { FlowSummary } from './types'

const MAX_NAME = 80
const input = 'h-8 min-w-0 rounded-md border border-slate-300 px-2 text-sm'
const small = 'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-600 hover:bg-slate-100'

function NewFlowForm({ onCancel }: { onCancel: () => void }) {
  const { create } = useFlowMutations()
  const navigate = useNavigate()
  const [name, setName] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate(name.trim(), { onSuccess: (flow) => navigate(`/flujos/${flow.id}`) })
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2 rounded-xl border border-slate-200 bg-white p-4">
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
        Nombre del flujo
        <input className={`${input} w-80`} value={name} maxLength={MAX_NAME} autoFocus onChange={(e) => setName(e.target.value)} />
      </label>
      <button type="submit" disabled={!name.trim() || create.isPending}
        className="h-8 rounded-md bg-brand-600 px-3 text-sm text-white disabled:opacity-50">Crear</button>
      <button type="button" className={`${small} h-8`} onClick={onCancel}>Cancelar</button>
      {create.isError && <p role="alert" className="w-full text-xs text-red-700">No se ha podido crear el flujo.</p>}
    </form>
  )
}

function FlowRow({ flow, canEdit }: { flow: FlowSummary; canEdit: boolean }) {
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
            <input aria-label="Nuevo nombre" className={`${input} w-64`} value={name} maxLength={MAX_NAME} autoFocus
              onChange={(e) => setName(e.target.value)} />
            <button type="submit" aria-label="Guardar nombre" className={small}><Check className="size-4" aria-hidden /></button>
            <button type="button" aria-label="Cancelar" className={small} onClick={() => setEditing(false)}><X className="size-4" aria-hidden /></button>
          </form>
        ) : (
          <Link to={href} state={linkState} className="font-medium text-brand-700 hover:underline">{flow.name}</Link>
        )}
      </td>
      <td className="px-3 py-2.5 text-slate-700">{flow.author.name}</td>
      <td className="px-3 py-2.5 whitespace-nowrap text-slate-700">{formatDateTime(flow.updated_at)}</td>
      <td className="px-3 py-2.5 whitespace-nowrap">
        {flow.last_run ? (
          <span className="inline-flex items-center gap-2 text-slate-700">
            {formatDateTime(flow.last_run.created_at)}
            <StatusBadge {...RUN_STATUS[flow.last_run.status]} />
          </span>
        ) : <span className="text-slate-400">Sin ejecuciones</span>}
      </td>
      <td className="px-3 py-2.5"><StatusBadge {...status} /></td>
      {canEdit && (
        <td className="px-3 py-2.5">
          {confirming ? (
            <span className="inline-flex items-center gap-1 text-xs text-slate-600">
              ¿Borrar el flujo y su historial?
              <button type="button" className={`${small} text-red-700`} onClick={() => remove.mutate(flow.id)}>Confirmar borrado</button>
              <button type="button" className={small} onClick={() => setConfirming(false)}>No</button>
            </span>
          ) : (
            <span className="inline-flex gap-1">
              <button type="button" className={small} disabled={duplicate.isPending} onClick={() => duplicate.mutate(flow.id)}>
                <Copy className="size-3" aria-hidden />Duplicar
              </button>
              <button type="button" className={small} onClick={() => { setName(flow.name); setEditing(true) }}>
                <Pencil className="size-3" aria-hidden />Renombrar
              </button>
              <button type="button" className={small} onClick={() => setConfirming(true)}>
                <Trash2 className="size-3" aria-hidden />Borrar
              </button>
            </span>
          )}
          {(duplicate.isError || rename.isError || remove.isError) && (
            <p role="alert" className="mt-1 text-xs text-red-700">No se ha podido completar la acción.</p>
          )}
        </td>
      )}
    </tr>
  )
}

export function FlowsPage() {
  const { can } = useAuth()
  const canEdit = can('flows:edit')
  const { data, isError, isPending } = useFlows()
  const [creating, setCreating] = useState(false)
  const newButton = canEdit && !creating && (
    <button type="button" onClick={() => setCreating(true)}
      className="inline-flex items-center gap-1.5 rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700">
      <Plus className="size-4" aria-hidden />Nuevo flujo
    </button>
  )

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Flujos de insights</h1>
          <p className="text-sm text-slate-500">
            Diseña flujos que toman una muestra de conversaciones, les aplican un prompt y producen insights.
            {!canEdit && ' Tienes acceso de solo lectura.'}
          </p>
        </div>
        {data && data.items.length > 0 && newButton}
      </header>
      {creating && <NewFlowForm onCancel={() => setCreating(false)} />}
      {isPending && <p role="status" className="text-sm text-slate-500">Cargando flujos…</p>}
      {isError && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">No se han podido cargar los flujos.</p>}
      {data && data.items.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-600">
          <p>Todavía no hay flujos.</p>
          {newButton}
        </div>
      )}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {['Nombre', 'Autor', 'Última modificación', 'Última ejecución', 'Estado', ...(canEdit ? ['Acciones'] : [])].map((label) => (
                  <th key={label} scope="col" className="px-3 py-2 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((flow) => <FlowRow key={flow.id} flow={flow} canEdit={canEdit} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

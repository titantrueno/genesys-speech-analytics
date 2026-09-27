import { useMemo } from 'react'
import { ApiError } from '../api/client'
import { LoadingScreen } from '../layout/LoadingScreen'
import { useQuerySchema } from './api'
import { GroupEditor, type GroupHandlers } from './GroupEditor'
import { useDebouncedValue, useQueryRun } from './hooks'
import {
  addCondition, addGroup, newCondition, pathFromApi, pruneIncomplete, queryToText, removeNode, replaceCondition, setGroupOp,
  type ExplorerQuery, type QuerySchema,
} from './queryModel'
import { useExplorerState } from './useExplorerState'

const inputClass = 'h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700'

function validationErrors(error: unknown, toOriginal: Map<string, number[]>): Map<string, string> {
  const errors = new Map<string, string>()
  if (!(error instanceof ApiError) || error.status !== 422 || !Array.isArray(error.detail)) return errors
  for (const item of error.detail as Array<{ path: string; message: string }>) {
    const sentPath = pathFromApi(item.path)
    if (sentPath === null) continue
    const original = toOriginal.get(sentPath.join('.')) ?? sentPath
    errors.set(original.join('.'), item.message)
  }
  return errors
}

function Explorer({ schema }: { schema: QuerySchema }) {
  const { query, invalidLink, setQuery, page, sort, order } = useExplorerState()
  const pruned = useMemo(() => pruneIncomplete(query, schema), [query, schema])
  const debounced = useDebouncedValue(pruned.query, 300)
  const run = useQueryRun(debounced, { page, sort, order })
  const errors = useMemo(() => validationErrors(run.error, pruned.toOriginal), [run.error, pruned.toOriginal])

  const from = query.from ?? schema.default_period.from
  const to = query.to ?? schema.default_period.to
  const edit = (next: ExplorerQuery) => setQuery(next)
  const handlers: GroupHandlers = {
    addCondition: (path) => edit(addCondition(query, path, newCondition(schema.fields[0]))),
    addGroup: (path) => edit(addGroup(query, path, 'and')),
    setOp: (path, op) => edit(setGroupOp(query, path, op)),
    update: (path, cond) => edit(replaceCondition(query, path, cond)),
    remove: (path) => edit(removeNode(query, path)),
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Explorador</h1>
        <p className="text-sm text-slate-500">Consultas asistidas en tiempo real sobre las conversaciones de un intervalo.</p>
      </header>
      {invalidLink && (
        <p role="alert" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          El enlace de la consulta no es válido; se ha cargado una consulta vacía.
        </p>
      )}
      <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
            Desde
            <input type="date" className={inputClass} value={from} max={to}
              onChange={(e) => e.target.value && edit({ ...query, from: e.target.value, to })} />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
            Hasta
            <input type="date" className={inputClass} value={to} min={from}
              onChange={(e) => e.target.value && edit({ ...query, from, to: e.target.value })} />
          </label>
        </div>
        <GroupEditor group={query.root} path={[]} schema={schema} from={from} to={to} errors={errors} handlers={handlers} />
        <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
          <span className="mr-1 font-medium text-slate-900">Consulta:</span>
          <span>{queryToText(query, schema)}</span>
        </p>
      </div>
      {run.data && <p className="text-sm text-slate-600">{run.data.total} conversaciones</p>}
    </div>
  )
}

export function ExplorerPage() {
  const { data: schema, isError } = useQuerySchema()
  if (isError) return <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">No se ha podido cargar el explorador.</p>
  if (!schema) return <LoadingScreen />
  return <Explorer schema={schema} />
}

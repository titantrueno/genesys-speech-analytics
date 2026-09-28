import { useMemo } from 'react'
import { useQuerySchema } from '../../explorer/api'
import { GroupEditor, type GroupHandlers } from '../../explorer/GroupEditor'
import { useDebouncedValue } from '../../explorer/hooks'
import {
  addCondition, addGroup, newCondition, pruneIncomplete, queryToText, removeNode, replaceCondition, setGroupOp,
  type ExplorerQuery, type QuerySchema,
} from '../../explorer/queryModel'
import { formatInteger } from '../../lib/format'
import { useEstimate } from '../api'
import { useCatalog } from '../catalog'
import type { SamplingConfig } from '../types'
import { control, Field, Section, Select } from './controls'

const EMPTY_QUERY: ExplorerQuery = { root: { op: 'and', conditions: [] } }

function Estimate({ query, size, schema }: { query: ExplorerQuery; size: number | undefined; schema: QuerySchema }) {
  // Solo se envían las condiciones completas y se espera a que se deje de escribir.
  const pruned = useMemo(() => pruneIncomplete(query, schema).query, [query, schema])
  const debounced = useDebouncedValue({ query: pruned, size }, 400)
  const estimate = useEstimate(debounced.query, debounced.size)
  if (estimate.isError) return <p role="alert" className="text-xs text-red-700">No se ha podido estimar: revisa los filtros.</p>
  if (!estimate.data) return <p role="status" className="text-xs text-slate-500">Estimando conversaciones disponibles…</p>
  const { available, sample_size: sample } = estimate.data
  return (
    <p role="status" className={`rounded-md px-2.5 py-2 text-xs ${available ? 'bg-brand-50 text-brand-900' : 'bg-amber-50 text-amber-800'} ${estimate.isFetching ? 'opacity-60' : ''}`}>
      <span className="font-semibold">{formatInteger(available)}</span> {available === 1 ? 'conversación disponible' : 'conversaciones disponibles'}
      {sample !== null && available > 0 && <> · muestra de <span className="font-semibold">{formatInteger(sample)}</span></>}
      {available === 0 && ' · la muestra estaría vacía'}
    </p>
  )
}

export function SamplingPanel({ config, onChange }: { config: SamplingConfig; onChange: (config: SamplingConfig) => void }) {
  const catalog = useCatalog()
  const { data: schema, isError } = useQuerySchema()
  const query = config.query ?? EMPTY_QUERY
  const setQuery = (next: ExplorerQuery) => onChange({ ...config, query: next })

  if (isError) return <p role="alert" className="text-sm text-red-700">No se ha podido cargar el constructor de filtros.</p>
  if (!schema) return <p role="status" className="text-sm text-slate-500">Cargando filtros…</p>

  const from = query.from ?? schema.default_period.from
  const to = query.to ?? schema.default_period.to
  const handlers: GroupHandlers = {
    addCondition: (path) => setQuery(addCondition(query, path, newCondition(schema.fields[0]))),
    addGroup: (path) => setQuery(addGroup(query, path, 'and')),
    setOp: (path, op) => setQuery(setGroupOp(query, path, op)),
    update: (path, cond) => setQuery(replaceCondition(query, path, cond)),
    remove: (path) => setQuery(removeNode(query, path)),
  }

  return (
    <div className="space-y-3">
      <Section title="Intervalo y filtros">
        <div className="grid grid-cols-2 gap-2">
          <Field label="Desde">
            <input type="date" className={control} value={from} max={to}
              onChange={(e) => e.target.value && setQuery({ ...query, from: e.target.value, to })} />
          </Field>
          <Field label="Hasta">
            <input type="date" className={control} value={to} min={from}
              onChange={(e) => e.target.value && setQuery({ ...query, from, to: e.target.value })} />
          </Field>
        </div>
        {!query.from && <p className="text-xs text-slate-500">Periodo por defecto: los 30 días anteriores a la fecha de referencia.</p>}
        <GroupEditor group={query.root} path={[]} schema={schema} from={from} to={to} errors={new Map()} handlers={handlers} />
        <p className="rounded-md bg-slate-50 px-2.5 py-2 text-xs text-slate-700">
          <span className="font-medium text-slate-900">Filtros:</span> {queryToText(query, schema)}
        </p>
      </Section>
      <Section title="Muestra">
        <Select label="Método" value={config.method} options={catalog.sampling_methods}
          onChange={(method) => onChange({
            ...config, method,
            stratify_by: method === 'estratificado' ? config.stratify_by ?? 'canal' : undefined,
            order_by: method === 'primeros_n' ? config.order_by ?? 'fecha' : undefined,
            order: method === 'primeros_n' ? config.order ?? 'desc' : undefined,
          })} />
        {config.method === 'estratificado' && (
          <Select label="Estratificar por" value={config.stratify_by} options={catalog.strata}
            onChange={(stratify_by) => onChange({ ...config, stratify_by })} />
        )}
        {config.method === 'primeros_n' && (
          <div className="grid grid-cols-2 gap-2">
            <Select label="Ordenar por" value={config.order_by} options={catalog.order_keys}
              onChange={(order_by) => onChange({ ...config, order_by })} />
            <Select label="Sentido" value={config.order} options={catalog.orders} onChange={(order) => onChange({ ...config, order })} />
          </div>
        )}
        <Field label="Tamaño de la muestra" hint={`Entre 1 y ${formatInteger(catalog.limits.max_sample_size)} conversaciones.`}>
          <input type="number" className={control} min={1} max={catalog.limits.max_sample_size} step={1}
            value={config.size ?? ''}
            onChange={(e) => {
              const size = e.target.valueAsNumber
              onChange({ ...config, size: Number.isInteger(size) ? Math.min(Math.max(size, 1), catalog.limits.max_sample_size) : undefined })
            }} />
        </Field>
        <Estimate query={query} size={config.size} schema={schema} />
      </Section>
    </div>
  )
}

import { useMemo } from 'react'
import { useQuerySchema } from '../../explorer/api'
import { GroupEditor, type GroupHandlers } from '../../explorer/GroupEditor'
import { useDebouncedValue } from '../../explorer/hooks'
import {
  addCondition, addGroup, newCondition, pruneIncomplete, queryToText, removeNode, replaceCondition, setGroupOp,
  type ExplorerQuery, type QuerySchema,
} from '../../explorer/queryModel'
import { useI18n } from '../../i18n/useI18n'
import { formatInteger } from '../../lib/format'
import { useEstimate } from '../api'
import { useCatalog } from '../catalog'
import type { SamplingConfig } from '../types'
import { control, Field, Section, Select } from './controls'

const EMPTY_QUERY: ExplorerQuery = { root: { op: 'and', conditions: [] } }

function Estimate({ query, size, schema, afterDownload }: {
  query: ExplorerQuery; size: number | 'all' | undefined; schema: QuerySchema; afterDownload: boolean
}) {
  const { t } = useI18n()
  // Solo se envían las condiciones completas y se espera a que se deje de escribir.
  const pruned = useMemo(() => pruneIncomplete(query, schema).query, [query, schema])
  const debounced = useDebouncedValue({ query: pruned, size }, 400)
  const estimate = useEstimate(debounced.query, debounced.size, afterDownload)
  if (estimate.isError) return <p role="alert" className="text-xs text-red-700">{t('flows.sampling.estimateError')}</p>
  if (!estimate.data) return <p role="status" className="text-xs text-slate-500">{t('flows.sampling.estimating')}</p>
  if (estimate.data.depends_on_download || estimate.data.available === null) {
    return <p role="status" className="rounded-md bg-slate-50 px-2.5 py-2 text-xs text-slate-700">{t('flows.sampling.dependsOnDownload')}</p>
  }
  const { available, sample_size: sample } = estimate.data
  return (
    <p role="status" className={`rounded-md px-2.5 py-2 text-xs ${available ? 'bg-brand-50 text-brand-900' : 'bg-amber-50 text-amber-800'} ${estimate.isFetching ? 'opacity-60' : ''}`}>
      <span className="font-semibold">{formatInteger(available)}</span> {t('flows.sampling.available', { count: available })}
      {sample !== null && available > 0 && <>{t('flows.sampling.sampleOf', { n: '' })}<span className="font-semibold">{formatInteger(sample)}</span></>}
      {available === 0 && t('flows.sampling.emptySample')}
    </p>
  )
}

export function SamplingPanel({ config, onChange, afterDownload = false }: {
  config: SamplingConfig; onChange: (config: SamplingConfig) => void
  /** Detrás de una caja «Genesys download» (FE017): sin fechas, las conversaciones las da la descarga. */
  afterDownload?: boolean
}) {
  const catalog = useCatalog()
  const i18n = useI18n()
  const { t } = i18n
  const { data: schema, isError } = useQuerySchema()
  const query = config.query ?? EMPTY_QUERY
  const setQuery = (next: ExplorerQuery) => onChange({ ...config, query: next })

  if (isError) return <p role="alert" className="text-sm text-red-700">{t('flows.sampling.builderError')}</p>
  if (!schema) return <p role="status" className="text-sm text-slate-500">{t('flows.sampling.loadingFilters')}</p>

  const everything = config.size === 'all'
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
      <Section title={afterDownload ? t('flows.sampling.filtersOnly') : t('flows.sampling.rangeAndFilters')}>
        {afterDownload ? (
          <p className="rounded-md bg-amber-50 px-2.5 py-2 text-xs text-amber-900">{t('flows.sampling.afterDownload')}</p>
        ) : (
        <>
        <div className="grid grid-cols-2 gap-2">
          <Field label={t('dash.from')}>
            <input type="date" className={control} value={from} max={to}
              onChange={(e) => e.target.value && setQuery({ ...query, from: e.target.value, to })} />
          </Field>
          <Field label={t('dash.to')}>
            <input type="date" className={control} value={to} min={from}
              onChange={(e) => e.target.value && setQuery({ ...query, from, to: e.target.value })} />
          </Field>
        </div>
        {!query.from && <p className="text-xs text-slate-500">{t('flows.sampling.defaultPeriod')}</p>}
        </>
        )}
        <GroupEditor group={query.root} path={[]} schema={schema} from={from} to={to} errors={new Map()} handlers={handlers} />
        <p className="rounded-md bg-slate-50 px-2.5 py-2 text-xs text-slate-700">
          <span className="font-medium text-slate-900">{t('flows.sampling.filters')}</span>{' '}
          {afterDownload && query.root.conditions.length === 0 ? t('flows.sampling.allDownloaded') : queryToText(query, schema, i18n)}
        </p>
      </Section>
      <Section title={t('flows.sampling.sample')}>
        <div>
          <label className="inline-flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={everything} aria-describedby="sampling-all-hint"
              onChange={(e) => onChange(e.target.checked
                ? { query: config.query, size: 'all' }
                : { query: config.query, method: 'aleatorio', size: 100 })} />
            {t('flows.sampling.all')}
          </label>
          <p id="sampling-all-hint" className="ml-6 text-xs text-slate-500">{t('flows.sampling.allHint')}</p>
        </div>
        {!everything && (
        <>
        <Select label={t('flows.sampling.method')} group="sampling_methods" value={config.method} options={catalog.sampling_methods}
          onChange={(method) => onChange({
            ...config, method,
            stratify_by: method === 'estratificado' ? config.stratify_by ?? 'canal' : undefined,
            order_by: method === 'primeros_n' ? config.order_by ?? 'fecha' : undefined,
            order: method === 'primeros_n' ? config.order ?? 'desc' : undefined,
          })} />
        {config.method === 'estratificado' && (
          <Select label={t('flows.sampling.stratify')} group="strata" value={config.stratify_by} options={catalog.strata}
            onChange={(stratify_by) => onChange({ ...config, stratify_by })} />
        )}
        {config.method === 'primeros_n' && (
          <div className="grid grid-cols-2 gap-2">
            <Select label={t('flows.sampling.orderBy')} group="order_keys" value={config.order_by} options={catalog.order_keys}
              onChange={(order_by) => onChange({ ...config, order_by })} />
            <Select label={t('flows.sampling.direction')} group="orders" value={config.order} options={catalog.orders} onChange={(order) => onChange({ ...config, order })} />
          </div>
        )}
        <Field label={t('flows.sampling.size')} hint={t('flows.sampling.sizeHint', { max: formatInteger(catalog.limits.max_sample_size) })}>
          <input type="number" className={control} min={1} max={catalog.limits.max_sample_size} step={1}
            value={config.size ?? ''}
            onChange={(e) => {
              const size = e.target.valueAsNumber
              onChange({ ...config, size: Number.isInteger(size) ? Math.min(Math.max(size, 1), catalog.limits.max_sample_size) : undefined })
            }} />
        </Field>
        </>
        )}
        <Estimate query={query} size={config.size} schema={schema} afterDownload={afterDownload} />
      </Section>
    </div>
  )
}

import { useMemo } from 'react'
import type { KpiSummary } from '../api/metrics'
import { ConversationTable, Pagination } from '../conversations/ConversationTable'
import { nextSort, type SortState } from '../conversations/sorting'
import { LoadError } from '../dashboards/ChartCard'
import { KpiTile } from '../dashboards/KpiTile'
import { useI18n } from '../i18n/useI18n'
import { formatInteger } from '../lib/format'
import { ApiError } from '../api/client'
import { LoadingScreen } from '../layout/LoadingScreen'
import { useQuerySchema } from './api'
import { GroupEditor, type GroupHandlers } from './GroupEditor'
import { NaturalLanguage } from './NaturalLanguage'
import { SavedQueries } from './SavedQueries'
import { useDebouncedValue, useQueryRun, type QueryRunResponse } from './hooks'
import {
  addCondition, addGroup, newCondition, pathFromApi, pruneIncomplete, queryToText, removeNode, replaceCondition, setGroupOp,
  type ExplorerQuery, type QuerySchema,
} from './queryModel'
import { useExplorerState } from './useExplorerState'

const inputClass = 'h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700'

interface ValidationErrors { byPath: Map<string, string>; general: string[] }

function validationErrors(error: unknown, toOriginal: Map<string, number[]>): ValidationErrors {
  const result: ValidationErrors = { byPath: new Map(), general: [] }
  if (!(error instanceof ApiError) || error.status !== 422 || !Array.isArray(error.detail)) return result
  for (const item of error.detail as Array<{ path: string; message: string }>) {
    const sentPath = pathFromApi(item.path)
    if (sentPath === null || sentPath.length === 0) {
      result.general.push(item.message)
      continue
    }
    const original = toOriginal.get(sentPath.join('.')) ?? sentPath
    result.byPath.set(original.join('.'), item.message)
  }
  return result
}

function Explorer({ schema }: { schema: QuerySchema }) {
  const i18n = useI18n()
  const { t } = i18n
  const { query, invalidLink, setQuery, page, sort, order, setListing } = useExplorerState()
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
        <h1 className="text-2xl font-semibold text-slate-900">{t('exp.title')}</h1>
        <p className="text-sm text-slate-500">{t('exp.subtitle')}</p>
      </header>
      {invalidLink && (
        <p role="alert" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t('exp.invalidLink')}
        </p>
      )}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <NaturalLanguage onQuery={edit} />
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
            {t('dash.from')}
            <input type="date" className={inputClass} value={from} max={to}
              onChange={(e) => e.target.value && edit({ ...query, from: e.target.value, to })} />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
            {t('dash.to')}
            <input type="date" className={inputClass} value={to} min={from}
              onChange={(e) => e.target.value && edit({ ...query, from, to: e.target.value })} />
          </label>
        </div>
        <GroupEditor group={query.root} path={[]} schema={schema} from={from} to={to} errors={errors.byPath} handlers={handlers} />
        <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
          <span className="mr-1 font-medium text-slate-900">{t('exp.query')}</span>
          <span>{queryToText(query, schema, i18n)}</span>
        </p>
      </div>
        <SavedQueries current={pruned.query} onLoad={edit} />
      </div>
      <Results run={run} validation={errors} sort={sort} order={order} page={page}
        onSort={(key) => setListing(nextSort({ sort, order }, key))}
        onPage={(next) => setListing({ page: next })}
        onRemoveLast={query.root.conditions.length > 0 ? () => edit(removeNode(query, [query.root.conditions.length - 1])) : undefined} />
    </div>
  )
}

const RESULT_KPIS = ['volume', 'aht_s', 'resolution_rate', 'escalation_rate', 'csat_avg', 'sentiment_avg']

function Results({ run, validation, sort, order, page, onSort, onPage, onRemoveLast }: {
  run: ReturnType<typeof useQueryRun>
  validation: ValidationErrors
  sort: SortState['sort']
  order: SortState['order']
  page: number
  onSort: (key: SortState['sort']) => void
  onPage: (page: number) => void
  onRemoveLast?: () => void
}) {
  const { t } = useI18n()
  const data: QueryRunResponse | undefined = run.data
  const kpis = (data?.kpis ?? []).filter((k) => RESULT_KPIS.includes(k.code))
    .map((k): KpiSummary => ({ ...k, previous: null, delta: null, delta_pct: null }))
  return (
    <section aria-label={t('exp.results')} className="space-y-3">
      {validation.byPath.size > 0 && <p className="text-sm text-red-700">{t('exp.reviewConditions')}</p>}
      {validation.general.map((message) => <p key={message} role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>)}
      {run.isError && validation.byPath.size === 0 && validation.general.length === 0 && (
        <LoadError message={t('exp.resultsError')} />
      )}
      {!data && run.isPending && <p role="status" className="text-sm text-slate-500">{t('exp.loadingResults')}</p>}
      {data && (
        <>
          <p className="text-sm font-medium text-slate-700">
            {t('conv.count', { count: data.total, n: formatInteger(data.total) })}
          </p>
          {data.total > 0 && (
            <div className={`grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6 ${run.isFetching ? 'opacity-60' : ''}`}>
              {kpis.map((kpi) => <KpiTile key={kpi.code} kpi={kpi} comparison={false} />)}
            </div>
          )}
          <ConversationTable items={data.items} sort={sort} order={order} onSort={onSort} dimmed={run.isFetching}
            empty={
              <div className="space-y-2 py-10 text-center text-sm text-slate-500">
                <p>{t('exp.noMatch')}</p>
                {onRemoveLast && (
                  <button type="button" onClick={onRemoveLast} className="rounded-md border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-50">
                    {t('exp.removeLast')}
                  </button>
                )}
              </div>
            } />
          <Pagination page={page} pages={data.pages} onPage={onPage} />
        </>
      )}
    </section>
  )
}

export function ExplorerPage() {
  const { t } = useI18n()
  const { data: schema, isError } = useQuerySchema()
  if (isError) return <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{t('exp.loadError')}</p>
  if (!schema) return <LoadingScreen />
  return <Explorer schema={schema} />
}

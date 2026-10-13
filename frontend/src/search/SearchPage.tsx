import { Search } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { ApiError } from '../api/client'
import { useCatalog } from '../api/metrics'
import { MultiSelect } from '../components/MultiSelect'
import { LoadError } from '../dashboards/ChartCard'
import { useI18n } from '../i18n/useI18n'
import { parseIsoDate, presetRange, DEFAULT_PRESET } from '../dashboards/useDashboardFilters'
import { useDebouncedValue } from '../explorer/hooks'
import { formatInteger, formatPercentWhole, shortId } from '../lib/format'
import { useSemanticSearch, useSimilar, type SearchResponse } from './api'
import { ResultCard } from './ResultCard'
import { useSearchState } from './useSearchState'

const inputClass = 'h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700'
const labelClass = 'flex flex-col gap-1 text-xs font-medium text-slate-500'

const percent = (score: number) => Math.round(score * 100)

function ThresholdSlider({ value, best, onChange }: { value: number; best?: number | null; onChange: (value: number) => void }) {
  const { t } = useI18n()
  const external = Math.round(value * 100)
  const [draft, setDraft] = useState(external)
  const [previous, setPrevious] = useState(external)
  if (external !== previous) {
    setPrevious(external)
    setDraft(external)
  }
  const debounced = useDebouncedValue(draft, 300)
  useEffect(() => {
    // Solo cuando se estabiliza el borrador: si dependiera de `external`, un cambio de la URL (volver atrás)
    // reenviaría el valor anterior durante el debounce.
    if (debounced !== external) onChange(debounced / 100)
  }, [debounced]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <label className={`relative ${labelClass}`}>
      {t('search.minScore')}
      <span className="flex h-9 items-center gap-2">
        <span className="relative flex w-32 items-center">
          <input type="range" min={0} max={100} step={5} value={draft} aria-label={t('search.minScore')}
            onChange={(e) => setDraft(Number(e.target.value))} className="w-full accent-brand-600" />
          {best != null && (
            <span data-testid="max-score-mark" aria-hidden title={t('search.bestMark')}
              className="pointer-events-none absolute -top-1 h-5 w-0.5 -translate-x-1/2 rounded bg-amber-500"
              style={{ left: `${percent(best)}%` }} />
          )}
        </span>
        <span className="w-10 text-sm text-slate-700 tabular-nums">{formatPercentWhole(draft)}</span>
      </span>
      {best != null && (
        <span className="absolute top-full mt-0.5 whitespace-nowrap text-[11px] font-normal text-slate-500">
          {t('search.best', { value: formatPercentWhole(percent(best)) })}
        </span>
      )}
    </label>
  )
}

export function SearchPage() {
  const { t } = useI18n()
  const { search, similar, raw, update } = useSearchState()
  const { data: catalog } = useCatalog()
  const run = useSemanticSearch(search)
  const [draft, setDraft] = useState(raw.q)
  const [previousQ, setPreviousQ] = useState(raw.q)
  if (raw.q !== previousQ) {
    setPreviousQ(raw.q)
    setDraft(raw.q)
  }

  const fallback = catalog ? presetRange(DEFAULT_PRESET, parseIsoDate(catalog.reference_date), catalog.origin === 'real') : undefined
  const from = raw.from ?? run.data?.period.from ?? fallback?.from ?? ''
  const to = raw.to ?? run.data?.period.to ?? fallback?.to ?? ''

  const setThreshold = (score: number) => update({ min_score: score > 0 ? String(score) : undefined })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (draft.trim()) update({ q: draft.trim() })
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">{t('search.title')}</h1>
        <p className="text-sm text-slate-500">{t('search.subtitle')}</p>
      </header>
      <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <form role="search" aria-label={t('search.formAria')} onSubmit={onSubmit} className="flex gap-2">
          <input type="search" aria-label={t('search.queryAria')} maxLength={500} value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder={t('search.placeholder')}
            className="h-10 min-w-0 flex-1 rounded-md border border-slate-300 px-3 text-sm text-slate-800" />
          <button type="submit" className="inline-flex items-center gap-1.5 rounded-md bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700">
            <Search className="size-4" aria-hidden />{t('search.submit')}
          </button>
        </form>
        <div className="flex flex-wrap items-end gap-x-3 gap-y-5 pb-3">
          <label className={labelClass}>
            {t('dash.from')}
            <input type="date" className={inputClass} value={from} max={to || undefined}
              onChange={(e) => e.target.value && update({ from: e.target.value, to: to || undefined })} />
          </label>
          <label className={labelClass}>
            {t('dash.to')}
            <input type="date" className={inputClass} value={to} min={from || undefined}
              onChange={(e) => e.target.value && update({ from: from || undefined, to: e.target.value })} />
          </label>
          <label className={labelClass}>
            {t('dash.channel')}
            <select className={inputClass} value={raw.channel} onChange={(e) => update({ channel: e.target.value || undefined })}>
              <option value="">{t('dash.all')}</option>
              <option value="voz">{t('domain.channel.voz')}</option>
              <option value="chat">{t('domain.channel.chat')}</option>
            </select>
          </label>
          <MultiSelect label={t('dash.queue')} allLabel={t('dash.allFeminine')} selected={raw.queue} onChange={(queue) => update({ queue })}
            options={(catalog?.queues ?? []).map((q) => ({ value: q.id, label: q.name }))} />
          <ThresholdSlider value={raw.minScore} best={search ? run.data?.max_score : null} onChange={setThreshold} />
          <label className={labelClass}>
            {t('search.showLabel')}
            <select className={inputClass} value={raw.group}
              onChange={(e) => update({ group: e.target.value === 'fragment' ? 'fragment' : undefined })}>
              <option value="conversation">{t('search.group.conversation')}</option>
              <option value="fragment">{t('search.group.fragment')}</option>
            </select>
          </label>
        </div>
      </div>
      {similar ? <SimilarResults conversationId={similar} /> : search ? (
        <Results run={run} group={search.group} minScore={search.min_score} onThreshold={setThreshold} />
      ) : (
        <p className="rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center text-sm text-slate-500">
          {t('search.intro')}
        </p>
      )}
    </div>
  )
}

function Results({ run, group, minScore, onThreshold }: {
  run: ReturnType<typeof useSemanticSearch>
  group: 'conversation' | 'fragment'
  minScore: number
  onThreshold: (score: number) => void
}) {
  const { t } = useI18n()
  const data: SearchResponse | undefined = run.data
  const apiMessage = run.error instanceof ApiError && run.error.status === 422 && typeof run.error.detail === 'string'
    ? run.error.detail : undefined
  return (
    <section aria-label={t('search.results')} className="space-y-3">
      {run.isError && <LoadError message={apiMessage ?? t('search.error')} />}
      {!data && run.isFetching && <p role="status" className="text-sm text-slate-500">{t('search.searching')}</p>}
      {data && (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
            <p className="font-medium text-slate-700">{t(group === 'fragment' ? 'search.fragments' : 'conv.count', { count: data.total, n: formatInteger(data.total) })}</p>
            {data.expansions.length > 0 && (
              <p className="text-slate-500"><span>{t('search.alsoSearched')}</span> <span className="text-slate-700">{data.expansions.join(', ')}</span></p>
            )}
          </div>
          {data.results.length === 0 ? (
            <EmptyResults best={data.max_score} minScore={minScore} onThreshold={onThreshold} />
          ) : (
            <div className={`space-y-3 transition-opacity ${run.isFetching ? 'opacity-60' : ''}`}>
              {data.results.map((result) => (
                <ResultCard key={`${result.conversation_id}-${result.start_turn}`} conversation={result.conversation} score={result.score}
                  href={`/conversaciones/${result.conversation_id}?turn=${result.start_turn}`} turns={result.turns} highlights={result.highlights} />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}

function EmptyResults({ best, minScore, onThreshold }: { best: number | null; minScore: number; onThreshold: (score: number) => void }) {
  const { t } = useI18n()
  const box = 'space-y-2 rounded-xl border border-slate-200 bg-white py-10 text-center text-sm text-slate-500'
  if (best !== null && minScore > best) {
    // Múltiplo de 5 por debajo de la mejor puntuación, el paso del control.
    const adjusted = Math.floor(percent(best) / 5) * 5
    return (
      <div className={box}>
        <p>{t('search.belowThreshold', { min: formatPercentWhole(percent(minScore)), best: formatPercentWhole(percent(best)) })}</p>
        <button type="button" onClick={() => onThreshold(adjusted / 100)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-50">
          {t('search.adjustThreshold', { value: formatPercentWhole(adjusted) })}
        </button>
      </div>
    )
  }
  return (
    <div className={box}>
      <p>{t('search.noResults')}</p>
      <p>{t('search.noResultsHint')}</p>
    </div>
  )
}

function SimilarResults({ conversationId }: { conversationId: string }) {
  const { t } = useI18n()
  const { data, error, isPending } = useSimilar(conversationId)
  const notFound = error instanceof ApiError && error.status === 404
  return (
    <section aria-labelledby="similar-title" className="space-y-3">
      <h2 id="similar-title" className="text-sm font-medium text-slate-700">
        {t('search.similarTo')}{' '}
        <Link to={`/conversaciones/${conversationId}`} className="font-mono text-brand-700 hover:underline" title={conversationId}>
          {shortId(conversationId)}
        </Link>
      </h2>
      {notFound && <LoadError message={t('search.similarMissing')} />}
      {error && !notFound && <LoadError message={t('search.similarError')} />}
      {isPending && <p role="status" className="text-sm text-slate-500">{t('search.similarLoading')}</p>}
      {data && (
        <div className="space-y-3">
          {data.results.map((r) => (
            <ResultCard key={r.conversation_id} conversation={r.conversation} score={r.score} href={`/conversaciones/${r.conversation_id}`} />
          ))}
        </div>
      )}
    </section>
  )
}

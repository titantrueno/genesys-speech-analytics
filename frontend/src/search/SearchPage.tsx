import { Search } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { ApiError } from '../api/client'
import { useCatalog } from '../api/metrics'
import { MultiSelect } from '../components/MultiSelect'
import { LoadError } from '../dashboards/ChartCard'
import { parseIsoDate, presetRange, DEFAULT_PRESET } from '../dashboards/useDashboardFilters'
import { useDebouncedValue } from '../explorer/hooks'
import { formatInteger, shortId } from '../lib/format'
import { useSemanticSearch, useSimilar, type SearchResponse } from './api'
import { ResultCard } from './ResultCard'
import { useSearchState } from './useSearchState'

const inputClass = 'h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700'
const labelClass = 'flex flex-col gap-1 text-xs font-medium text-slate-500'

const percent = (score: number) => Math.round(score * 100)

function ThresholdSlider({ value, best, onChange }: { value: number; best?: number | null; onChange: (value: number) => void }) {
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
      Puntuación mínima
      <span className="flex h-9 items-center gap-2">
        <span className="relative flex w-32 items-center">
          <input type="range" min={0} max={100} step={5} value={draft} aria-label="Puntuación mínima"
            onChange={(e) => setDraft(Number(e.target.value))} className="w-full accent-brand-600" />
          {best != null && (
            <span data-testid="max-score-mark" aria-hidden title="Mejor puntuación de esta búsqueda"
              className="pointer-events-none absolute -top-1 h-5 w-0.5 -translate-x-1/2 rounded bg-amber-500"
              style={{ left: `${percent(best)}%` }} />
          )}
        </span>
        <span className="w-10 text-sm text-slate-700 tabular-nums">{draft} %</span>
      </span>
      {best != null && (
        <span className="absolute top-full mt-0.5 whitespace-nowrap text-[11px] font-normal text-slate-500">
          Mejor puntuación de esta búsqueda: {percent(best)} %
        </span>
      )}
    </label>
  )
}

export function SearchPage() {
  const { search, similar, raw, update } = useSearchState()
  const { data: catalog } = useCatalog()
  const run = useSemanticSearch(search)
  const [draft, setDraft] = useState(raw.q)
  const [previousQ, setPreviousQ] = useState(raw.q)
  if (raw.q !== previousQ) {
    setPreviousQ(raw.q)
    setDraft(raw.q)
  }

  const fallback = catalog ? presetRange(DEFAULT_PRESET, parseIsoDate(catalog.reference_date)) : undefined
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
        <h1 className="text-2xl font-semibold text-slate-900">Búsqueda semántica</h1>
        <p className="text-sm text-slate-500">Encuentra conversaciones por significado, no solo por palabras exactas.</p>
      </header>
      <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <form role="search" aria-label="Búsqueda" onSubmit={onSubmit} className="flex gap-2">
          <input type="search" aria-label="Consulta" maxLength={500} value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="Por ejemplo: me han cobrado algo que no he comprado"
            className="h-10 min-w-0 flex-1 rounded-md border border-slate-300 px-3 text-sm text-slate-800" />
          <button type="submit" className="inline-flex items-center gap-1.5 rounded-md bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700">
            <Search className="size-4" aria-hidden />Buscar
          </button>
        </form>
        <div className="flex flex-wrap items-end gap-x-3 gap-y-5 pb-3">
          <label className={labelClass}>
            Desde
            <input type="date" className={inputClass} value={from} max={to || undefined}
              onChange={(e) => e.target.value && update({ from: e.target.value, to: to || undefined })} />
          </label>
          <label className={labelClass}>
            Hasta
            <input type="date" className={inputClass} value={to} min={from || undefined}
              onChange={(e) => e.target.value && update({ from: from || undefined, to: e.target.value })} />
          </label>
          <label className={labelClass}>
            Canal
            <select className={inputClass} value={raw.channel} onChange={(e) => update({ channel: e.target.value || undefined })}>
              <option value="">Todos</option>
              <option value="voz">Voz</option>
              <option value="chat">Chat</option>
            </select>
          </label>
          <MultiSelect label="Cola" allLabel="Todas" selected={raw.queue} onChange={(queue) => update({ queue })}
            options={(catalog?.queues ?? []).map((q) => ({ value: q.id, label: q.name }))} />
          <ThresholdSlider value={raw.minScore} best={search ? run.data?.max_score : null} onChange={setThreshold} />
          <label className={labelClass}>
            Mostrar
            <select className={inputClass} value={raw.group}
              onChange={(e) => update({ group: e.target.value === 'fragment' ? 'fragment' : undefined })}>
              <option value="conversation">Mejor fragmento por conversación</option>
              <option value="fragment">Todos los fragmentos</option>
            </select>
          </label>
        </div>
      </div>
      {similar ? <SimilarResults conversationId={similar} /> : search ? (
        <Results run={run} group={search.group} minScore={search.min_score} onThreshold={setThreshold} />
      ) : (
        <p className="rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center text-sm text-slate-500">
          Escribe lo que buscas con tus palabras: encontraremos conversaciones que hablen de lo mismo aunque no usen los mismos términos.
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
  const data: SearchResponse | undefined = run.data
  const unit = group === 'fragment' ? ['fragmento', 'fragmentos'] : ['conversación', 'conversaciones']
  const apiMessage = run.error instanceof ApiError && run.error.status === 422 && typeof run.error.detail === 'string'
    ? run.error.detail : undefined
  return (
    <section aria-label="Resultados" className="space-y-3">
      {run.isError && <LoadError message={apiMessage ?? 'No se ha podido completar la búsqueda. Inténtalo de nuevo.'} />}
      {!data && run.isFetching && <p role="status" className="text-sm text-slate-500">Buscando…</p>}
      {data && (
        <>
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
            <p className="font-medium text-slate-700">{formatInteger(data.total)} {data.total === 1 ? unit[0] : unit[1]}</p>
            {data.expansions.length > 0 && (
              <p className="text-slate-500"><span>También se ha buscado:</span> <span className="text-slate-700">{data.expansions.join(', ')}</span></p>
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
  const box = 'space-y-2 rounded-xl border border-slate-200 bg-white py-10 text-center text-sm text-slate-500'
  if (best !== null && minScore > best) {
    // Múltiplo de 5 por debajo de la mejor puntuación, el paso del control.
    const adjusted = Math.floor(percent(best) / 5) * 5
    return (
      <div className={box}>
        <p>Ningún resultado alcanza el {percent(minScore)} %; la mejor coincidencia puntúa un {percent(best)} %.</p>
        <button type="button" onClick={() => onThreshold(adjusted / 100)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-50">
          Ajustar el umbral a {adjusted} %
        </button>
      </div>
    )
  }
  return (
    <div className={box}>
      <p>No hay resultados para esta búsqueda.</p>
      <p>Baja la puntuación mínima o amplía el intervalo.</p>
    </div>
  )
}

function SimilarResults({ conversationId }: { conversationId: string }) {
  const { data, error, isPending } = useSimilar(conversationId)
  const notFound = error instanceof ApiError && error.status === 404
  return (
    <section aria-labelledby="similar-title" className="space-y-3">
      <h2 id="similar-title" className="text-sm font-medium text-slate-700">
        Conversaciones similares a{' '}
        <Link to={`/conversaciones/${conversationId}`} className="font-mono text-brand-700 hover:underline" title={conversationId}>
          {shortId(conversationId)}
        </Link>
      </h2>
      {notFound && <LoadError message="La conversación de origen no existe." />}
      {error && !notFound && <LoadError message="No se han podido cargar las conversaciones similares." />}
      {isPending && <p role="status" className="text-sm text-slate-500">Buscando conversaciones similares…</p>}
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

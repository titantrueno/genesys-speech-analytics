import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, MessageSquareText, Phone, X } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { useConversations, type ConversationListItem, type ConversationQuery, type SortKey, type SortOrder } from '../api/conversations'
import { useCatalog } from '../api/metrics'
import { FilterBar } from '../dashboards/FilterBar'
import { useDashboardFilters } from '../dashboards/useDashboardFilters'
import { formatDuration, formatInteger, shortId } from '../lib/format'
import { activeFilterChips, CHANNEL_LABELS } from './labels'
import { ResolutionBadge, SentimentValue } from './badges'

const PAGE_SIZE = 25
const dateTime = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
const csatFormat = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function firstSentence(text: string): string {
  const match = text.match(/^.*?[.!?](?=\s|$)/)
  return match ? match[0] : text
}

function useConversationQuery(): ConversationQuery {
  const { filters, params } = useDashboardFilters()
  const sort = (['date', 'duration', 'sentiment'] as const).find((s) => s === params.get('sort')) ?? 'date'
  return {
    ...filters,
    resolution: params.getAll('resolution'),
    churn_risk: params.getAll('churn_risk'),
    sentiment_lt: params.get('sentiment_lt') ?? undefined,
    compliant: params.get('compliant') ?? undefined,
    repeat_contact: params.get('repeat_contact') ?? undefined,
    page: Math.max(1, Number(params.get('page') ?? 1) || 1),
    page_size: PAGE_SIZE,
    sort,
    order: params.get('order') === 'asc' ? 'asc' : 'desc',
  }
}

function SortHeader({ label, sortKey, query, onSort }: {
  label: string; sortKey: SortKey; query: ConversationQuery; onSort: (key: SortKey) => void
}) {
  const active = query.sort === sortKey
  const Icon = !active ? ArrowUpDown : query.order === 'asc' ? ArrowUp : ArrowDown
  return (
    <th scope="col" aria-sort={active ? (query.order === 'asc' ? 'ascending' : 'descending') : undefined} className="px-2.5 py-2 font-medium">
      <button type="button" onClick={() => onSort(sortKey)} className={`inline-flex items-center gap-1 ${active ? 'text-slate-900' : ''} hover:text-slate-900`}>
        {label}
        <Icon className="size-3.5" aria-hidden />
      </button>
    </th>
  )
}

function Row({ item }: { item: ConversationListItem }) {
  const location = useLocation()
  const ChannelIcon = item.channel === 'voz' ? Phone : MessageSquareText
  return (
    <tr className="border-b border-slate-100 align-top hover:bg-slate-50">
      <td className="px-2.5 py-2.5 whitespace-nowrap">
        <Link to={`/conversaciones/${item.id}`} state={{ from: location }} className="font-medium text-brand-700 hover:underline">
          {dateTime.format(new Date(item.started_at))}
        </Link>
        <p className="font-mono text-[11px] text-slate-400" title={item.id}>{shortId(item.id)}</p>
      </td>
      <td className="px-2.5 py-2.5 whitespace-nowrap">
        <span className="inline-flex items-center gap-1.5 text-slate-700"><ChannelIcon className="size-3.5 text-slate-400" aria-hidden />{CHANNEL_LABELS[item.channel]}</span>
      </td>
      <td className="px-2.5 py-2.5 text-slate-700">{item.queue}</td>
      <td className="px-2.5 py-2.5 text-slate-700">{item.agent}</td>
      <td className="px-2.5 py-2.5">
        <span className="inline-block rounded-lg bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">{item.main_topic_label}</span>
      </td>
      <td className="min-w-56 px-2.5 py-2.5 text-slate-600">
        <span title={item.summary} className="line-clamp-2">{firstSentence(item.summary)}</span>
      </td>
      <td className="px-2.5 py-2.5 text-right whitespace-nowrap text-slate-700 tabular-nums">{formatDuration(item.duration_s)}</td>
      <td className="px-2.5 py-2.5 whitespace-nowrap"><SentimentValue value={item.sentiment} /></td>
      <td className="px-2.5 py-2.5"><ResolutionBadge resolution={item.resolution} /></td>
      <td className="px-2.5 py-2.5 text-right text-slate-700 tabular-nums">{csatFormat.format(item.csat)}</td>
    </tr>
  )
}

export function ConversationsPage() {
  const { update, params } = useDashboardFilters()
  const query = useConversationQuery()
  const { data, isFetching, isError } = useConversations(query)
  const { data: catalog } = useCatalog()
  const chips = activeFilterChips(params, catalog)

  function onSort(key: SortKey) {
    const order: SortOrder = query.sort === key && query.order === 'desc' ? 'asc' : 'desc'
    const isDefault = key === 'date' && order === 'desc'
    update({ sort: isDefault ? undefined : key, order: isDefault ? undefined : order })
  }
  const goToPage = (page: number) => update({ page: page > 1 ? String(page) : undefined })

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Conversaciones</h1>
        <p className="text-sm text-slate-500">
          {data ? `${formatInteger(data.total)} ${data.total === 1 ? 'conversación' : 'conversaciones'}` : 'Cargando…'}
        </p>
      </header>
      <FilterBar />
      {chips.length > 0 && (
        <ul aria-label="Filtros activos" className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <li key={chip.id} className="inline-flex items-center gap-1 rounded-full border border-brand-100 bg-brand-50 py-0.5 pr-1 pl-3 text-sm text-brand-700">
              {chip.label}
              <button type="button" onClick={() => update(chip.remove)} aria-label={`Quitar filtro ${chip.label}`}
                className="rounded-full p-0.5 hover:bg-brand-100">
                <X className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      {isError && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">No se han podido cargar las conversaciones.</p>}
      <div className={`overflow-x-auto rounded-xl border border-slate-200 bg-white transition-opacity ${isFetching ? 'opacity-60' : ''}`}>
        <table aria-label="Conversaciones" className="w-full text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <SortHeader label="Fecha" sortKey="date" query={query} onSort={onSort} />
              <th scope="col" className="px-2.5 py-2 font-medium">Canal</th>
              <th scope="col" className="px-2.5 py-2 font-medium">Cola</th>
              <th scope="col" className="px-2.5 py-2 font-medium">Agente</th>
              <th scope="col" className="px-2.5 py-2 font-medium">Main topic</th>
              <th scope="col" className="px-2.5 py-2 font-medium">Summary</th>
              <SortHeader label="Duración" sortKey="duration" query={query} onSort={onSort} />
              <SortHeader label="Sentimiento" sortKey="sentiment" query={query} onSort={onSort} />
              <th scope="col" className="px-2.5 py-2 font-medium">Resolución</th>
              <th scope="col" className="px-2.5 py-2 text-right font-medium">CSAT</th>
            </tr>
          </thead>
          <tbody>{data?.items.map((item) => <Row key={item.id} item={item} />)}</tbody>
        </table>
        {data && data.total === 0 && (
          <p className="py-12 text-center text-sm text-slate-500">No hay conversaciones con estos filtros. Prueba a quitar alguno.</p>
        )}
      </div>
      {data && data.pages > 1 && (
        <nav aria-label="Paginación" className="flex items-center justify-between text-sm text-slate-600">
          <span>Página {query.page} de {data.pages}</span>
          <div className="flex gap-2">
            <button type="button" disabled={query.page <= 1} onClick={() => goToPage(query.page - 1)}
              className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">
              <ChevronLeft className="size-4" aria-hidden />Anterior
            </button>
            <button type="button" disabled={query.page >= data.pages} onClick={() => goToPage(query.page + 1)}
              className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">
              Siguiente<ChevronRight className="size-4" aria-hidden />
            </button>
          </div>
        </nav>
      )}
    </div>
  )
}

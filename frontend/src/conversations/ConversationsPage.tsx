import { X } from 'lucide-react'
import { useConversations, type ConversationQuery, type SortKey } from '../api/conversations'
import { useCatalog } from '../api/metrics'
import { FilterBar } from '../dashboards/FilterBar'
import { useDashboardFilters } from '../dashboards/useDashboardFilters'
import { formatInteger } from '../lib/format'
import { ConversationTable, Pagination } from './ConversationTable'
import { nextSort } from './sorting'
import { activeFilterChips } from './labels'

const PAGE_SIZE = 25

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

export function ConversationsPage() {
  const { update, params } = useDashboardFilters()
  const query = useConversationQuery()
  const { data, isFetching, isError } = useConversations(query)
  const { data: catalog } = useCatalog()
  const chips = activeFilterChips(params, catalog)

  function onSort(key: SortKey) {
    const next = nextSort(query, key)
    const isDefault = next.sort === 'date' && next.order === 'desc'
    update({ sort: isDefault ? undefined : next.sort, order: isDefault ? undefined : next.order })
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
      <ConversationTable items={data?.items ?? []} sort={query.sort} order={query.order} onSort={onSort} dimmed={isFetching}
        empty={data && <p className="py-12 text-center text-sm text-slate-500">No hay conversaciones con estos filtros. Prueba a quitar alguno.</p>} />
      {data && <Pagination page={query.page} pages={data.pages} onPage={goToPage} />}
    </div>
  )
}

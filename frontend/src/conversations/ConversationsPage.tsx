import { X } from 'lucide-react'
import { useConversations, type ConversationQuery, type SortKey } from '../api/conversations'
import { useCatalog } from '../api/metrics'
import { useI18n } from '../i18n/useI18n'
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
    phone: params.get('phone') ?? undefined,
    external_tag: params.get('external_tag') ?? undefined,
    page: Math.max(1, Number(params.get('page') ?? 1) || 1),
    page_size: PAGE_SIZE,
    sort,
    order: params.get('order') === 'asc' ? 'asc' : 'desc',
  }
}

/** Búsqueda exacta por ANI y `externalTag`; solo con conversaciones reales (FE012). */
function ExactSearch() {
  const { params, update } = useDashboardFilters()
  const { t } = useI18n()
  const phone = params.get('phone') ?? ''
  const tag = params.get('external_tag') ?? ''
  return (
    // La clave reinicia los campos cuando un chip quita el filtro.
    <form key={`${phone}|${tag}`} role="search" aria-label={t('conv.exactSearch')}
      className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-3"
      onSubmit={(event) => {
        event.preventDefault()
        const data = new FormData(event.currentTarget)
        update({ phone: String(data.get('phone') ?? '').trim() || undefined, external_tag: String(data.get('external_tag') ?? '').trim() || undefined })
      }}>
      <label className="text-xs font-medium text-slate-600">
        {t('conv.phone')}
        <input name="phone" defaultValue={phone} placeholder={t('conv.phonePlaceholder')}
          className="mt-1 block w-56 rounded-md border border-slate-300 px-2 py-1.5 text-sm font-normal" />
      </label>
      <label className="text-xs font-medium text-slate-600">
        externalTag
        <input name="external_tag" defaultValue={tag}
          className="mt-1 block w-56 rounded-md border border-slate-300 px-2 py-1.5 text-sm font-normal" />
      </label>
      <button type="submit" className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700">{t('conv.search')}</button>
    </form>
  )
}

export function ConversationsPage() {
  const { update, params } = useDashboardFilters()
  const { t } = useI18n()
  const query = useConversationQuery()
  const { data, isFetching, isError } = useConversations(query)
  const { data: catalog } = useCatalog()
  const chips = activeFilterChips(params, t, catalog)

  function onSort(key: SortKey) {
    const next = nextSort(query, key)
    const isDefault = next.sort === 'date' && next.order === 'desc'
    update({ sort: isDefault ? undefined : next.sort, order: isDefault ? undefined : next.order })
  }
  const goToPage = (page: number) => update({ page: page > 1 ? String(page) : undefined })

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">{t('conv.title')}</h1>
        <p className="text-sm text-slate-500">
          {data ? t('conv.count', { count: data.total, n: formatInteger(data.total) }) : t('common.loading')}
        </p>
      </header>
      <FilterBar />
      {catalog?.origin === 'real' && <ExactSearch />}
      {chips.length > 0 && (
        <ul aria-label={t('conv.activeFilters')} className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <li key={chip.id} className="inline-flex items-center gap-1 rounded-full border border-brand-100 bg-brand-50 py-0.5 pr-1 pl-3 text-sm text-brand-700">
              {chip.label}
              <button type="button" onClick={() => update(chip.remove)} aria-label={t('conv.removeFilter', { label: chip.label })}
                className="rounded-full p-0.5 hover:bg-brand-100">
                <X className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      {isError && <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{t('conv.loadError')}</p>}
      <ConversationTable items={data?.items ?? []} sort={query.sort} order={query.order} onSort={onSort} dimmed={isFetching}
        empty={data && <p className="py-12 text-center text-sm text-slate-500">{t('conv.empty')}</p>} />
      {data && <Pagination page={query.page} pages={data.pages} onPage={goToPage} />}
    </div>
  )
}

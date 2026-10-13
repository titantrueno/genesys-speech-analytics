import type { ReactNode } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, MessageSquareText, Phone } from 'lucide-react'
import { Link } from 'react-router'
import { useI18n } from '../i18n/useI18n'
import type { ConversationListItem, SortKey, SortOrder } from '../api/conversations'
import { formatDateTime, formatDecimal, formatDuration, shortId } from '../lib/format'
import { channelLabel } from './labels'
import { PendingText, ResolutionBadge, SentimentValue } from './badges'
import type { SortState } from './sorting'
import { useRowNavigation } from './useRowNavigation'


function firstSentence(text: string): string {
  const match = text.match(/^.*?[.!?](?=\s|$)/)
  return match ? match[0] : text
}


function SortHeader({ label, sortKey, query, onSort }: {
  label: string; sortKey: SortKey; query: SortState; onSort: (key: SortKey) => void
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


/** Las columnas de Genesys solo existen con conversaciones reales (FE012). */
function hasGenesysColumns(items: ConversationListItem[]): boolean {
  return items.some((item) => Boolean(item.transcript_quality))
}

function Row({ item, genesys }: { item: ConversationListItem; genesys: boolean }) {
  const { t } = useI18n()
  const href = `/conversaciones/${item.id}`
  const { onClick, onAuxClick, linkState } = useRowNavigation(href)
  const ChannelIcon = item.channel === 'voz' ? Phone : MessageSquareText

  return (
    <tr onClick={onClick} onAuxClick={onAuxClick} className="cursor-pointer border-b border-slate-100 align-top hover:bg-brand-50/60">
      <td className="px-2.5 py-2.5 whitespace-nowrap">
        <Link to={href} state={linkState} className="font-medium text-brand-700 hover:underline">
          {formatDateTime(item.started_at)}
        </Link>
        <p className="font-mono text-[11px] text-slate-400" title={item.id}>{shortId(item.id)}</p>
      </td>
      <td className="px-2.5 py-2.5 whitespace-nowrap">
        <span className="inline-flex items-center gap-1.5 text-slate-700"><ChannelIcon className="size-3.5 text-slate-400" aria-hidden />{channelLabel(t, item.channel)}</span>
      </td>
      <td className="px-2.5 py-2.5 text-slate-700">{item.queue ?? '—'}</td>
      <td className="px-2.5 py-2.5 text-slate-700">{item.agent ?? '—'}</td>
      {genesys && (
        <>
          <td className="px-2.5 py-2.5 whitespace-nowrap text-slate-700 tabular-nums">{item.ani ?? '—'}</td>
          <td className="px-2.5 py-2.5 text-slate-700">{item.external_tag ?? '—'}</td>
          <td className="px-2.5 py-2.5 whitespace-nowrap text-slate-700">
            {item.contained_in_bot === null ? '—' : item.contained_in_bot ? t('conv.contained') : t('conv.derived')}
          </td>
          <td className="px-2.5 py-2.5 whitespace-nowrap text-slate-700">
            {item.transcript_quality ? t(`conv.quality.${item.transcript_quality}`) : '—'}
          </td>
        </>
      )}
      <td className="px-2.5 py-2.5">
        {item.main_topic_label
          ? <span className="inline-block rounded-lg bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">{item.main_topic_label}</span>
          : <PendingText />}
      </td>
      <td className="min-w-56 px-2.5 py-2.5 text-slate-600">
        {item.summary
          ? <span title={item.summary} className="line-clamp-2">{firstSentence(item.summary)}</span>
          : <PendingText />}
      </td>
      <td className="px-2.5 py-2.5 text-right whitespace-nowrap text-slate-700 tabular-nums">{formatDuration(item.duration_s)}</td>
      <td className="px-2.5 py-2.5 whitespace-nowrap"><SentimentValue value={item.sentiment} /></td>
      <td className="px-2.5 py-2.5"><ResolutionBadge resolution={item.resolution} /></td>
      <td className="px-2.5 py-2.5 text-right text-slate-700 tabular-nums">{item.csat === null ? '—' : formatDecimal(item.csat, 2)}</td>
    </tr>
  )
}

export function ConversationTable({ items, sort, order, onSort, dimmed, empty }: {
  items: ConversationListItem[]
  sort: SortKey
  order: SortOrder
  onSort: (key: SortKey) => void
  dimmed?: boolean
  empty?: ReactNode
}) {
  const { t } = useI18n()
  const query = { sort, order }
  const genesys = hasGenesysColumns(items)
  return (
    <div className={`overflow-x-auto rounded-xl border border-slate-200 bg-white transition-opacity ${dimmed ? 'opacity-60' : ''}`}>
      <table aria-label={t('conv.title')} className="w-full text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
          <tr>
            <SortHeader label={t('conv.col.date')} sortKey="date" query={query} onSort={onSort} />
            <th scope="col" className="px-2.5 py-2 font-medium">{t('conv.col.channel')}</th>
            <th scope="col" className="px-2.5 py-2 font-medium">{t('conv.col.queue')}</th>
            <th scope="col" className="px-2.5 py-2 font-medium">{t('conv.col.agent')}</th>
            {genesys && (
              <>
                <th scope="col" className="px-2.5 py-2 font-medium">ANI</th>
                <th scope="col" className="px-2.5 py-2 font-medium">externalTag</th>
                <th scope="col" className="px-2.5 py-2 font-medium">{t('conv.col.containment')}</th>
                <th scope="col" className="px-2.5 py-2 font-medium">{t('conv.transcript')}</th>
              </>
            )}
            <th scope="col" className="px-2.5 py-2 font-medium">{t('conv.col.mainTopic')}</th>
            <th scope="col" className="px-2.5 py-2 font-medium">{t('conv.col.summary')}</th>
            <SortHeader label={t('conv.col.duration')} sortKey="duration" query={query} onSort={onSort} />
            <SortHeader label={t('conv.col.sentiment')} sortKey="sentiment" query={query} onSort={onSort} />
            <th scope="col" className="px-2.5 py-2 font-medium">{t('conv.col.resolution')}</th>
            <th scope="col" className="px-2.5 py-2 text-right font-medium">CSAT</th>
          </tr>
        </thead>
        <tbody>{items.map((item) => <Row key={item.id} item={item} genesys={genesys} />)}</tbody>
      </table>
      {items.length === 0 && empty}
    </div>
  )
}

export function Pagination({ page, pages, onPage }: { page: number; pages: number; onPage: (page: number) => void }) {
  const { t } = useI18n()
  if (pages <= 1) return null
  return (
    <nav aria-label={t('conv.pagination')} className="flex items-center justify-between text-sm text-slate-600">
      <span>{t('conv.page', { page, pages })}</span>
      <div className="flex gap-2">
        <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}
          className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">
          <ChevronLeft className="size-4" aria-hidden />{t('conv.prev')}
        </button>
        <button type="button" disabled={page >= pages} onClick={() => onPage(page + 1)}
          className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40">
          {t('conv.next')}<ChevronRight className="size-4" aria-hidden />
        </button>
      </div>
    </nav>
  )
}

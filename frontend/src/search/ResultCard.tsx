import { MessageSquareText, Phone } from 'lucide-react'
import { Link } from 'react-router'
import { SentimentValue } from '../conversations/badges'
import { CHANNEL_LABELS } from '../conversations/labels'
import { useRowNavigation } from '../conversations/useRowNavigation'
import { formatDateTimeWithYear } from '../lib/format'
import { highlight } from '../lib/highlight'
import type { ConversationListItem } from '../api/conversations'
import type { SearchResult } from './api'


export function ScoreBar({ score }: { score: number }) {
  const percent = Math.round(score * 100)
  return (
    <div className="flex items-center gap-2">
      <div role="meter" aria-label="Puntuación" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
        className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${percent}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-medium text-slate-700 tabular-nums">{percent} %</span>
    </div>
  )
}

/** Tarjeta navegable de una conversación: con fragmento (búsqueda) o sin él (similares). */
export function ResultCard({ conversation: conv, score, href, turns, highlights = [] }: {
  conversation: ConversationListItem
  score: number
  href: string
  turns?: SearchResult['turns']
  highlights?: string[]
}) {
  const { onClick, onAuxClick, linkState } = useRowNavigation(href)
  const ChannelIcon = conv.channel === 'voz' ? Phone : MessageSquareText
  const speaker = (s: SearchResult['turns'][number]['speaker']) => s === 'agente' ? conv.agent : s === 'bot' ? 'Asistente virtual' : 'Cliente'

  return (
    <article onClick={onClick} onAuxClick={onAuxClick}
      className="cursor-pointer rounded-xl border border-slate-200 bg-white p-4 transition-colors hover:border-brand-300 hover:bg-brand-50/40">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600">
          <Link to={href} state={linkState} className="font-medium text-brand-700 hover:underline">
            {formatDateTimeWithYear(conv.started_at)}
          </Link>
          <span className="inline-flex items-center gap-1.5"><ChannelIcon className="size-3.5 text-slate-400" aria-hidden />{CHANNEL_LABELS[conv.channel]}</span>
          <span>{conv.queue}</span>
          <span className="rounded-lg bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">{conv.main_topic_label}</span>
          <SentimentValue value={conv.sentiment} />
        </div>
        <ScoreBar score={score} />
      </header>
      {turns && (
        <ol className="mt-3 space-y-1 border-l-2 border-brand-200 pl-3 text-sm leading-relaxed text-slate-800">
          {turns.map((turn) => (
            <li key={turn.index}>
              <span className="font-medium text-slate-900">{speaker(turn.speaker)}</span>
              <span className="text-slate-400">: </span>
              {highlight(turn.text, highlights)}
            </li>
          ))}
        </ol>
      )}
      <p className="mt-2 line-clamp-2 text-xs text-slate-500" title={conv.summary}>{conv.summary}</p>
    </article>
  )
}

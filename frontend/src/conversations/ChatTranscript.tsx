import { Bot, CircleAlert, Split } from 'lucide-react'
import { Fragment } from 'react'
import type { ConversationDetail, Turn } from '../api/conversations'
import { useI18n } from '../i18n/useI18n'
import { formatOffset } from '../lib/format'
import { highlight } from '../lib/highlight'
import { sentimentTone } from './labels'

const SIDE: Record<Turn['speaker'], 'left' | 'right' | 'center'> = { cliente: 'left', agente: 'right', bot: 'right', sistema: 'center' }

const BUBBLE: Record<Exclude<Turn['speaker'], 'sistema'>, string> = {
  cliente: 'bg-white rounded-2xl rounded-tl-sm',
  agente: 'bg-[#d9fdd3] rounded-2xl rounded-tr-sm',
  bot: 'bg-[#e3eefc] rounded-2xl rounded-tr-sm border border-brand-100',
}

/** Turnos del agente que toman la conversación de manos del bot: ahí va la línea de transferencia (FE012). */
function transfersBefore(turns: Turn[]): boolean[] {
  let handler: 'bot' | 'agente' | null = null
  return turns.map((turn) => {
    const transfer = turn.speaker === 'agente' && handler === 'bot'
    if (turn.speaker === 'bot' || turn.speaker === 'agente') handler = turn.speaker
    return transfer
  })
}

interface Props {
  conversation: ConversationDetail
  activeTurn: number | null
  registerTurn: (index: number, element: HTMLLIElement | null) => void
}

export function ChatTranscript({ conversation, activeTurn, registerTurn }: Props) {
  const { t } = useI18n()
  const keywords = conversation.analysis.keywords
  const speakerName = (speaker: Turn['speaker']) =>
    speaker === 'agente' ? conversation.agent ?? t('conv.speaker.agent') : speaker === 'bot' ? t('conv.speaker.bot') : t('conv.speaker.customer')
  const transfers = transfersBefore(conversation.turns)

  return (
    <ol aria-label={t('conv.transcript')} className="space-y-2 p-4">
      {conversation.turns.map((turn, index) => {
        const transfer = transfers[index]
        const side = SIDE[turn.speaker]
        const active = activeTurn === index
        const common = {
          ref: (el: HTMLLIElement | null) => registerTurn(index, el),
          'data-turn': index,
          'data-speaker': turn.speaker,
          'data-side': side,
          'data-active': active ? 'true' : undefined,
        }
        const line = transfer && (
          <li role="separator" aria-label={t('conv.transfer')}
            className="flex items-center gap-2 py-1 text-xs font-medium text-brand-700">
            <span className="h-px flex-1 bg-brand-200" aria-hidden />
            <Split className="size-3.5" aria-hidden />{t('conv.transfer')}
            <span className="h-px flex-1 bg-brand-200" aria-hidden />
          </li>
        )
        if (turn.speaker === 'sistema') {
          return (
            <li key={index} {...common} className="flex justify-center py-1">
              <span className="rounded-lg bg-white/70 px-3 py-1 text-xs text-slate-600 shadow-sm">
                {turn.text} · {formatOffset(turn.offset_s)}
              </span>
            </li>
          )
        }
        const tone = turn.sentiment === null ? null : sentimentTone(turn.sentiment, t)
        const undelivered = turn.delivered === false
        return (
          <Fragment key={index}>
          {line}
          <li {...common} className={`flex ${side === 'left' ? 'justify-start' : 'justify-end'}`}>
            <div className={`max-w-[75%] px-3 py-2 shadow-sm transition-shadow ${BUBBLE[turn.speaker]} ${undelivered ? 'border border-dashed border-amber-400 opacity-80' : ''} ${active ? 'ring-2 ring-brand-500' : ''}`}>
              <p className="flex items-center gap-1 text-xs font-semibold text-slate-600">
                {turn.speaker === 'bot' && <Bot className="size-3.5" aria-hidden />}
                {speakerName(turn.speaker)}
              </p>
              <p className="mt-0.5 text-sm leading-relaxed text-slate-800">{highlight(turn.text, keywords)}</p>
              <p className="mt-1 flex items-center justify-end gap-1.5 text-[11px] text-slate-500">
                {undelivered && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 font-medium text-amber-800">
                    <CircleAlert className="size-3" aria-hidden />{t('conv.undelivered')}
                  </span>
                )}
                {tone && (
                  <>
                    <span aria-hidden className="size-2 rounded-full" style={{ background: tone.color }} title={t('conv.sentimentTone', { tone: tone.label.toLowerCase() })} />
                    <span className="sr-only">{t('conv.sentimentTone', { tone: tone.label.toLowerCase() })}</span>
                  </>
                )}
                <span className="tabular-nums">{formatOffset(turn.offset_s)}</span>
              </p>
            </div>
          </li>
          </Fragment>
        )
      })}
    </ol>
  )
}

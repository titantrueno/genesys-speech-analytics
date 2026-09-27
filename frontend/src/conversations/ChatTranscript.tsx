import { Bot } from 'lucide-react'
import type { ConversationDetail, Turn } from '../api/conversations'
import { formatOffset } from '../lib/format'
import { highlight } from '../lib/highlight'
import { sentimentTone } from './labels'

const SIDE: Record<Turn['speaker'], 'left' | 'right' | 'center'> = { cliente: 'left', agente: 'right', bot: 'right', sistema: 'center' }

const BUBBLE: Record<Exclude<Turn['speaker'], 'sistema'>, string> = {
  cliente: 'bg-white rounded-2xl rounded-tl-sm',
  agente: 'bg-[#d9fdd3] rounded-2xl rounded-tr-sm',
  bot: 'bg-[#e3eefc] rounded-2xl rounded-tr-sm border border-brand-100',
}

interface Props {
  conversation: ConversationDetail
  activeTurn: number | null
  registerTurn: (index: number, element: HTMLLIElement | null) => void
}

export function ChatTranscript({ conversation, activeTurn, registerTurn }: Props) {
  const keywords = conversation.analysis.keywords
  const speakerName = (speaker: Turn['speaker']) =>
    speaker === 'agente' ? conversation.agent : speaker === 'bot' ? 'Asistente virtual' : 'Cliente'

  return (
    <ol aria-label="Transcripción" className="space-y-2 p-4">
      {conversation.turns.map((turn, index) => {
        const side = SIDE[turn.speaker]
        const active = activeTurn === index
        const common = {
          ref: (el: HTMLLIElement | null) => registerTurn(index, el),
          'data-turn': index,
          'data-speaker': turn.speaker,
          'data-side': side,
          'data-active': active ? 'true' : undefined,
        }
        if (turn.speaker === 'sistema') {
          return (
            <li key={index} {...common} className="flex justify-center py-1">
              <span className="rounded-lg bg-white/70 px-3 py-1 text-xs text-slate-600 shadow-sm">
                {turn.text} · {formatOffset(turn.offset_s)}
              </span>
            </li>
          )
        }
        const tone = sentimentTone(turn.sentiment)
        return (
          <li key={index} {...common} className={`flex ${side === 'left' ? 'justify-start' : 'justify-end'}`}>
            <div className={`max-w-[75%] px-3 py-2 shadow-sm transition-shadow ${BUBBLE[turn.speaker]} ${active ? 'ring-2 ring-brand-500' : ''}`}>
              <p className="flex items-center gap-1 text-xs font-semibold text-slate-600">
                {turn.speaker === 'bot' && <Bot className="size-3.5" aria-hidden />}
                {speakerName(turn.speaker)}
              </p>
              <p className="mt-0.5 text-sm leading-relaxed text-slate-800">{highlight(turn.text, keywords)}</p>
              <p className="mt-1 flex items-center justify-end gap-1.5 text-[11px] text-slate-500">
                <span aria-hidden className="size-2 rounded-full" style={{ background: tone.color }} title={`Sentimiento ${tone.label.toLowerCase()}`} />
                <span className="sr-only">Sentimiento {tone.label.toLowerCase()}</span>
                <span className="tabular-nums">{formatOffset(turn.offset_s)}</span>
              </p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

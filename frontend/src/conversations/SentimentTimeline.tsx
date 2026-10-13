import type { KeyboardEvent } from 'react'
import type { Turn } from '../api/conversations'
import { useI18n } from '../i18n/useI18n'
import { formatOffset, formatSigned } from '../lib/format'
import { sentimentTone } from './labels'

const WIDTH = 320
const HEIGHT = 150
const M = { top: 12, right: 12, bottom: 24, left: 28 }

interface Props {
  turns: Turn[]
  activeTurn: number | null
  onSelect: (turnIndex: number) => void
}

export function SentimentTimeline({ turns, activeTurn, onSelect }: Props) {
  const { t } = useI18n()
  // Solo los turnos del cliente con sentimiento: en las conversaciones reales, Genesys puede no darlo (FE012).
  const points = turns.flatMap((turn, index) =>
    turn.speaker === 'cliente' && turn.sentiment !== null ? [{ index, turn, sentiment: turn.sentiment }] : [])
  const innerW = WIDTH - M.left - M.right
  const innerH = HEIGHT - M.top - M.bottom
  const x = (i: number) => M.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
  const y = (v: number) => M.top + ((1 - v) / 2) * innerH
  const line = points.map((p, i) => `${x(i)},${y(p.sentiment)}`).join(' ')

  function onKey(event: KeyboardEvent, turnIndex: number) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(turnIndex)
    }
  }

  return (
    <div role="group" aria-label={t('conv.timeline.group')}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" aria-hidden={points.length === 0}>
        {[1, 0, -1].map((v) => (
          <g key={v}>
            <line x1={M.left} x2={WIDTH - M.right} y1={y(v)} y2={y(v)}
              stroke={v === 0 ? 'var(--chart-axis)' : 'var(--chart-grid)'} strokeWidth={1} />
            <text x={M.left - 6} y={y(v)} dy="0.32em" textAnchor="end" fontSize={10} fill="var(--chart-muted)">
              {v === 0 ? '0' : formatSigned(v).replace(',00', '')}
            </text>
          </g>
        ))}
        <polyline points={line} fill="none" stroke="var(--chart-muted)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {points.map((p, i) => {
          const tone = sentimentTone(p.sentiment, t)
          const active = activeTurn === p.index
          return (
            <g key={p.index} role="button" tabIndex={0} className="cursor-pointer outline-none [&:focus-visible>circle:last-child]:stroke-[var(--series-1)]"
              aria-label={t('conv.timeline.point', { n: p.index + 1, value: formatSigned(p.sentiment), tone: tone.label.toLowerCase() })}
              onClick={() => onSelect(p.index)} onKeyDown={(e) => onKey(e, p.index)}>
              <title>{t('conv.timeline.title', { n: p.index + 1, time: formatOffset(p.turn.offset_s), value: formatSigned(p.sentiment) })}</title>
              <circle cx={x(i)} cy={y(p.sentiment)} r={12} fill="transparent" />
              <circle cx={x(i)} cy={y(p.sentiment)} r={active ? 6 : 4.5} fill={tone.color}
                stroke={active ? 'var(--series-1)' : 'var(--chart-surface)'} strokeWidth={2} />
            </g>
          )
        })}
        <text x={M.left} y={HEIGHT - 6} fontSize={10} fill="var(--chart-muted)">{t('conv.timeline.start')}</text>
        <text x={WIDTH - M.right} y={HEIGHT - 6} fontSize={10} fill="var(--chart-muted)" textAnchor="end">{t('conv.timeline.end')}</text>
      </svg>
      <p className="text-xs text-slate-500">{t('conv.timeline.hint')}</p>
    </div>
  )
}


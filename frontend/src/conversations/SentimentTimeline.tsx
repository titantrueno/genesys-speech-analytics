import type { KeyboardEvent } from 'react'
import type { Turn } from '../api/conversations'
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
  const points = turns.map((turn, index) => ({ index, turn })).filter((p) => p.turn.speaker === 'cliente')
  const innerW = WIDTH - M.left - M.right
  const innerH = HEIGHT - M.top - M.bottom
  const x = (i: number) => M.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
  const y = (v: number) => M.top + ((1 - v) / 2) * innerH
  const line = points.map((p, i) => `${x(i)},${y(p.turn.sentiment)}`).join(' ')

  function onKey(event: KeyboardEvent, turnIndex: number) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(turnIndex)
    }
  }

  return (
    <div role="group" aria-label="Evolución del sentimiento del cliente">
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
          const tone = sentimentTone(p.turn.sentiment)
          const active = activeTurn === p.index
          return (
            <g key={p.index} role="button" tabIndex={0} className="cursor-pointer outline-none [&:focus-visible>circle:last-child]:stroke-[var(--series-1)]"
              aria-label={`Turno ${p.index + 1}: sentimiento ${formatSigned(p.turn.sentiment)} (${tone.label.toLowerCase()})`}
              onClick={() => onSelect(p.index)} onKeyDown={(e) => onKey(e, p.index)}>
              <title>{`Turno ${p.index + 1} · ${formatOffset(p.turn.offset_s)} · ${formatSigned(p.turn.sentiment)}`}</title>
              <circle cx={x(i)} cy={y(p.turn.sentiment)} r={12} fill="transparent" />
              <circle cx={x(i)} cy={y(p.turn.sentiment)} r={active ? 6 : 4.5} fill={tone.color}
                stroke={active ? 'var(--series-1)' : 'var(--chart-surface)'} strokeWidth={2} />
            </g>
          )
        })}
        <text x={M.left} y={HEIGHT - 6} fontSize={10} fill="var(--chart-muted)">Inicio</text>
        <text x={WIDTH - M.right} y={HEIGHT - 6} fontSize={10} fill="var(--chart-muted)" textAnchor="end">Final</text>
      </svg>
      <p className="text-xs text-slate-500">Pulsa un punto para ir a ese mensaje del cliente.</p>
    </div>
  )
}


import { AlertTriangle, ArrowUpRight, CheckCircle2 } from 'lucide-react'
import type { Resolution } from '../api/conversations'
import { RESOLUTION_LABELS, sentimentTone } from './labels'

const RESOLUTION_STYLE: Record<Resolution, { icon: typeof CheckCircle2; className: string }> = {
  resuelta: { icon: CheckCircle2, className: 'bg-green-50 text-[var(--status-good-text)]' },
  no_resuelta: { icon: AlertTriangle, className: 'bg-red-50 text-[var(--status-critical)]' },
  escalada: { icon: ArrowUpRight, className: 'bg-amber-50 text-amber-800' },
}

export function ResolutionBadge({ resolution }: { resolution: Resolution }) {
  const { icon: Icon, className } = RESOLUTION_STYLE[resolution]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${className}`}>
      <Icon className="size-3.5" aria-hidden />{RESOLUTION_LABELS[resolution]}
    </span>
  )
}

const signed = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero' })

export function SentimentValue({ value }: { value: number }) {
  const tone = sentimentTone(value)
  return (
    <span className="inline-flex items-center gap-1.5 text-slate-700 tabular-nums" title={tone.label}>
      <span aria-hidden className="size-2 rounded-full" style={{ background: tone.color }} />
      {signed.format(value)}
      <span className="sr-only">{tone.label}</span>
    </span>
  )
}

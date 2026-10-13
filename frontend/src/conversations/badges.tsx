import { AlertTriangle, ArrowUpRight, CheckCircle2 } from 'lucide-react'
import type { Resolution } from '../api/conversations'
import { useI18n } from '../i18n/useI18n'
import { formatSigned } from '../lib/format'
import { resolutionLabel, sentimentTone } from './labels'

const RESOLUTION_STYLE: Record<Resolution, { icon: typeof CheckCircle2; className: string }> = {
  resuelta: { icon: CheckCircle2, className: 'bg-green-50 text-[var(--status-good-text)]' },
  no_resuelta: { icon: AlertTriangle, className: 'bg-red-50 text-[var(--status-critical)]' },
  escalada: { icon: ArrowUpRight, className: 'bg-amber-50 text-amber-800' },
}

/** Campo del análisis de la plataforma que una conversación real aún no tiene (FE012). */
export function PendingText({ className = '' }: { className?: string }) {
  const { t } = useI18n()
  return <span className={`text-xs text-slate-400 italic ${className}`}>{t('domain.analysisPending')}</span>
}

export function ResolutionBadge({ resolution }: { resolution: Resolution | null }) {
  const { t } = useI18n()
  if (resolution === null) return <PendingText />
  const { icon: Icon, className } = RESOLUTION_STYLE[resolution]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${className}`}>
      <Icon className="size-3.5" aria-hidden />{resolutionLabel(t, resolution)}
    </span>
  )
}


export function SentimentValue({ value }: { value: number | null }) {
  const { t } = useI18n()
  if (value === null) return <span className="text-slate-400" title={t('conv.noSentiment')}>—</span>
  const tone = sentimentTone(value, t)
  return (
    <span className="inline-flex items-center gap-1.5 text-slate-700 tabular-nums" title={tone.label}>
      <span aria-hidden className="size-2 rounded-full" style={{ background: tone.color }} />
      {formatSigned(value)}
      <span className="sr-only">{tone.label}</span>
    </span>
  )
}

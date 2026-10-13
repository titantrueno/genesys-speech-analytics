import { CheckCircle2, CircleMinus, Clock, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ConversationDetail } from '../api/conversations'
import { useCatalog } from '../api/metrics'
import type { Translate } from '../i18n/context'
import type { TKey } from '../i18n/dictionaries'
import { useI18n } from '../i18n/useI18n'
import { formatDecimal } from '../lib/format'
import { PendingText, ResolutionBadge, SentimentValue } from './badges'
import { Metric, Section } from './panelParts'
import { churnLabel } from './labels'
import { SentimentTimeline } from './SentimentTimeline'

const CHURN_STYLE: Record<string, string> = {
  bajo: 'text-[var(--status-good-text)]',
  medio: 'text-amber-700',
  alto: 'text-[var(--status-critical)]',
}

interface Props {
  conversation: ConversationDetail
  activeTurn: number | null
  onSelectTurn: (turnIndex: number) => void
}

/** Lo que falta del análisis, para el aviso (FE014): solo nombra lo que aún no se ha generado. */
function missingParts(a: ConversationDetail['analysis'], t: Translate): string[] {
  const pending = a.compliance_pending?.length ?? 0
  return [
    ...(a.summary ? [] : [t('conv.missing.summary')]), ...(a.main_topic ? [] : [t('conv.missing.mainTopic')]),
    ...(a.resolution === null ? [t('conv.missing.resolution')] : []), ...(a.csat === null ? [t('conv.missing.csat')] : []),
    ...(a.effort === null ? [t('conv.missing.effort')] : []), ...(a.churn_risk === null ? [t('conv.missing.churn')] : []),
    ...(pending ? [t('conv.missing.checks', { count: pending, n: pending })] : []),
  ]
}

function sentence(parts: string[], t: Translate): string {
  const list = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(', ')}${t('conv.missing.and')}${parts.at(-1)}`
  const text = t(parts.length === 1 ? 'conv.missing.one' : 'conv.missing.many', { list })
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function Pending() {
  const { t } = useI18n()
  return <span className="text-xs font-normal text-slate-400 italic">{t('domain.pending')}</span>
}

const COMPLIANCE_STATES = {
  cumple: [CheckCircle2, 'conv.compliance.cumple', 'text-[var(--status-good-text)]'],
  no_cumple: [XCircle, 'conv.compliance.no_cumple', 'text-[var(--status-critical)]'],
  no_aplica: [CircleMinus, 'conv.compliance.no_aplica', 'text-slate-400'],
  pendiente: [Clock, 'conv.compliance.pendiente', 'text-slate-400 italic'],
} as const satisfies Record<string, readonly [unknown, TKey, string]>

/** Cada dato del análisis se muestra en cuanto existe (FE014): en una conversación real, lo que falta dice «Pendiente». */
export function AnalysisPanel({ conversation, activeTurn, onSelectTurn }: Props) {
  const { data: catalog } = useCatalog()
  const { t, tOr } = useI18n()
  const a = conversation.analysis
  const pendingChecks = new Set(a.compliance_pending ?? [])
  const checks = (catalog?.compliance_checks ?? []).filter((check) => check.code in a.compliance || pendingChecks.has(check.code))
  const missing = a.pending ? missingParts(a, t) : []
  const orPending = (value: unknown, shown: ReactNode) => (value === null ? (a.pending ? <Pending /> : '—') : shown)

  return (
    <aside aria-label={t('conv.analysis')} className="rounded-xl border border-slate-200 bg-white">
      <Section title={t('conv.sec.result')}>
        {missing.length > 0 && (
          <p className="mb-2 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
            <PendingText className="text-sm font-medium" />
            <span className="mt-1 block">{sentence(missing, t)}</span>
          </p>
        )}
        <dl>
          <Metric label={t('conv.m.resolution')}>{orPending(a.resolution, <ResolutionBadge resolution={a.resolution} />)}</Metric>
          <Metric label={t('conv.m.csat')}>{orPending(a.csat, a.csat !== null && t('conv.outOf5', { value: formatDecimal(a.csat, 1) }))}</Metric>
          <Metric label={t('conv.m.effort')}>{orPending(a.effort, a.effort !== null && t('conv.outOf5', { value: formatDecimal(a.effort, 1) }))}</Metric>
          <Metric label={t('conv.m.churn')}>
            {orPending(a.churn_risk, a.churn_risk !== null && <span className={CHURN_STYLE[a.churn_risk]}>{churnLabel(t, a.churn_risk)}</span>)}
          </Metric>
          <Metric label={t('conv.m.sentiment')}>{orPending(a.sentiment, <SentimentValue value={a.sentiment} />)}</Metric>
        </dl>
      </Section>
      <Section title={t('conv.sec.timeline')}>
        <SentimentTimeline turns={conversation.turns} activeTurn={activeTurn} onSelect={onSelectTurn} />
      </Section>
      <Section title={t('conv.sec.compliance')}>
        <ul aria-label={t('conv.sec.compliance')} className="space-y-1.5">
          {checks.map((check) => {
            const value = a.compliance[check.code]
            const state = pendingChecks.has(check.code) ? 'pendiente' : value === null ? 'no_aplica' : value ? 'cumple' : 'no_cumple'
            const [Icon, label, color] = COMPLIANCE_STATES[state]
            return (
              <li key={check.code} className="flex items-start justify-between gap-3 text-sm">
                <span className="text-slate-700">{check.label}</span>
                <span className={`inline-flex shrink-0 items-center gap-1 text-xs font-medium ${color}`}>
                  <Icon className="size-4" aria-hidden />{t(label)}
                </span>
              </li>
            )
          })}
        </ul>
      </Section>
      {a.secondary_topics.length > 0 && (
        <Section title={t('conv.sec.secondary')}>
          <ul className="flex flex-wrap gap-1.5">
            {a.secondary_topics.map((topic) => (
              <li key={topic} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">{topic}</li>
            ))}
          </ul>
        </Section>
      )}
      {a.entities.length > 0 && (
        <Section title={t('conv.sec.entities')}>
          <dl>{a.entities.map((e) => <Metric key={`${e.type}-${e.value}`} label={tOr(`conv.entity.${e.type}`, e.type)}>{e.value}</Metric>)}</dl>
        </Section>
      )}
      {a.keywords.length > 0 && (
        <Section title={t('conv.sec.keywords')}>
          <ul className="flex flex-wrap gap-1.5">
            {a.keywords.map((k) => <li key={k} className="rounded bg-amber-100 px-2 py-0.5 text-xs text-slate-800">{k}</li>)}
          </ul>
        </Section>
      )}
    </aside>
  )
}

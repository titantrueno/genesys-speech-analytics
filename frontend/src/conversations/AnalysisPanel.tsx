import { CheckCircle2, CircleMinus, Clock, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ConversationDetail } from '../api/conversations'
import { useCatalog } from '../api/metrics'
import { formatDecimal } from '../lib/format'
import { PendingText, ResolutionBadge, SentimentValue } from './badges'
import { Metric, Section } from './panelParts'
import { CHURN_LABELS } from './labels'
import { SentimentTimeline } from './SentimentTimeline'

const ENTITY_LABELS: Record<string, string> = { importe: 'Importe', producto: 'Producto', fecha: 'Fecha', comercio: 'Comercio' }
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
function missingParts(a: ConversationDetail['analysis']): string[] {
  const pending = a.compliance_pending?.length ?? 0
  return [
    ...(a.summary ? [] : ['el summary']), ...(a.main_topic ? [] : ['el main topic']),
    ...(a.resolution === null ? ['la resolución'] : []), ...(a.csat === null ? ['el CSAT'] : []),
    ...(a.effort === null ? ['el esfuerzo'] : []), ...(a.churn_risk === null ? ['el riesgo de abandono'] : []),
    ...(pending ? [`${pending} ${pending === 1 ? 'check' : 'checks'} de cumplimiento`] : []),
  ]
}

function sentence(parts: string[]): string {
  const list = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(', ')} y ${parts.at(-1)}`
  const text = `${list} aún no ${parts.length === 1 ? 'se ha generado' : 'se han generado'}.`
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function Pending() {
  return <span className="text-xs font-normal text-slate-400 italic">Pendiente</span>
}

const COMPLIANCE_STATES = {
  cumple: [CheckCircle2, 'Cumple', 'text-[var(--status-good-text)]'],
  no_cumple: [XCircle, 'No cumple', 'text-[var(--status-critical)]'],
  no_aplica: [CircleMinus, 'No aplica', 'text-slate-400'],
  pendiente: [Clock, 'Pendiente', 'text-slate-400 italic'],
} as const

/** Cada dato del análisis se muestra en cuanto existe (FE014): en una conversación real, lo que falta dice «Pendiente». */
export function AnalysisPanel({ conversation, activeTurn, onSelectTurn }: Props) {
  const { data: catalog } = useCatalog()
  const a = conversation.analysis
  const pendingChecks = new Set(a.compliance_pending ?? [])
  const checks = (catalog?.compliance_checks ?? []).filter((check) => check.code in a.compliance || pendingChecks.has(check.code))
  const missing = a.pending ? missingParts(a) : []
  const orPending = (value: unknown, shown: ReactNode) => (value === null ? (a.pending ? <Pending /> : '—') : shown)

  return (
    <aside aria-label="Análisis" className="rounded-xl border border-slate-200 bg-white">
      <Section title="Resultado">
        {missing.length > 0 && (
          <p className="mb-2 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
            <PendingText className="text-sm font-medium" />
            <span className="mt-1 block">{sentence(missing)}</span>
          </p>
        )}
        <dl>
          <Metric label="Resolución">{orPending(a.resolution, <ResolutionBadge resolution={a.resolution} />)}</Metric>
          <Metric label="CSAT predicho">{orPending(a.csat, a.csat !== null && `${formatDecimal(a.csat, 1)} / 5`)}</Metric>
          <Metric label="Esfuerzo del cliente">{orPending(a.effort, a.effort !== null && `${formatDecimal(a.effort, 1)} / 5`)}</Metric>
          <Metric label="Riesgo de abandono">
            {orPending(a.churn_risk, a.churn_risk !== null && <span className={CHURN_STYLE[a.churn_risk]}>{CHURN_LABELS[a.churn_risk]}</span>)}
          </Metric>
          <Metric label="Sentimiento global">{orPending(a.sentiment, <SentimentValue value={a.sentiment} />)}</Metric>
        </dl>
      </Section>
      <Section title="Evolución del sentimiento">
        <SentimentTimeline turns={conversation.turns} activeTurn={activeTurn} onSelect={onSelectTurn} />
      </Section>
      <Section title="Cumplimiento">
        <ul aria-label="Cumplimiento" className="space-y-1.5">
          {checks.map((check) => {
            const value = a.compliance[check.code]
            const state = pendingChecks.has(check.code) ? 'pendiente' : value === null ? 'no_aplica' : value ? 'cumple' : 'no_cumple'
            const [Icon, label, color] = COMPLIANCE_STATES[state]
            return (
              <li key={check.code} className="flex items-start justify-between gap-3 text-sm">
                <span className="text-slate-700">{check.label}</span>
                <span className={`inline-flex shrink-0 items-center gap-1 text-xs font-medium ${color}`}>
                  <Icon className="size-4" aria-hidden />{label}
                </span>
              </li>
            )
          })}
        </ul>
      </Section>
      {a.secondary_topics.length > 0 && (
        <Section title="Temas secundarios">
          <ul className="flex flex-wrap gap-1.5">
            {a.secondary_topics.map((topic) => (
              <li key={topic} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">{topic}</li>
            ))}
          </ul>
        </Section>
      )}
      {a.entities.length > 0 && (
        <Section title="Entidades">
          <dl>{a.entities.map((e) => <Metric key={`${e.type}-${e.value}`} label={ENTITY_LABELS[e.type] ?? e.type}>{e.value}</Metric>)}</dl>
        </Section>
      )}
      {a.keywords.length > 0 && (
        <Section title="Palabras clave">
          <ul className="flex flex-wrap gap-1.5">
            {a.keywords.map((k) => <li key={k} className="rounded bg-amber-100 px-2 py-0.5 text-xs text-slate-800">{k}</li>)}
          </ul>
        </Section>
      )}
    </aside>
  )
}

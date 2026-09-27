import { CheckCircle2, CircleMinus, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ConversationDetail } from '../api/conversations'
import { useCatalog } from '../api/metrics'
import { formatDecimal } from '../lib/format'
import { ResolutionBadge, SentimentValue } from './badges'
import { CHURN_LABELS } from './labels'
import { SentimentTimeline } from './SentimentTimeline'

const ENTITY_LABELS: Record<string, string> = { importe: 'Importe', producto: 'Producto', fecha: 'Fecha', comercio: 'Comercio' }
const CHURN_STYLE: Record<string, string> = {
  bajo: 'text-[var(--status-good-text)]',
  medio: 'text-amber-700',
  alto: 'text-[var(--status-critical)]',
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-b border-slate-100 px-4 py-4 last:border-0">
      <h2 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h2>
      {children}
    </section>
  )
}

function Metric({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-800">{children}</dd>
    </div>
  )
}

interface Props {
  conversation: ConversationDetail
  activeTurn: number | null
  onSelectTurn: (turnIndex: number) => void
}

export function AnalysisPanel({ conversation, activeTurn, onSelectTurn }: Props) {
  const { data: catalog } = useCatalog()
  const a = conversation.analysis
  const checks = (catalog?.compliance_checks ?? []).filter((check) => check.code in a.compliance)

  return (
    <aside aria-label="Análisis" className="rounded-xl border border-slate-200 bg-white">
      <Section title="Resultado">
        <dl>
          <Metric label="Resolución"><ResolutionBadge resolution={a.resolution} /></Metric>
          <Metric label="CSAT predicho">{formatDecimal(a.csat, 1)} / 5</Metric>
          <Metric label="Esfuerzo del cliente">{formatDecimal(a.effort, 1)} / 5</Metric>
          <Metric label="Riesgo de abandono"><span className={CHURN_STYLE[a.churn_risk]}>{CHURN_LABELS[a.churn_risk]}</span></Metric>
          <Metric label="Sentimiento global"><SentimentValue value={a.sentiment} /></Metric>
        </dl>
      </Section>
      <Section title="Evolución del sentimiento">
        <SentimentTimeline turns={conversation.turns} activeTurn={activeTurn} onSelect={onSelectTurn} />
      </Section>
      <Section title="Cumplimiento">
        <ul aria-label="Cumplimiento" className="space-y-1.5">
          {checks.map((check) => {
            const value = a.compliance[check.code]
            const [Icon, label, color] = value === null
              ? [CircleMinus, 'No aplica', 'text-slate-400']
              : value ? [CheckCircle2, 'Cumple', 'text-[var(--status-good-text)]'] : [XCircle, 'No cumple', 'text-[var(--status-critical)]']
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
      <Section title="Temas secundarios">
        <ul className="flex flex-wrap gap-1.5">
          {a.secondary_topics.map((topic) => (
            <li key={topic} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">{topic}</li>
          ))}
        </ul>
      </Section>
      {a.entities.length > 0 && (
        <Section title="Entidades">
          <dl>{a.entities.map((e) => <Metric key={`${e.type}-${e.value}`} label={ENTITY_LABELS[e.type] ?? e.type}>{e.value}</Metric>)}</dl>
        </Section>
      )}
      <Section title="Palabras clave">
        <ul className="flex flex-wrap gap-1.5">
          {a.keywords.map((k) => <li key={k} className="rounded bg-amber-100 px-2 py-0.5 text-xs text-slate-800">{k}</li>)}
        </ul>
      </Section>
    </aside>
  )
}

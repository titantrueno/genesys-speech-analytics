import type { ReactNode } from 'react'
import { BreakdownBars, BreakdownTable, ChannelSplit, ComplianceChecks, KpiRow, TimeseriesWidget } from './widgets'

export interface DashboardDefinition {
  id: string
  title: string
  description: string
  render: () => ReactNode
}

export const DASHBOARDS: DashboardDefinition[] = [
  {
    id: 'vision-general',
    title: 'Visión general',
    description: 'Volumen, resolución y satisfacción de la atención al cliente.',
    render: () => (
      <>
        <KpiRow codes={['volume', 'aht_s', 'resolution_rate', 'escalation_rate', 'fcr_rate', 'csat_avg']} />
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <TimeseriesWidget kpi="volume" title="Volumen de conversaciones" />
          <BreakdownBars title="Distribución por main topic" dimension="main_topic" kpi="volume" subtitle="Conversaciones por motivo principal" />
          <div className="space-y-4">
            <ChannelSplit />
            <BreakdownBars title="Volumen por cola" dimension="queue" kpi="volume" />
          </div>
          <BreakdownTable title="KPIs por main topic" dimension="main_topic"
            codes={['volume', 'resolution_rate', 'escalation_rate', 'fcr_rate', 'csat_avg', 'sentiment_avg', 'aht_s']} />
        </div>
      </>
    ),
  },
  {
    id: 'calidad-y-cumplimiento',
    title: 'Calidad y cumplimiento',
    description: 'Checks de cumplimiento, resolución y escalado por cola y agente.',
    render: () => (
      <>
        <KpiRow codes={['compliance_rate', 'resolution_rate', 'escalation_rate', 'aht_s', 'avg_turns']} />
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <ComplianceChecks />
          <BreakdownBars title="Cumplimiento por cola" dimension="queue" kpi="compliance_rate" />
          <TimeseriesWidget kpi="compliance_rate" title="Evolución del cumplimiento" />
          <BreakdownTable title="Rendimiento por agente" dimension="agent"
            codes={['volume', 'compliance_rate', 'resolution_rate', 'escalation_rate', 'aht_s', 'csat_avg']} />
        </div>
      </>
    ),
  },
  {
    id: 'experiencia-de-cliente',
    title: 'Experiencia de cliente',
    description: 'Satisfacción, esfuerzo, sentimiento y riesgo de abandono.',
    render: () => (
      <>
        <KpiRow codes={['csat_avg', 'effort_avg', 'sentiment_avg', 'negative_pct', 'churn_high_pct', 'first_response_s']} />
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <TimeseriesWidget kpi="csat_avg" title="Evolución del CSAT predicho" />
          <BreakdownBars title="CSAT predicho por main topic" dimension="main_topic" kpi="csat_avg" order="asc"
            subtitle="De peor a mejor valorado" />
          <BreakdownBars title="Sentimiento medio por cola" dimension="queue" kpi="sentiment_avg" order="asc" diverging
            subtitle="Índice de -1 (negativo) a 1 (positivo)" />
        </div>
      </>
    ),
  },
]

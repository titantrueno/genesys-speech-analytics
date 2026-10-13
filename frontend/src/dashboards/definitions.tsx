import type { ReactNode } from 'react'
import type { TKey } from '../i18n/dictionaries'
import { DEFAULT_DASHBOARD_ID } from './DashboardsIndex'
import { BreakdownBars, BreakdownTable, ChannelSplit, ComplianceChecks, KpiRow, TimeseriesWidget } from './widgets'

export interface DashboardDefinition {
  id: string
  titleKey: TKey
  descriptionKey: TKey
  render: () => ReactNode
}

export const DASHBOARDS: DashboardDefinition[] = [
  {
    id: DEFAULT_DASHBOARD_ID,
    titleKey: 'dash.overview.title',
    descriptionKey: 'dash.overview.description',
    render: () => (
      <>
        <KpiRow dashboard={DEFAULT_DASHBOARD_ID} codes={['volume', 'aht_s', 'resolution_rate', 'escalation_rate', 'fcr_rate', 'csat_avg']} />
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <TimeseriesWidget kpi="volume" titleKey="dash.w.volume" />
          <BreakdownBars titleKey="dash.w.topicDistribution" dimension="main_topic" kpi="volume" subtitleKey="dash.w.topicSubtitle" />
          <div className="space-y-4">
            <ChannelSplit />
            <BreakdownBars titleKey="dash.w.volumeByQueue" dimension="queue" kpi="volume" />
          </div>
          <BreakdownTable titleKey="dash.w.kpisByTopic" dimension="main_topic"
            codes={['volume', 'resolution_rate', 'escalation_rate', 'fcr_rate', 'csat_avg', 'sentiment_avg', 'aht_s']} />
        </div>
      </>
    ),
  },
  {
    id: 'calidad-y-cumplimiento',
    titleKey: 'dash.quality.title',
    descriptionKey: 'dash.quality.description',
    render: () => (
      <>
        <KpiRow dashboard="calidad-y-cumplimiento" codes={['compliance_rate', 'resolution_rate', 'escalation_rate', 'aht_s', 'avg_turns']} />
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <ComplianceChecks />
          <BreakdownBars titleKey="dash.w.complianceByQueue" dimension="queue" kpi="compliance_rate" />
          <TimeseriesWidget kpi="compliance_rate" titleKey="dash.w.complianceTrend" />
          <BreakdownTable titleKey="dash.w.agentPerformance" dimension="agent"
            codes={['volume', 'compliance_rate', 'resolution_rate', 'escalation_rate', 'aht_s', 'csat_avg']} />
        </div>
      </>
    ),
  },
  {
    id: 'experiencia-de-cliente',
    titleKey: 'dash.experience.title',
    descriptionKey: 'dash.experience.description',
    render: () => (
      <>
        <KpiRow dashboard="experiencia-de-cliente" codes={['csat_avg', 'effort_avg', 'sentiment_avg', 'negative_pct', 'churn_high_pct', 'first_response_s']} />
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <TimeseriesWidget kpi="csat_avg" titleKey="dash.w.csatTrend" />
          <BreakdownBars titleKey="dash.w.csatByTopic" dimension="main_topic" kpi="csat_avg" order="asc"
            subtitleKey="dash.w.worstToBest" />
          <BreakdownBars titleKey="dash.w.sentimentByQueue" dimension="queue" kpi="sentiment_avg" order="asc" diverging
            subtitleKey="dash.w.sentimentScale" />
        </div>
      </>
    ),
  },
]

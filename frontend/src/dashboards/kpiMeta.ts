import type { KpiCode, KpiUnit } from '../api/metrics'
import type { TKey } from '../i18n/dictionaries'

export const KPI_META: Record<KpiCode, { short: TKey; unit: KpiUnit }> = {
  volume: { short: 'kpi.volume.short', unit: 'conversaciones' },
  aht_s: { short: 'kpi.aht_s.short', unit: 's' },
  sentiment_avg: { short: 'kpi.sentiment_avg.short', unit: 'índice' },
  negative_pct: { short: 'kpi.negative_pct.short', unit: '%' },
  resolution_rate: { short: 'kpi.resolution_rate.short', unit: '%' },
  escalation_rate: { short: 'kpi.escalation_rate.short', unit: '%' },
  fcr_rate: { short: 'kpi.fcr_rate.short', unit: '%' },
  csat_avg: { short: 'kpi.csat_avg.short', unit: '1-5' },
  effort_avg: { short: 'kpi.effort_avg.short', unit: '1-5' },
  compliance_rate: { short: 'kpi.compliance_rate.short', unit: '%' },
  churn_high_pct: { short: 'kpi.churn_high_pct.short', unit: '%' },
  first_response_s: { short: 'kpi.first_response_s.short', unit: 's' },
  avg_turns: { short: 'kpi.avg_turns.short', unit: 'turnos' },
}

/** KPIs que dependen del análisis de la plataforma: pendientes con conversaciones reales sin analizar (FE012). */
export const ANALYSIS_KPIS: ReadonlySet<KpiCode> = new Set<KpiCode>([
  'resolution_rate', 'escalation_rate', 'fcr_rate', 'csat_avg', 'effort_avg', 'compliance_rate', 'churn_high_pct',
])

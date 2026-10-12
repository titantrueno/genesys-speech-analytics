import type { KpiCode, KpiUnit } from '../api/metrics'

export const KPI_META: Record<KpiCode, { short: string; unit: KpiUnit }> = {
  volume: { short: 'Volumen', unit: 'conversaciones' },
  aht_s: { short: 'AHT', unit: 's' },
  sentiment_avg: { short: 'Sentimiento', unit: 'índice' },
  negative_pct: { short: '% negativas', unit: '%' },
  resolution_rate: { short: 'Resolución', unit: '%' },
  escalation_rate: { short: 'Escalado', unit: '%' },
  fcr_rate: { short: 'FCR', unit: '%' },
  csat_avg: { short: 'CSAT', unit: '1-5' },
  effort_avg: { short: 'Esfuerzo', unit: '1-5' },
  compliance_rate: { short: 'Cumplimiento', unit: '%' },
  churn_high_pct: { short: 'Riesgo alto', unit: '%' },
  first_response_s: { short: '1.ª respuesta', unit: 's' },
  avg_turns: { short: 'Turnos', unit: 'turnos' },
}

/** KPIs que dependen del análisis de la plataforma: pendientes con conversaciones reales sin analizar (FE012). */
export const ANALYSIS_KPIS: ReadonlySet<KpiCode> = new Set<KpiCode>([
  'resolution_rate', 'escalation_rate', 'fcr_rate', 'csat_avg', 'effort_avg', 'compliance_rate', 'churn_high_pct',
])

export const PENDING_KPI_TEXT = 'Sin datos · pendiente de análisis'

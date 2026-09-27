import type { Dimension, KpiCode, MetricsFilters } from '../api/metrics'

type DrillParams = Record<string, string | string[] | undefined>

/** Filtro que selecciona las conversaciones que forman el numerador de cada KPI, para que el listado cuente lo mismo que el elemento pulsado. */
export const KPI_DRILL: Record<KpiCode, DrillParams> = {
  volume: {},
  aht_s: {},
  sentiment_avg: {},
  negative_pct: { sentiment_lt: '-0.3' },
  resolution_rate: { resolution: 'resuelta' },
  escalation_rate: { resolution: 'escalada' },
  fcr_rate: { repeat_contact: 'false' },
  csat_avg: {},
  effort_avg: {},
  compliance_rate: { compliant: 'true' },
  churn_high_pct: { churn_risk: 'alto' },
  first_response_s: { channel: 'chat' },
  avg_turns: {},
}

export function drillDownHref(filters: MetricsFilters, ...extras: DrillParams[]): string {
  const merged: DrillParams = { ...filters }
  for (const extra of extras) Object.assign(merged, extra)
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(merged)) {
    for (const item of Array.isArray(value) ? value : [value]) if (item) params.append(key, item)
  }
  const query = params.toString()
  return `/conversaciones${query ? `?${query}` : ''}`
}

export function dimensionDrill(dimension: Dimension, key: string): DrillParams {
  return { [dimension]: key }
}

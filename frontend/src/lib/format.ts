import type { KpiSummary, KpiUnit } from '../api/metrics'

const LOCALE = 'es-ES'
const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0, useGrouping: 'always' })
const oneDecimal = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1, useGrouping: 'always' })
const twoDecimals = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const signedTwo = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero' })
const signedOne = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })
const shortDate = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short', timeZone: 'UTC' })

export const EMPTY_VALUE = '—'

export function formatDuration(seconds: number): string {
  const rounded = Math.round(seconds)
  if (rounded < 60) return `${rounded} s`
  const minutes = Math.floor(rounded / 60)
  return `${minutes}:${String(rounded % 60).padStart(2, '0')} min`
}

export function formatInteger(value: number): string {
  return integer.format(value)
}

export function formatKpi(value: number | null | undefined, unit: KpiUnit): string {
  if (value === null || value === undefined) return EMPTY_VALUE
  switch (unit) {
    case 'conversaciones': return integer.format(value)
    case 's': return formatDuration(value)
    case '%': return `${oneDecimal.format(value)} %`
    case 'índice': return signedTwo.format(value)
    case '1-5': return twoDecimals.format(value)
    case 'turnos': return oneDecimal.format(value)
  }
}

export function formatDelta(kpi: Pick<KpiSummary, 'delta' | 'delta_pct' | 'unit'>): string | null {
  if (kpi.delta_pct !== null) return `${signedOne.format(kpi.delta_pct)} %`
  if (kpi.delta === null) return null
  return kpi.unit === 'índice' || kpi.unit === '1-5' ? signedTwo.format(kpi.delta) : signedOne.format(kpi.delta)
}

export type Trend = 'mejora' | 'empeora' | 'estable'

export function trendOf(kpi: Pick<KpiSummary, 'delta' | 'higher_is_better'>): Trend | null {
  if (kpi.delta === null) return null
  if (kpi.delta === 0) return 'estable'
  return (kpi.delta > 0) === kpi.higher_is_better ? 'mejora' : 'empeora'
}

export function formatShortDate(iso: string): string {
  return shortDate.format(new Date(`${iso}T00:00:00Z`))
}

export function formatOffset(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

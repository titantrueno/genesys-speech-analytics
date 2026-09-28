import type { KpiSummary, KpiUnit } from '../api/metrics'

const LOCALE = 'es-ES'
const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0, useGrouping: 'always' })
const oneDecimal = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1, useGrouping: 'always' })
const twoDecimals = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const signedTwo = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero' })
const signedOne = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })
const shortDate = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short', timeZone: 'UTC' })

/**
 * Zona horaria de la plataforma (Configuración › General). Sin configurar, la del navegador.
 * La fija `AppLayout` con `GET /api/config/public`; todas las fechas con hora se formatean aquí (FE005).
 */
let displayZone: string | undefined
const formatters = new Map<string, Intl.DateTimeFormat>()

export function setDisplayTimeZone(zone: string | undefined) {
  displayZone = zone
}

function dateTimeFormat(kind: 'short' | 'year' | 'long'): Intl.DateTimeFormat {
  const key = `${kind}|${displayZone ?? ''}`
  let format = formatters.get(key)
  if (!format) {
    const options: Intl.DateTimeFormatOptions = {
      short: { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' } as const,
      year: { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' } as const,
      long: { dateStyle: 'long', timeStyle: 'short' } as const,
    }[kind]
    format = new Intl.DateTimeFormat(LOCALE, { ...options, timeZone: displayZone })
    formatters.set(key, format)
  }
  return format
}

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

export function shortId(id: string): string {
  return id.slice(0, 12)
}

export function formatDecimal(value: number, digits: 1 | 2): string {
  return (digits === 1 ? oneDecimal : twoDecimals).format(value)
}

export function formatSigned(value: number): string {
  return signedTwo.format(value)
}

/** Fecha y hora en la zona de la plataforma («27 sept, 10:30»). */
export function formatDateTime(iso: string): string {
  return dateTimeFormat('short').format(new Date(iso))
}

/** Con año («27 sept 2026, 10:30»), para resultados que pueden ser de otro año. */
export function formatDateTimeWithYear(iso: string): string {
  return dateTimeFormat('year').format(new Date(iso))
}

/** Larga («27 de septiembre de 2026, 10:30»), para la cabecera del detalle. */
export function formatDateTimeLong(iso: string): string {
  return dateTimeFormat('long').format(new Date(iso))
}

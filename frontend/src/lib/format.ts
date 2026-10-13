import type { KpiSummary, KpiUnit } from '../api/metrics'

/**
 * Idioma de los números y las fechas (FE016). Lo fija `I18nProvider` durante el render, igual que la zona horaria;
 * los formateadores se crean una vez por idioma.
 */
let locale = 'es-ES'

export function setDisplayLocale(next: string) {
  locale = next
}

interface NumberFormats {
  integer: Intl.NumberFormat
  oneDecimal: Intl.NumberFormat
  twoDecimals: Intl.NumberFormat
  signedTwo: Intl.NumberFormat
  signedOne: Intl.NumberFormat
  upToOneDecimal: Intl.NumberFormat
  shortDate: Intl.DateTimeFormat
  /** Español: «12,3 %» con espacio; inglés: «12.3%». */
  percent: string
}

const numberFormats = new Map<string, NumberFormats>()

function formats(): NumberFormats {
  let cached = numberFormats.get(locale)
  if (!cached) {
    const decimals = (digits: number, extra: Intl.NumberFormatOptions = {}) =>
      new Intl.NumberFormat(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits, ...extra })
    cached = {
      integer: new Intl.NumberFormat(locale, { maximumFractionDigits: 0, useGrouping: 'always' }),
      oneDecimal: decimals(1, { useGrouping: 'always' }),
      twoDecimals: decimals(2),
      signedTwo: decimals(2, { signDisplay: 'exceptZero' }),
      signedOne: decimals(1, { signDisplay: 'exceptZero' }),
      upToOneDecimal: new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }),
      shortDate: new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', timeZone: 'UTC' }),
      percent: locale.startsWith('es') ? ' %' : '%',
    }
    numberFormats.set(locale, cached)
  }
  return cached
}

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
  const key = `${locale}|${kind}|${displayZone ?? ''}`
  let format = formatters.get(key)
  if (!format) {
    const options: Intl.DateTimeFormatOptions = {
      short: { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' } as const,
      year: { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' } as const,
      long: { dateStyle: 'long', timeStyle: 'short' } as const,
    }[kind]
    format = new Intl.DateTimeFormat(locale, { ...options, timeZone: displayZone })
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
  return formats().integer.format(value)
}

export function formatKpi(value: number | null | undefined, unit: KpiUnit): string {
  if (value === null || value === undefined) return EMPTY_VALUE
  switch (unit) {
    case 'conversaciones': return formats().integer.format(value)
    case 's': return formatDuration(value)
    case '%': return `${formats().oneDecimal.format(value)}${formats().percent}`
    case 'índice': return formats().signedTwo.format(value)
    case '1-5': return formats().twoDecimals.format(value)
    case 'turnos': return formats().oneDecimal.format(value)
  }
}

export function formatDelta(kpi: Pick<KpiSummary, 'delta' | 'delta_pct' | 'unit'>): string | null {
  if (kpi.delta_pct !== null) return `${formats().signedOne.format(kpi.delta_pct)}${formats().percent}`
  if (kpi.delta === null) return null
  return kpi.unit === 'índice' || kpi.unit === '1-5' ? formats().signedTwo.format(kpi.delta) : formats().signedOne.format(kpi.delta)
}

export type Trend = 'mejora' | 'empeora' | 'estable'

export function trendOf(kpi: Pick<KpiSummary, 'delta' | 'higher_is_better'>): Trend | null {
  if (kpi.delta === null) return null
  if (kpi.delta === 0) return 'estable'
  return (kpi.delta > 0) === kpi.higher_is_better ? 'mejora' : 'empeora'
}

export function formatShortDate(iso: string): string {
  return formats().shortDate.format(new Date(`${iso}T00:00:00Z`))
}

export function formatOffset(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export function shortId(id: string): string {
  return id.slice(0, 12)
}

export function formatDecimal(value: number, digits: 1 | 2): string {
  return (digits === 1 ? formats().oneDecimal : formats().twoDecimals).format(value)
}

/** Porcentaje sin decimales («50 %» en español, «50%» en inglés). */
export function formatPercentWhole(value: number): string {
  return `${formats().integer.format(Math.round(value))}${formats().percent}`
}

/** Hasta un decimal, sin ceros finales («2,5», «3»). */
export function formatUpToOneDecimal(value: number): string {
  return formats().upToOneDecimal.format(value)
}

export function formatSigned(value: number): string {
  return formats().signedTwo.format(value)
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

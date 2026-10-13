import type { Translate } from '../i18n/context'
import type { TKey } from '../i18n/dictionaries'
import { formatInteger, formatUpToOneDecimal } from '../lib/format'
import type { DownloadInterval, DownloadRunStatus, DownloadSchedule, LogLevel, RelativeUnit } from './types'

export const DOWNLOAD_STATUS: Record<DownloadRunStatus, { label: TKey; className: string }> = {
  pendiente: { label: 'dl.status.pendiente', className: 'bg-slate-100 text-slate-600' },
  en_curso: { label: 'dl.status.en_curso', className: 'bg-brand-50 text-brand-700' },
  completada: { label: 'dl.status.completada', className: 'bg-green-50 text-[var(--status-good-text)]' },
  completada_con_avisos: { label: 'dl.status.completada_con_avisos', className: 'bg-amber-50 text-amber-800' },
  error: { label: 'dl.status.error', className: 'bg-red-50 text-[var(--status-critical)]' },
}

export const UNIT_KEYS: Record<RelativeUnit, TKey> = {
  hoy: 'dl.unit.hoy', ayer: 'dl.unit.ayer', horas: 'dl.unit.horas', dias: 'dl.unit.dias',
}

export const SCHEDULE_KEYS: Record<DownloadSchedule['type'], TKey> = {
  desactivada: 'dl.schedule.desactivada', cada_horas: 'dl.schedule.cada_horas', diaria: 'dl.schedule.diaria',
}

export const LEVEL_KEYS: Record<LogLevel, TKey> = { info: 'dl.level.info', aviso: 'dl.level.aviso', error: 'dl.level.error' }

export const ORIGIN_KEYS = { manual: 'dl.origin.manual', programada: 'dl.origin.programada' } as const

export const CHANNEL_KEYS = { voz: 'domain.channel.voz', chat: 'domain.channel.chat' } as const

export const QUALITY_KEYS = {
  completa: 'conv.quality.completa', parcial: 'conv.quality.parcial', sin_transcripcion: 'conv.quality.sin_transcripcion',
} as const

/** «Voz 3 · Chat 2»: un recuento por cada clave conocida, en el orden de `keys`. */
export function splitCounts(t: Translate, values: Record<string, number>, keys: Record<string, TKey>): string {
  return Object.entries(keys).map(([key, label]) => `${t(label)} ${formatInteger(values[key] ?? 0)}`).join(' · ')
}

export function describeInterval(t: Translate, interval: DownloadInterval): string {
  if (interval.type === 'especifico') return t('dl.interval.specific')
  if (interval.unit === 'horas') return t('dl.interval.lastHours', { n: interval.amount ?? '' })
  if (interval.unit === 'dias') return t('dl.interval.lastDays', { n: interval.amount ?? '' })
  return t(interval.unit === 'ayer' ? 'dl.unit.ayer' : 'dl.unit.hoy')
}

export function describeSchedule(t: Translate, schedule: DownloadSchedule): string {
  if (schedule.type === 'cada_horas') return schedule.hours === 1 ? t('dl.schedule.hourly') : t('dl.schedule.everyHours', { n: schedule.hours ?? '' })
  if (schedule.type === 'diaria') return t('dl.schedule.dailyAt', { time: schedule.time ?? '' })
  return t('dl.schedule.desactivada')
}

export function formatSeconds(seconds: number | null): string {
  if (seconds === null) return '—'
  return `${formatUpToOneDecimal(seconds)} s`
}

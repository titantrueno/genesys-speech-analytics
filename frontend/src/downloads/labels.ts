import type { DownloadInterval, DownloadRunStatus, DownloadSchedule, LogLevel, RelativeUnit } from './types'

export const DOWNLOAD_STATUS: Record<DownloadRunStatus, { label: string; className: string }> = {
  pendiente: { label: 'Pendiente', className: 'bg-slate-100 text-slate-600' },
  en_curso: { label: 'En curso', className: 'bg-brand-50 text-brand-700' },
  completada: { label: 'Completada', className: 'bg-green-50 text-[var(--status-good-text)]' },
  completada_con_avisos: { label: 'Con avisos', className: 'bg-amber-50 text-amber-800' },
  error: { label: 'Error', className: 'bg-red-50 text-[var(--status-critical)]' },
}

export const UNIT_LABELS: Record<RelativeUnit, string> = {
  hoy: 'Hoy', ayer: 'Ayer', horas: 'Últimas horas', dias: 'Últimos días',
}

export const SCHEDULE_LABELS: Record<DownloadSchedule['type'], string> = {
  desactivada: 'Solo manual', cada_horas: 'Cada N horas', diaria: 'Diaria',
}

export const LEVEL_LABELS: Record<LogLevel, string> = { info: 'Información', aviso: 'Aviso', error: 'Error' }

export const ORIGIN_LABELS = { manual: 'Manual', programada: 'Programada' } as const

export const CHANNEL_LABELS = { voz: 'Voz', chat: 'Chat' } as const

export const QUALITY_LABELS: Record<string, string> = {
  completa: 'Completa', parcial: 'Parcial', sin_transcripcion: 'Sin transcripción',
}

export function describeInterval(interval: DownloadInterval): string {
  if (interval.type === 'especifico') return 'Intervalo específico'
  if (interval.unit === 'horas') return `Últimas ${interval.amount} horas`
  if (interval.unit === 'dias') return `Últimos ${interval.amount} días`
  return interval.unit === 'ayer' ? 'Ayer' : 'Hoy'
}

export function describeSchedule(schedule: DownloadSchedule): string {
  if (schedule.type === 'cada_horas') return schedule.hours === 1 ? 'Cada hora' : `Cada ${schedule.hours} horas`
  if (schedule.type === 'diaria') return `Diaria a las ${schedule.time}`
  return 'Solo manual'
}

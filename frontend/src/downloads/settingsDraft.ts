import type { DownloadChannel, DownloadInterval, DownloadSchedule, RelativeUnit } from './types'

/**
 * Intervalo, canales, programación, activo y «Sobrescribir» de una descarga. Los comparten el formulario de un flujo de
 * descarga (FE011) y el panel de la caja «Genesys download» de un flujo de insights (FE017).
 */
export interface SettingsDraft {
  intervalType: 'relativo' | 'especifico'
  unit: RelativeUnit
  amount: string
  from: string
  to: string
  channels: DownloadChannel[]
  scheduleType: 'desactivada' | 'cada_horas' | 'diaria'
  hours: string
  time: string
  active: boolean
  overwrite: boolean
}

export function settingsDraft(value: {
  interval?: DownloadInterval; channels?: DownloadChannel[]; schedule?: DownloadSchedule; active?: boolean; overwrite?: boolean
}): SettingsDraft {
  const { interval, schedule } = value
  return {
    intervalType: interval?.type ?? 'relativo',
    unit: interval?.unit ?? 'hoy',
    amount: interval?.amount ? String(interval.amount) : '',
    from: interval?.from ?? '',
    to: interval?.to ?? '',
    channels: value.channels ?? [],
    scheduleType: schedule?.type ?? 'desactivada',
    hours: schedule?.hours ? String(schedule.hours) : '',
    time: schedule?.time ?? '',
    active: value.active ?? true,
    overwrite: value.overwrite ?? false,
  }
}

/** Con `partial`, un intervalo a medio escribir es `undefined` (la caja queda «sin configurar») en vez de un valor no válido. */
export function draftInterval(draft: SettingsDraft, partial = false): DownloadInterval | undefined {
  if (draft.intervalType === 'especifico') {
    return partial && !(draft.from && draft.to) ? undefined : { type: 'especifico', from: draft.from, to: draft.to }
  }
  if (draft.unit === 'horas' || draft.unit === 'dias') {
    return partial && !draft.amount ? undefined : { type: 'relativo', unit: draft.unit, amount: Number(draft.amount) }
  }
  return { type: 'relativo', unit: draft.unit }
}

export function draftSchedule(draft: SettingsDraft, partial = false): DownloadSchedule | undefined {
  if (draft.scheduleType === 'cada_horas') {
    return partial && !draft.hours ? undefined : { type: 'cada_horas', hours: Number(draft.hours) }
  }
  if (draft.scheduleType === 'diaria') return partial && !draft.time ? undefined : { type: 'diaria', time: draft.time }
  return { type: 'desactivada' }
}

export const scheduleConflict = (draft: SettingsDraft) => draft.intervalType === 'especifico' && draft.scheduleType !== 'desactivada'

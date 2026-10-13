import { useId } from 'react'
import { errorFor } from '../config/api'
import { ConfigField, input } from '../config/controls'
import { useI18n } from '../i18n/useI18n'
import { SCHEDULE_KEYS, UNIT_KEYS } from './labels'
import { scheduleConflict, type SettingsDraft } from './settingsDraft'
import type { DownloadChannel, RelativeUnit } from './types'

/** Campos de una descarga; los comparten el flujo de descarga (FE011) y la caja «Genesys download» (FE017). */
export function DownloadSettingsFields({ draft, set, disabled, errors, timezone }: {
  draft: SettingsDraft
  set: <K extends keyof SettingsDraft>(key: K, value: SettingsDraft[K]) => void
  disabled: boolean
  /** Errores del backend (`422`) por campo. */
  errors: Record<string, string>
  timezone: string
}) {
  const { t } = useI18n()
  const radioName = useId()
  const intervalError = errorFor(errors, 'interval')
  const scheduleError = scheduleConflict(draft) ? t('dl.form.scheduledNeedsRelative') : errorFor(errors, 'schedule')
  // Siempre en el orden voz, chat: desmarcar y volver a marcar un canal no cuenta como cambio.
  const toggleChannel = (channel: DownloadChannel) => set('channels', draft.channels.includes(channel)
    ? draft.channels.filter((c) => c !== channel)
    : (['voz', 'chat'] as const).filter((c) => c === channel || draft.channels.includes(c)))

  return (
    <>
      <fieldset className="space-y-3">
        <legend className="text-xs font-medium text-slate-600">{t('dl.form.interval')}</legend>
        <div className="flex gap-4 text-sm">
          {(['relativo', 'especifico'] as const).map((type) => (
            <label key={type} className="inline-flex items-center gap-1.5">
              <input type="radio" name={radioName} checked={draft.intervalType === type} disabled={disabled}
                onChange={() => set('intervalType', type)} />
              {type === 'relativo' ? t('dl.form.relative') : t('dl.form.specific')}
            </label>
          ))}
        </div>
        {draft.intervalType === 'relativo' ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <ConfigField label={t('dl.form.period')} error={draft.unit === 'hoy' || draft.unit === 'ayer' ? intervalError : undefined}>
              <select className={input} value={draft.unit} disabled={disabled}
                onChange={(e) => set('unit', e.target.value as RelativeUnit)}>
                {Object.entries(UNIT_KEYS).map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}
              </select>
            </ConfigField>
            {(draft.unit === 'horas' || draft.unit === 'dias') && (
              <ConfigField label={t('dl.form.amount')} error={intervalError}
                hint={draft.unit === 'horas' ? t('dl.form.hoursRange') : t('dl.form.daysRange')}>
                <input type="number" className={input} value={draft.amount} disabled={disabled}
                  onChange={(e) => set('amount', e.target.value)} />
              </ConfigField>
            )}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <ConfigField label={t('dl.form.from')} error={errors['interval.from'] ?? (errors['interval.to'] ? undefined : intervalError)}>
              <input type="datetime-local" className={input} value={draft.from} disabled={disabled}
                onChange={(e) => set('from', e.target.value)} />
            </ConfigField>
            <ConfigField label={t('dl.form.to')} error={errors['interval.to']}>
              <input type="datetime-local" className={input} value={draft.to} disabled={disabled}
                onChange={(e) => set('to', e.target.value)} />
            </ConfigField>
          </div>
        )}
        <p className="text-xs text-slate-500">
          {t('dl.form.timezoneNote', { zone: timezone })}
        </p>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-xs font-medium text-slate-600">{t('dl.form.channels')}</legend>
        <div className="flex gap-4 text-sm">
          {(['voz', 'chat'] as const).map((channel) => (
            <label key={channel} className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={draft.channels.includes(channel)} disabled={disabled}
                onChange={() => toggleChannel(channel)} />
              {t(channel === 'voz' ? 'domain.channel.voz' : 'domain.channel.chat')}
            </label>
          ))}
        </div>
        {errorFor(errors, 'channels') && <p className="text-xs text-red-700">{errorFor(errors, 'channels')}</p>}
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-2">
        <ConfigField label={t('dl.form.schedule')} error={scheduleError}>
          <select className={input} value={draft.scheduleType} disabled={disabled}
            onChange={(e) => set('scheduleType', e.target.value as SettingsDraft['scheduleType'])}>
            {Object.entries(SCHEDULE_KEYS).map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}
          </select>
        </ConfigField>
        {draft.scheduleType === 'cada_horas' && (
          <ConfigField label={t('dl.form.everyHours')} hint={t('dl.form.everyHoursHint')}>
            <input type="number" className={input} value={draft.hours} disabled={disabled}
              onChange={(e) => set('hours', e.target.value)} />
          </ConfigField>
        )}
        {draft.scheduleType === 'diaria' && (
          <ConfigField label={t('dl.form.time')}>
            <input type="time" className={input} value={draft.time} disabled={disabled}
              onChange={(e) => set('time', e.target.value)} />
          </ConfigField>
        )}
      </div>

      <label className="inline-flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={draft.active} disabled={disabled} onChange={(e) => set('active', e.target.checked)} />
        {t('dl.form.active')}
      </label>

      <div>
        <label className="inline-flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={draft.overwrite} disabled={disabled} aria-describedby={`${radioName}-overwrite`}
            onChange={(e) => set('overwrite', e.target.checked)} />
          {t('dl.form.overwrite')}
        </label>
        <p id={`${radioName}-overwrite`} className="ml-6 text-xs text-slate-500">
          {t('dl.form.overwriteHint')}
        </p>
      </div>
    </>
  )
}

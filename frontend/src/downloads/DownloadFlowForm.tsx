import { useState } from 'react'
import { errorFor, fieldErrors } from '../config/api'
import { ConfigField, input } from '../config/controls'
import { useI18n } from '../i18n/useI18n'
import { DownloadSettingsFields } from './DownloadSettingsFields'
import { draftInterval, draftSchedule, scheduleConflict, settingsDraft, type SettingsDraft } from './settingsDraft'
import type { DownloadFlow, DownloadFlowInput } from './types'

interface Draft extends SettingsDraft {
  name: string
}

function toDraft(flow: DownloadFlow): Draft {
  return { name: flow.name, ...settingsDraft(flow) }
}

function toInput(draft: Draft): DownloadFlowInput {
  return { name: draft.name, interval: draftInterval(draft)!, channels: draft.channels, schedule: draftSchedule(draft)!,
    active: draft.active, overwrite: draft.overwrite }
}

/** Formulario de un flujo de descarga; los errores del backend (`422`) se muestran junto a su campo. */
export function DownloadFlowForm({ flow, canEdit, pending, error, saved, onSave }: {
  flow: DownloadFlow; canEdit: boolean; pending: boolean; error: unknown; saved: boolean
  onSave: (input: DownloadFlowInput) => void
}) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<Draft>(() => toDraft(flow))
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }))
  const setSetting = <K extends keyof SettingsDraft>(key: K, value: SettingsDraft[K]) => set(key, value as Draft[K])
  const errors = fieldErrors(error)
  const disabled = !canEdit
  const dirty = JSON.stringify(toInput(draft)) !== JSON.stringify(toInput(toDraft(flow)))

  return (
    <form className="space-y-5" onSubmit={(event) => { event.preventDefault(); onSave(toInput(draft)) }}>
      <ConfigField label={t('dl.form.name')} error={errorFor(errors, 'name')}>
        <input className={input} value={draft.name} maxLength={80} disabled={disabled}
          onChange={(e) => set('name', e.target.value)} />
      </ConfigField>

      <DownloadSettingsFields draft={draft} set={setSetting} disabled={disabled} errors={errors} timezone={flow.timezone} />

      {canEdit && (
        <div className="flex items-center gap-3">
          <button type="submit" disabled={!dirty || pending || scheduleConflict(draft)}
            className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50">
            {t('dl.form.save')}
          </button>
          {saved && !dirty && <p role="status" className="text-sm text-emerald-700">{t('dl.form.saved')}</p>}
          {error !== null && error !== undefined && <p role="alert" className="text-sm text-red-700">
            {Object.keys(errors).length ? t('dl.form.reviewFields') : t('dl.form.saveError')}
          </p>}
        </div>
      )}
    </form>
  )
}

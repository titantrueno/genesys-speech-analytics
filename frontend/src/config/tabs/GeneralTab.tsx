import { useI18n } from '../../i18n/useI18n'
import { configRequests } from '../api'
import { Card, ConfigField, input, SaveBar } from '../controls'
import type { GeneralConfig, PlatformConfig } from '../types'
import { useSectionForm } from '../useSectionForm'

export function GeneralTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const { t } = useI18n()
  const form = useSectionForm<GeneralConfig>(config.general, configRequests.general)
  return (
    <Card title={t('cfg.tab.general')} description={t('cfg.general.description')}>
      <fieldset disabled={!canEdit} className="grid gap-4 sm:grid-cols-2">
        <ConfigField label={t('cfg.general.name')} error={form.errors.platform_name}
          hint={t('cfg.general.nameHint')}>
          <input className={input} value={form.draft.platform_name} maxLength={80}
            onChange={(e) => form.set('platform_name', e.target.value)} />
        </ConfigField>
        <ConfigField label={t('cfg.general.timezone')} error={form.errors.timezone}
          hint={t('cfg.general.timezoneHint')}>
          <select className={input} value={form.draft.timezone} onChange={(e) => form.set('timezone', e.target.value)}>
            {config.options.timezones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}
          </select>
        </ConfigField>
        <ConfigField label={t('cfg.general.language')} error={form.errors.language} hint={t('cfg.general.languageHint')}>
          <select className={input} value={form.draft.language} onChange={(e) => form.set('language', e.target.value)}>
            {config.options.languages.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </ConfigField>
      </fieldset>
      {canEdit && <SaveBar {...form.bar} />}
    </Card>
  )
}

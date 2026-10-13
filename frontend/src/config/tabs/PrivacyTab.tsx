import { useI18n } from '../../i18n/useI18n'
import { configRequests } from '../api'
import { Card, SaveBar } from '../controls'
import type { PlatformConfig, PrivacyConfig } from '../types'
import { useSectionForm } from '../useSectionForm'

export function PrivacyTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const { t } = useI18n()
  const form = useSectionForm<PrivacyConfig>(config.privacy, configRequests.privacy)
  return (
    <Card title={t('cfg.privacy.title')} description={t('cfg.privacy.description')}>
      <fieldset disabled={!canEdit} className="space-y-2">
        <label className="flex items-start gap-3 text-sm text-slate-700">
          <input type="checkbox" className="mt-0.5 size-4" checked={form.draft.pii_masking}
            onChange={(e) => form.set('pii_masking', e.target.checked)} />
          <span>
            <span className="font-medium">{t('cfg.privacy.label')}</span>
            <span className="block text-slate-500">
              {t('cfg.privacy.hint')}
            </span>
          </span>
        </label>
      </fieldset>
      <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
        {t('cfg.privacy.note')}
      </p>
      {form.errors.pii_masking && <p className="text-xs text-red-700">{form.errors.pii_masking}</p>}
      {canEdit && <SaveBar {...form.bar} />}
    </Card>
  )
}

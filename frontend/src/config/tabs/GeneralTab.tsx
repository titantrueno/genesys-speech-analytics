import { configRequests } from '../api'
import { Card, ConfigField, input, SaveBar } from '../controls'
import type { GeneralConfig, PlatformConfig } from '../types'
import { useSectionForm } from '../useSectionForm'

export function GeneralTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const form = useSectionForm<GeneralConfig>(config.general, configRequests.general)
  return (
    <Card title="General" description="Nombre, zona horaria e idioma de la plataforma.">
      <fieldset disabled={!canEdit} className="grid gap-4 sm:grid-cols-2">
        <ConfigField label="Nombre de la plataforma" error={form.errors.platform_name}
          hint="Aparece en la cabecera y en la pantalla de acceso.">
          <input className={input} value={form.draft.platform_name} maxLength={80}
            onChange={(e) => form.set('platform_name', e.target.value)} />
        </ConfigField>
        <ConfigField label="Zona horaria" error={form.errors.timezone}
          hint="Las fechas y los días de filtros, gráficos y listados se calculan en esta zona.">
          <select className={input} value={form.draft.timezone} onChange={(e) => form.set('timezone', e.target.value)}>
            {config.options.timezones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}
          </select>
        </ConfigField>
        <ConfigField label="Idioma por defecto" error={form.errors.language}>
          <select className={input} value={form.draft.language} onChange={(e) => form.set('language', e.target.value)}>
            {config.options.languages.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </ConfigField>
      </fieldset>
      {canEdit && <SaveBar {...form.bar} />}
    </Card>
  )
}

import { configRequests } from '../api'
import { Card, SaveBar } from '../controls'
import type { PlatformConfig, PrivacyConfig } from '../types'
import { useSectionForm } from '../useSectionForm'

export function PrivacyTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const form = useSectionForm<PrivacyConfig>(config.privacy, configRequests.privacy)
  return (
    <Card title="Privacidad" description="Enmascarado de datos personales detectados por patrones.">
      <fieldset disabled={!canEdit} className="space-y-2">
        <label className="flex items-start gap-3 text-sm text-slate-700">
          <input type="checkbox" className="mt-0.5 size-4" checked={form.draft.pii_masking}
            onChange={(e) => form.set('pii_masking', e.target.checked)} />
          <span>
            <span className="font-medium">Enmascarar datos personales</span>
            <span className="block text-slate-500">
              Teléfonos, emails, DNI/NIE, IBAN y tarjetas se muestran como [TELÉFONO], [EMAIL], [DNI], [IBAN] y [TARJETA]
              en el detalle, el listado, el explorador y la búsqueda.
            </span>
          </span>
        </label>
      </fieldset>
      <p className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
        Con independencia de este interruptor, el índice de la búsqueda semántica y los prompts de los flujos usan siempre
        el texto enmascarado.
      </p>
      {form.errors.pii_masking && <p className="text-xs text-red-700">{form.errors.pii_masking}</p>}
      {canEdit && <SaveBar {...form.bar} />}
    </Card>
  )
}

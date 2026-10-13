import { useState } from 'react'
import { usePublicConfig } from '../../config/api'
import { DownloadSettingsFields } from '../../downloads/DownloadSettingsFields'
import { draftInterval, draftSchedule, settingsDraft, type SettingsDraft } from '../../downloads/settingsDraft'
import type { DownloadConfig } from '../types'

/** Lo que se guarda de la caja: un intervalo o una programación a medio escribir quedan sin configurar (FE017). */
function toConfig(draft: SettingsDraft): DownloadConfig {
  return { interval: draftInterval(draft, true), channels: draft.channels, overwrite: draft.overwrite,
    schedule: draftSchedule(draft, true), active: draft.active }
}

/** Caja «Genesys download» (FE017): los mismos campos que un flujo de descarga, sin nombre. */
export function DownloadPanel({ config, onChange }: { config: DownloadConfig; onChange: (config: DownloadConfig) => void }) {
  const timezone = usePublicConfig().data?.timezone ?? ''
  const [draft, setDraft] = useState<SettingsDraft>(() => settingsDraft(config))
  const set = <K extends keyof SettingsDraft>(key: K, value: SettingsDraft[K]) => {
    const next = { ...draft, [key]: value }
    setDraft(next)
    onChange(toConfig(next))
  }
  // Deshabilitado por el `fieldset` del panel cuando no hay permiso de edición.
  return (
    <div className="space-y-4">
      <DownloadSettingsFields draft={draft} set={set} disabled={false} errors={{}} timezone={timezone} />
    </div>
  )
}

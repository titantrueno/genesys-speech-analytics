import { useState } from 'react'
import { errorFor, fieldErrors } from '../config/api'
import { ConfigField, input } from '../config/controls'
import { SCHEDULE_LABELS, UNIT_LABELS } from './labels'
import type { DownloadChannel, DownloadFlow, DownloadFlowInput, RelativeUnit } from './types'

const SCHEDULED_NEEDS_RELATIVE = 'Una descarga programada necesita un intervalo relativo'

interface Draft {
  name: string
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
}

function toDraft(flow: DownloadFlow): Draft {
  const { interval, schedule } = flow
  return {
    name: flow.name,
    intervalType: interval.type,
    unit: interval.unit ?? 'hoy',
    amount: interval.amount ? String(interval.amount) : '',
    from: interval.from ?? '',
    to: interval.to ?? '',
    channels: flow.channels,
    scheduleType: schedule.type,
    hours: schedule.hours ? String(schedule.hours) : '',
    time: schedule.time ?? '',
    active: flow.active,
  }
}

function toInput(draft: Draft): DownloadFlowInput {
  const interval = draft.intervalType === 'especifico'
    ? { type: 'especifico' as const, from: draft.from, to: draft.to }
    : draft.unit === 'horas' || draft.unit === 'dias'
      ? { type: 'relativo' as const, unit: draft.unit, amount: Number(draft.amount) }
      : { type: 'relativo' as const, unit: draft.unit }
  const schedule = draft.scheduleType === 'cada_horas'
    ? { type: draft.scheduleType, hours: Number(draft.hours) }
    : draft.scheduleType === 'diaria' ? { type: draft.scheduleType, time: draft.time } : { type: draft.scheduleType }
  return { name: draft.name, interval, channels: draft.channels, schedule, active: draft.active }
}

/** Formulario de un flujo de descarga; los errores del backend (`422`) se muestran junto a su campo. */
export function DownloadFlowForm({ flow, canEdit, pending, error, saved, onSave }: {
  flow: DownloadFlow; canEdit: boolean; pending: boolean; error: unknown; saved: boolean
  onSave: (input: DownloadFlowInput) => void
}) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(flow))
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }))
  const errors = fieldErrors(error)
  const disabled = !canEdit
  const intervalError = errorFor(errors, 'interval')
  const scheduleConflict = draft.intervalType === 'especifico' && draft.scheduleType !== 'desactivada'
  const scheduleError = scheduleConflict ? SCHEDULED_NEEDS_RELATIVE : errorFor(errors, 'schedule')
  const dirty = JSON.stringify(toInput(draft)) !== JSON.stringify(toInput(toDraft(flow)))
  // Siempre en el orden voz, chat: desmarcar y volver a marcar un canal no cuenta como cambio.
  const toggleChannel = (channel: DownloadChannel) => set('channels', draft.channels.includes(channel)
    ? draft.channels.filter((c) => c !== channel)
    : (['voz', 'chat'] as const).filter((c) => c === channel || draft.channels.includes(c)))

  return (
    <form className="space-y-5" onSubmit={(event) => { event.preventDefault(); onSave(toInput(draft)) }}>
      <ConfigField label="Nombre" error={errorFor(errors, 'name')}>
        <input className={input} value={draft.name} maxLength={80} disabled={disabled}
          onChange={(e) => set('name', e.target.value)} />
      </ConfigField>

      <fieldset className="space-y-3">
        <legend className="text-xs font-medium text-slate-600">Intervalo</legend>
        <div className="flex gap-4 text-sm">
          {(['relativo', 'especifico'] as const).map((type) => (
            <label key={type} className="inline-flex items-center gap-1.5">
              <input type="radio" name="interval-type" checked={draft.intervalType === type} disabled={disabled}
                onChange={() => set('intervalType', type)} />
              {type === 'relativo' ? 'Relativo' : 'Específico'}
            </label>
          ))}
        </div>
        {draft.intervalType === 'relativo' ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <ConfigField label="Periodo" error={draft.unit === 'hoy' || draft.unit === 'ayer' ? intervalError : undefined}>
              <select className={input} value={draft.unit} disabled={disabled}
                onChange={(e) => set('unit', e.target.value as RelativeUnit)}>
                {Object.entries(UNIT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </ConfigField>
            {(draft.unit === 'horas' || draft.unit === 'dias') && (
              <ConfigField label="Cantidad" error={intervalError}
                hint={draft.unit === 'horas' ? 'De 1 a 720 horas.' : 'De 1 a 90 días.'}>
                <input type="number" className={input} value={draft.amount} disabled={disabled}
                  onChange={(e) => set('amount', e.target.value)} />
              </ConfigField>
            )}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <ConfigField label="Desde" error={errors['interval.from'] ?? (errors['interval.to'] ? undefined : intervalError)}>
              <input type="datetime-local" className={input} value={draft.from} disabled={disabled}
                onChange={(e) => set('from', e.target.value)} />
            </ConfigField>
            <ConfigField label="Hasta" error={errors['interval.to']}>
              <input type="datetime-local" className={input} value={draft.to} disabled={disabled}
                onChange={(e) => set('to', e.target.value)} />
            </ConfigField>
          </div>
        )}
        <p className="text-xs text-slate-500">
          «Hoy», «ayer», las fechas y la programación se calculan en la zona horaria de la plataforma ({flow.timezone}).
        </p>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-xs font-medium text-slate-600">Canales</legend>
        <div className="flex gap-4 text-sm">
          {(['voz', 'chat'] as const).map((channel) => (
            <label key={channel} className="inline-flex items-center gap-1.5">
              <input type="checkbox" checked={draft.channels.includes(channel)} disabled={disabled}
                onChange={() => toggleChannel(channel)} />
              {channel === 'voz' ? 'Voz' : 'Chat'}
            </label>
          ))}
        </div>
        {errorFor(errors, 'channels') && <p className="text-xs text-red-700">{errorFor(errors, 'channels')}</p>}
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-2">
        <ConfigField label="Programación" error={scheduleError}>
          <select className={input} value={draft.scheduleType} disabled={disabled}
            onChange={(e) => set('scheduleType', e.target.value as Draft['scheduleType'])}>
            {Object.entries(SCHEDULE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </ConfigField>
        {draft.scheduleType === 'cada_horas' && (
          <ConfigField label="Cada cuántas horas" hint="De 1 a 24, alineadas con la medianoche (cada 6: 00, 06, 12 y 18 h).">
            <input type="number" className={input} value={draft.hours} disabled={disabled}
              onChange={(e) => set('hours', e.target.value)} />
          </ConfigField>
        )}
        {draft.scheduleType === 'diaria' && (
          <ConfigField label="Hora">
            <input type="time" className={input} value={draft.time} disabled={disabled}
              onChange={(e) => set('time', e.target.value)} />
          </ConfigField>
        )}
      </div>

      <label className="inline-flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={draft.active} disabled={disabled} onChange={(e) => set('active', e.target.checked)} />
        Activo (un flujo inactivo no se ejecuta por programación, pero sí a mano)
      </label>

      {canEdit && (
        <div className="flex items-center gap-3">
          <button type="submit" disabled={!dirty || pending || scheduleConflict}
            className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50">
            Guardar
          </button>
          {saved && !dirty && <p role="status" className="text-sm text-emerald-700">Cambios guardados.</p>}
          {error !== null && error !== undefined && <p role="alert" className="text-sm text-red-700">
            {Object.keys(errors).length ? 'Revisa los campos marcados.' : 'No se han podido guardar los cambios.'}
          </p>}
        </div>
      )}
    </form>
  )
}

import { X } from 'lucide-react'
import { useCatalog, type Period } from '../api/metrics'
import { MultiSelect } from '../components/MultiSelect'
import { DEFAULT_PRESET, matchingPreset, PERIOD_PRESETS, presetRange, useDashboardFilters } from './useDashboardFilters'

const inputClass = 'h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700'

export function FilterBar({ effectivePeriod }: { effectivePeriod?: Period }) {
  const { filters, update, clear, activeCount } = useDashboardFilters()
  const { data: catalog } = useCatalog()
  const preset = matchingPreset(filters.from, filters.to)
  const fallback = effectivePeriod ?? presetRange(DEFAULT_PRESET)
  const from = filters.from ?? fallback.from
  const to = filters.to ?? fallback.to

  function onPreset(value: string) {
    if (value === 'custom') return
    update(Number(value) === DEFAULT_PRESET ? { from: undefined, to: undefined } : presetRange(Number(value)))
  }

  return (
    <div role="search" aria-label="Filtros" className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-3">
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
        Periodo
        <select className={inputClass} value={String(preset)} onChange={(e) => onPreset(e.target.value)}>
          {PERIOD_PRESETS.map((days) => <option key={days} value={days}>Últimos {days} días</option>)}
          <option value="custom" disabled>Personalizado</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
        Desde
        <input type="date" className={inputClass} value={from} max={to || undefined}
          onChange={(e) => e.target.value && update({ from: e.target.value, to })} />
      </label>
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
        Hasta
        <input type="date" className={inputClass} value={to} min={from || undefined}
          onChange={(e) => e.target.value && update({ from, to: e.target.value })} />
      </label>
      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
        Canal
        <select className={inputClass} value={filters.channel ?? ''} onChange={(e) => update({ channel: e.target.value || undefined })}>
          <option value="">Todos</option>
          {catalog?.channels.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
        </select>
      </label>
      <MultiSelect label="Cola" allLabel="Todas" selected={filters.queue}
        options={(catalog?.queues ?? []).map((q) => ({ value: q.id, label: q.name }))}
        onChange={(queue) => update({ queue })} />
      <MultiSelect label="Agente" allLabel="Todos" selected={filters.agent}
        options={(catalog?.agents ?? []).map((a) => ({ value: a.id, label: a.name }))}
        onChange={(agent) => update({ agent })} />
      <MultiSelect label="Main topic" allLabel="Todos" selected={filters.main_topic}
        options={(catalog?.main_topics ?? []).map((t) => ({ value: t.code, label: t.name }))}
        onChange={(main_topic) => update({ main_topic })} />
      {activeCount > 0 && (
        <button type="button" onClick={clear} className="flex h-9 items-center gap-1 rounded-md px-2 text-sm text-slate-600 hover:bg-slate-100">
          <X className="size-4" aria-hidden />
          Limpiar filtros
        </button>
      )}
    </div>
  )
}

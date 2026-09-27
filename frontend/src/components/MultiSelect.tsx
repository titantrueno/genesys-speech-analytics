import { Check, ChevronDown } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'

interface Option { value: string; label: string }

interface Props {
  label: string
  allLabel: string
  options: Option[]
  selected: string[]
  onChange: (values: string[]) => void
}

export function MultiSelect({ label, allLabel, options, selected, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const labels = options.filter((o) => selected.includes(o.value)).map((o) => o.label)
  const summary = labels.length === 0 ? allLabel : labels.length === 1 ? labels[0] : `${labels.length} seleccionados`

  function toggle(value: string) {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value])
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className={`flex h-9 items-center gap-2 rounded-md border px-3 text-sm ${
          labels.length ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-300 bg-white text-slate-700'
        }`}
      >
        <span className="text-slate-500">{label}:</span>
        <span className="max-w-40 truncate font-medium">{summary}</span>
        <ChevronDown className="size-4 text-slate-400" aria-hidden />
      </button>
      {open && (
        <div id={panelId} role="group" aria-label={label}
          className="absolute z-20 mt-1 max-h-72 w-72 overflow-y-auto rounded-md border border-slate-200 bg-white p-1 shadow-lg">
          {options.map((option) => {
            const checked = selected.includes(option.value)
            return (
              <label key={option.value} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-slate-50">
                <input type="checkbox" className="sr-only" checked={checked} onChange={() => toggle(option.value)} />
                <span aria-hidden className={`flex size-4 items-center justify-center rounded border ${checked ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300'}`}>
                  {checked && <Check className="size-3" strokeWidth={3} />}
                </span>
                {option.label}
              </label>
            )
          })}
          {selected.length > 0 && (
            <button type="button" onClick={() => onChange([])} className="mt-1 w-full rounded px-2 py-1.5 text-left text-sm text-brand-600 hover:bg-slate-50">
              Quitar selección
            </button>
          )}
        </div>
      )}
    </div>
  )
}

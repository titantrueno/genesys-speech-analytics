import { useRef, type KeyboardEvent } from 'react'

export type TabItem<T extends string> = { code: T; label: string }

/** Lista de pestañas accesible: flechas izquierda y derecha para moverse, panel con `${idPrefix}-panel-<código>`. */
export function Tabs<T extends string>({ label, idPrefix, tabs, current, onSelect }: {
  label: string; idPrefix: string; tabs: TabItem<T>[]; current: TabItem<T>; onSelect: (code: T) => void
}) {
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  function onKeyDown(event: KeyboardEvent) {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!delta) return
    event.preventDefault()
    const index = tabs.findIndex((t) => t.code === current.code)
    const next = tabs[(index + delta + tabs.length) % tabs.length]
    onSelect(next.code)
    tabRefs.current[next.code]?.focus()
  }

  return (
    <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="flex flex-wrap gap-1 border-b border-slate-200">
      {tabs.map((tab) => {
        const selected = tab.code === current.code
        return (
          <button key={tab.code} ref={(el) => { tabRefs.current[tab.code] = el }} id={`${idPrefix}-tab-${tab.code}`}
            type="button" role="tab" aria-selected={selected} aria-controls={`${idPrefix}-panel-${tab.code}`}
            tabIndex={selected ? 0 : -1} onClick={() => onSelect(tab.code)}
            className={`-mb-px rounded-t-md border px-3 py-1.5 text-sm ${selected ? 'border-slate-200 border-b-white bg-white font-medium text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

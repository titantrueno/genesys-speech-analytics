import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from 'react'
import type { Option } from '../types'

export const control = 'h-9 w-full rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700 disabled:bg-slate-50'

/** Etiqueta asociada con `htmlFor` y pista con `aria-describedby`, para que el nombre accesible sea solo la etiqueta. */
export function Field({ label, children, hint }: { label: string; children: ReactElement<{ id?: string; 'aria-describedby'?: string }>; hint?: ReactNode }) {
  const id = useId()
  const hintId = `${id}-hint`
  const control = isValidElement(children) ? cloneElement(children, { id, 'aria-describedby': hint ? hintId : undefined }) : children
  return (
    <div className="space-y-1 text-xs font-medium text-slate-600">
      <label htmlFor={id} className="block">{label}</label>
      {control}
      {hint && <p id={hintId} className="font-normal text-slate-500">{hint}</p>}
    </div>
  )
}

export function Select<T extends string>({ label, value, options, onChange, placeholder }: {
  label: string; value: T | undefined; options: Option<T>[]; onChange: (value: T) => void; placeholder?: string
}) {
  return (
    <Field label={label}>
      <select className={control} value={value ?? ''} onChange={(e) => onChange(e.target.value as T)}>
        {(value === undefined || placeholder) && <option value="" disabled>{placeholder ?? 'Elige una opción'}</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </Field>
  )
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-2 border-t border-slate-100 pt-3">
      <h3 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h3>
      {children}
    </section>
  )
}

import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from 'react'

export const input = 'h-9 w-full rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700 disabled:bg-slate-50 disabled:text-slate-500 aria-[invalid=true]:border-red-500'

type ControlProps = { id?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }

/** Campo con etiqueta, pista y error del backend junto al control (`aria-describedby` y `aria-invalid`). */
export function ConfigField({ label, error, hint, children }: {
  label: string; error?: string; hint?: ReactNode; children: ReactElement<ControlProps>
}) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ') || undefined
  const control = isValidElement(children)
    ? cloneElement(children, { id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined })
    : children
  return (
    <div className="space-y-1 text-sm">
      <label htmlFor={id} className="block text-xs font-medium text-slate-600">{label}</label>
      {control}
      {error && <p id={errorId} className="text-xs text-red-700">{error}</p>}
      {hint && <p id={hintId} className="text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

/** Botón Guardar (solo con cambios) con el resultado de la última escritura. */
export function SaveBar({ dirty, pending, saved, failed, onSave }: {
  dirty: boolean; pending: boolean; saved: boolean; failed: boolean; onSave: () => void
}) {
  return (
    <div className="flex items-center gap-3 pt-2">
      <button type="button" onClick={onSave} disabled={!dirty || pending}
        className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50">
        Guardar
      </button>
      {saved && !dirty && <p role="status" className="text-sm text-emerald-700">Cambios guardados.</p>}
      {failed && <p role="alert" className="text-sm text-red-700">Revisa los campos marcados.</p>}
    </div>
  )
}

export function Card({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  return (
    <section aria-label={title} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <header>
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </header>
      {children}
    </section>
  )
}

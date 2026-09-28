import { useState } from 'react'
import { fieldErrors, useConfigMutation } from './api'

/** Borrador de una sección: se compara con el valor guardado para saber si hay cambios, y guarda con `request`. */
export function useSectionForm<T extends object>(saved: T, request: (body: T) => Promise<unknown>) {
  const [draft, setDraft] = useState<T>(saved)
  const mutation = useConfigMutation(request)
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved)
  return {
    draft,
    set: <K extends keyof T>(key: K, value: T[K]) => setDraft((current) => ({ ...current, [key]: value })),
    dirty,
    errors: fieldErrors(mutation.error),
    save: () => mutation.mutate(draft),
    bar: { dirty, pending: mutation.isPending, saved: mutation.isSuccess, failed: mutation.isError, onSave: () => mutation.mutate(draft) },
  }
}

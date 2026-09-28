import { Loader2, Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { useInterpret } from './api'
import type { ExplorerQuery } from './queryModel'

export function NaturalLanguage({ onQuery }: { onQuery: (query: ExplorerQuery) => void }) {
  const [text, setText] = useState('')
  const interpret = useInterpret()
  const unrecognized = interpret.data?.unrecognized ?? []

  function submit(event: FormEvent) {
    event.preventDefault()
    interpret.mutate(text, { onSuccess: (result) => onQuery(result.query) })
  }

  const error = interpret.error instanceof ApiError ? interpret.error.message : interpret.error ? 'No se ha podido interpretar la frase' : null

  return (
    <form onSubmit={submit} className="space-y-2">
      <label htmlFor="nl-query" className="block text-xs font-medium text-slate-500">Describe lo que buscas</label>
      <div className="flex gap-2">
        <input id="nl-query" type="text" value={text} onChange={(e) => setText(e.target.value)} maxLength={500}
          placeholder="p. ej. chats negativos de cargos no reconocidos escalados"
          className="h-9 min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none" />
        <button type="submit" disabled={!text.trim() || interpret.isPending}
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-brand-600 px-3 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
          {interpret.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
          Interpretar
        </button>
      </div>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {interpret.isSuccess && unrecognized.length > 0 && (
        <p role="alert" className="text-sm text-amber-800">No he entendido: {unrecognized.join(', ')}</p>
      )}
      {interpret.isSuccess && (
        <p role="status" className="text-xs text-slate-500">Consulta cargada en el constructor: revisa las condiciones antes de fiarte del resultado.</p>
      )}
    </form>
  )
}

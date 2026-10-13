import { Check, Pencil, Save, Trash2, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useI18n } from '../i18n/useI18n'
import { useSavedQueries, useSavedQueryMutations, type SavedQuery } from './api'
import type { ExplorerQuery } from './queryModel'

const input = 'h-8 min-w-0 flex-1 rounded-md border border-slate-300 px-2 text-sm'
const small = 'rounded-md px-2 py-1 text-xs text-slate-600 hover:bg-slate-100'

function SavedItem({ item, onLoad }: { item: SavedQuery; onLoad: (query: ExplorerQuery) => void }) {
  const { t } = useI18n()
  const { rename, remove } = useSavedQueryMutations()
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [name, setName] = useState(item.name)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    rename.mutate({ id: item.id, name: name.trim() }, { onSuccess: () => setEditing(false) })
  }

  return (
    <li className="rounded-lg border border-slate-200 p-2">
      {editing ? (
        <form onSubmit={submit} className="flex items-center gap-1">
          <input aria-label={t('exp.saved.newName')} className={input} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} autoFocus />
          <button type="submit" aria-label={t('exp.saved.saveName')} className={small}><Check className="size-4" aria-hidden /></button>
          <button type="button" aria-label={t('exp.saved.cancel')} className={small} onClick={() => setEditing(false)}><X className="size-4" aria-hidden /></button>
        </form>
      ) : (
        <p className="truncate text-sm font-medium text-slate-800" title={item.name}>{item.name}</p>
      )}
      {confirming ? (
        <div className="mt-1 flex items-center gap-1 text-xs text-slate-600">
          {t('exp.saved.confirmDelete')}
          <button type="button" className={`${small} text-red-700`} onClick={() => remove.mutate(item.id)}>{t('exp.saved.confirm')}</button>
          <button type="button" className={small} onClick={() => setConfirming(false)}>{t('exp.saved.no')}</button>
        </div>
      ) : (
        <div className="mt-1 flex gap-1">
          <button type="button" className={`${small} font-medium text-brand-700`} onClick={() => onLoad(item.query)}>{t('exp.saved.load')}</button>
          <button type="button" className={small} onClick={() => { setName(item.name); setEditing(true) }}>
            <Pencil className="mr-1 inline size-3" aria-hidden />{t('exp.saved.rename')}
          </button>
          <button type="button" className={small} onClick={() => setConfirming(true)}>
            <Trash2 className="mr-1 inline size-3" aria-hidden />{t('exp.saved.delete')}
          </button>
        </div>
      )}
    </li>
  )
}

export function SavedQueries({ current, onLoad }: { current: ExplorerQuery; onLoad: (query: ExplorerQuery) => void }) {
  const { t } = useI18n()
  const { data, isError } = useSavedQueries()
  const { create } = useSavedQueryMutations()
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    create.mutate({ name: name.trim(), query: current }, { onSuccess: () => { setSaving(false); setName('') } })
  }

  return (
    <section aria-label={t('exp.saved.title')} className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">{t('exp.saved.title')}</h2>
      {saving ? (
        <form onSubmit={submit} className="space-y-1.5">
          <label className="block text-xs font-medium text-slate-500">
            {t('exp.saved.name')}
            <input className={`${input} mt-1 w-full`} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} autoFocus />
          </label>
          <div className="flex gap-1">
            <button type="submit" disabled={!name.trim() || create.isPending}
              className="rounded-md bg-brand-600 px-3 py-1 text-sm text-white disabled:opacity-50">{t('exp.saved.save')}</button>
            <button type="button" className={small} onClick={() => setSaving(false)}>{t('exp.saved.cancel')}</button>
          </div>
          {create.isError && <p role="alert" className="text-xs text-red-700">{t('exp.saved.saveError')}</p>}
        </form>
      ) : (
        <button type="button" onClick={() => setSaving(true)}
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50">
          <Save className="size-4" aria-hidden />{t('exp.saved.saveCurrent')}
        </button>
      )}
      {isError && <p role="alert" className="text-xs text-red-700">{t('exp.saved.loadError')}</p>}
      {data && data.items.length === 0 && <p className="text-xs text-slate-500">{t('exp.saved.empty')}</p>}
      <ul className="space-y-1.5">
        {data?.items.map((item) => <SavedItem key={item.id} item={item} onLoad={onLoad} />)}
      </ul>
    </section>
  )
}

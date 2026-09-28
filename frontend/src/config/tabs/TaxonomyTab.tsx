import { useState } from 'react'
import { formatInteger } from '../../lib/format'
import { configRequests, errorFor, fieldErrors, useConfigMutation, useTaxonomy } from '../api'
import { Card, ConfigField, ConfirmAction, input, smallButton } from '../controls'
import { splitComma } from '../lists'
import type { Topic, TopicInput, TopicKind } from '../types'

const KINDS: Array<{ kind: TopicKind; title: string; singular: string; codeHint: string }> = [
  { kind: 'main-topics', title: 'Main topics', singular: 'main topic',
    codeHint: 'Minúsculas, números y guiones bajos (por ejemplo, cargo_no_reconocido). No se puede cambiar.' },
  { kind: 'secondary-topics', title: 'Temas secundarios', singular: 'tema secundario',
    codeHint: 'Texto en minúsculas tal como se guarda en las conversaciones. No se puede cambiar.' },
]

const editable = ({ code, name, description, keywords, active }: Topic): TopicInput => ({ code, name, description, keywords, active })

function TopicForm({ kind, singular, codeHint, topic, onDone }: {
  kind: TopicKind; singular: string; codeHint: string; topic?: Topic; onDone: () => void
}) {
  const [draft, setDraft] = useState<TopicInput>(topic ? editable(topic) : { code: '', name: '', description: '', keywords: [], active: true })
  const [keywords, setKeywords] = useState((topic?.keywords ?? []).join(', '))
  const save = useConfigMutation((body: TopicInput) => topic
    ? configRequests.updateTopic({ kind, id: topic.id, body })
    : configRequests.createTopic({ kind, body }))
  const errors = fieldErrors(save.error)
  const title = topic ? `Editar ${singular} «${topic.name}»` : `Nuevo ${singular}`
  return (
    <form aria-label={title} className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ ...draft, keywords: splitComma(keywords) }, { onSuccess: onDone })
      }}>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <ConfigField label="Código" error={errors.code} hint={codeHint}>
          <input className={input} value={draft.code} disabled={Boolean(topic)} onChange={(e) => setDraft({ ...draft, code: e.target.value })} />
        </ConfigField>
        <ConfigField label="Nombre" error={errors.name}>
          <input className={input} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </ConfigField>
        <ConfigField label="Descripción" error={errors.description}>
          <input className={input} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
        </ConfigField>
        <ConfigField label="Palabras clave" error={errorFor(errors, 'keywords')} hint="Separadas por comas.">
          <input className={input} value={keywords} onChange={(e) => setKeywords(e.target.value)} />
        </ConfigField>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={save.isPending}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">Guardar</button>
        <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={onDone}>Cancelar</button>
      </div>
    </form>
  )
}

function TopicSection({ kind, title, singular, codeHint, topics, canEdit }: (typeof KINDS)[number] & {
  topics: Topic[]; canEdit: boolean
}) {
  const [editing, setEditing] = useState<Topic | 'new' | null>(null)
  const update = useConfigMutation(configRequests.updateTopic)
  const remove = useConfigMutation(configRequests.deleteTopic)
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        {canEdit && editing === null && (
          <button type="button" className={smallButton} onClick={() => setEditing('new')}>{`Nuevo ${singular}`}</button>
        )}
      </div>
      {editing !== null && (
        <TopicForm key={editing === 'new' ? 'new' : editing.id} kind={kind} singular={singular} codeHint={codeHint}
          topic={editing === 'new' ? undefined : editing} onDone={() => setEditing(null)} />
      )}
      <div className="overflow-x-auto">
        <table aria-label={title} className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              {['Código', 'Nombre', 'Palabras clave', 'Conversaciones', 'Estado', ...(canEdit ? ['Acciones'] : [])].map((label) => (
                <th key={label} scope="col" className="px-2 py-1.5 font-medium">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topics.map((topic) => (
              <tr key={topic.id} className="border-b border-slate-100 align-top last:border-0">
                <td className="px-2 py-2 font-mono text-xs text-slate-600">{topic.code}</td>
                <td className="px-2 py-2">
                  <span className="font-medium text-slate-800">{topic.name}</span>
                  {topic.description && <span className="block text-xs text-slate-500">{topic.description}</span>}
                </td>
                <td className="px-2 py-2 text-xs text-slate-600">{topic.keywords.join(', ')}</td>
                <td className="px-2 py-2 tabular-nums">{formatInteger(topic.conversations)}</td>
                <td className="px-2 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${topic.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                    {topic.active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                {canEdit && (
                  <td className="px-2 py-2">
                    <span className="inline-flex flex-wrap gap-1">
                      <button type="button" className={smallButton} aria-label={`Editar ${topic.name}`} onClick={() => setEditing(topic)}>Editar</button>
                      {topic.active ? (
                        <ConfirmAction label="Desactivar" question="¿Dejar de ofrecerlo en filtros?"
                          onConfirm={() => update.mutate({ kind, id: topic.id, body: { ...editable(topic), active: false } })} />
                      ) : (
                        <button type="button" className={smallButton}
                          onClick={() => update.mutate({ kind, id: topic.id, body: { ...editable(topic), active: true } })}>Activar</button>
                      )}
                      {topic.conversations === 0 && (
                        <ConfirmAction label="Borrar" question="¿Borrarlo?" onConfirm={() => remove.mutate({ kind, id: topic.id })} />
                      )}
                    </span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(update.isError || remove.isError) && <p role="alert" className="text-sm text-red-700">No se ha podido completar la acción.</p>}
    </div>
  )
}

export function TaxonomyTab({ canEdit }: { canEdit: boolean }) {
  const { data, isError, isPending } = useTaxonomy()
  return (
    <Card title="Taxonomía"
      description="Main topics y temas secundarios. El código es la clave en filtros, consultas y flujos: no cambia. Un tema en uso no se borra; se desactiva y deja de ofrecerse en los filtros, pero sus conversaciones lo conservan.">
      {isPending && <p className="text-sm text-slate-500">Cargando taxonomía…</p>}
      {isError && <p role="alert" className="text-sm text-red-700">No se ha podido cargar la taxonomía.</p>}
      {data && KINDS.map((k) => (
        <TopicSection key={k.kind} {...k} canEdit={canEdit}
          topics={k.kind === 'main-topics' ? data.main_topics : data.secondary_topics} />
      ))}
    </Card>
  )
}

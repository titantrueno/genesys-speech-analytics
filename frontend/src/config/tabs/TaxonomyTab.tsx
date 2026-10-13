import { useState } from 'react'
import { useI18n } from '../../i18n/useI18n'
import type { TKey } from '../../i18n/dictionaries'
import { formatInteger } from '../../lib/format'
import { configRequests, errorFor, fieldErrors, useConfigMutation, useTaxonomy } from '../api'
import { Card, ConfigField, ConfirmAction, input, smallButton } from '../controls'
import { splitComma } from '../lists'
import type { Topic, TopicInput, TopicKind } from '../types'

const KINDS = [
  { kind: 'main-topics' as TopicKind, title: 'cfg.tax.main.title', newLabel: 'cfg.tax.main.new', editLabel: 'cfg.tax.main.edit', codeHint: 'cfg.tax.main.codeHint' },
  { kind: 'secondary-topics' as TopicKind, title: 'cfg.tax.secondary.title', newLabel: 'cfg.tax.secondary.new', editLabel: 'cfg.tax.secondary.edit', codeHint: 'cfg.tax.secondary.codeHint' },
] as const

const editable = ({ code, name, description, keywords, active }: Topic): TopicInput => ({ code, name, description, keywords, active })

function TopicForm({ kind, newLabel, editLabel, codeHint, topic, onDone }: {
  kind: TopicKind; newLabel: TKey; editLabel: TKey; codeHint: TKey; topic?: Topic; onDone: () => void
}) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<TopicInput>(topic ? editable(topic) : { code: '', name: '', description: '', keywords: [], active: true })
  const [keywords, setKeywords] = useState((topic?.keywords ?? []).join(', '))
  const save = useConfigMutation((body: TopicInput) => topic
    ? configRequests.updateTopic({ kind, id: topic.id, body })
    : configRequests.createTopic({ kind, body }))
  const errors = fieldErrors(save.error)
  const title = topic ? t(editLabel, { name: topic.name }) : t(newLabel)
  return (
    <form aria-label={title} className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ ...draft, keywords: splitComma(keywords) }, { onSuccess: onDone })
      }}>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <ConfigField label={t('cfg.code')} error={errors.code} hint={t(codeHint)}>
          <input className={input} value={draft.code} disabled={Boolean(topic)} onChange={(e) => setDraft({ ...draft, code: e.target.value })} />
        </ConfigField>
        <ConfigField label={t('cfg.name')} error={errors.name}>
          <input className={input} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </ConfigField>
        <ConfigField label={t('cfg.description')} error={errors.description}>
          <input className={input} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
        </ConfigField>
        <ConfigField label={t('cfg.tax.keywords')} error={errorFor(errors, 'keywords')} hint={t('cfg.tax.keywordsHint')}>
          <input className={input} value={keywords} onChange={(e) => setKeywords(e.target.value)} />
        </ConfigField>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={save.isPending}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">{t('cfg.save')}</button>
        <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={onDone}>{t('cfg.cancel')}</button>
      </div>
    </form>
  )
}

function TopicSection({ kind, title: titleKey, newLabel, editLabel, codeHint, topics, canEdit }: (typeof KINDS)[number] & {
  topics: Topic[]; canEdit: boolean
}) {
  const { t } = useI18n()
  const title = t(titleKey)
  const [editing, setEditing] = useState<Topic | 'new' | null>(null)
  const update = useConfigMutation(configRequests.updateTopic)
  const remove = useConfigMutation(configRequests.deleteTopic)
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        {canEdit && editing === null && (
          <button type="button" className={smallButton} onClick={() => setEditing('new')}>{t(newLabel)}</button>
        )}
      </div>
      {editing !== null && (
        <TopicForm key={editing === 'new' ? 'new' : editing.id} kind={kind} newLabel={newLabel} editLabel={editLabel} codeHint={codeHint}
          topic={editing === 'new' ? undefined : editing} onDone={() => setEditing(null)} />
      )}
      <div className="overflow-x-auto">
        <table aria-label={title} className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              {(['cfg.code', 'cfg.name', 'cfg.tax.keywords', 'cfg.conversations', 'cfg.status', ...(canEdit ? ['cfg.actions' as const] : [])] as const).map((label) => (
                <th key={label} scope="col" className="px-2 py-1.5 font-medium">{t(label)}</th>
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
                    {topic.active ? t('cfg.active') : t('cfg.inactive')}
                  </span>
                </td>
                {canEdit && (
                  <td className="px-2 py-2">
                    <span className="inline-flex flex-wrap gap-1">
                      <button type="button" className={smallButton} aria-label={t('cfg.editAria', { name: topic.name })} onClick={() => setEditing(topic)}>{t('cfg.edit')}</button>
                      {topic.active ? (
                        <ConfirmAction label={t('cfg.deactivate')} question={t('cfg.tax.deactivateQuestion')}
                          onConfirm={() => update.mutate({ kind, id: topic.id, body: { ...editable(topic), active: false } })} />
                      ) : (
                        <button type="button" className={smallButton}
                          onClick={() => update.mutate({ kind, id: topic.id, body: { ...editable(topic), active: true } })}>{t('cfg.activate')}</button>
                      )}
                      {topic.conversations === 0 && (
                        <ConfirmAction label={t('cfg.delete')} question={t('cfg.tax.deleteQuestion')} onConfirm={() => remove.mutate({ kind, id: topic.id })} />
                      )}
                    </span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(update.isError || remove.isError) && <p role="alert" className="text-sm text-red-700">{t('cfg.actionError')}</p>}
    </div>
  )
}

export function TaxonomyTab({ canEdit }: { canEdit: boolean }) {
  const { t } = useI18n()
  const { data, isError, isPending } = useTaxonomy()
  return (
    <Card title={t('cfg.tab.taxonomia')}
      description={t('cfg.tax.description')}>
      {isPending && <p className="text-sm text-slate-500">{t('cfg.tax.loading')}</p>}
      {isError && <p role="alert" className="text-sm text-red-700">{t('cfg.tax.error')}</p>}
      {data && KINDS.map((k) => (
        <TopicSection key={k.kind} {...k} canEdit={canEdit}
          topics={k.kind === 'main-topics' ? data.main_topics : data.secondary_topics} />
      ))}
    </Card>
  )
}

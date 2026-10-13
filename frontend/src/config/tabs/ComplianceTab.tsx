import { useState } from 'react'
import { useI18n } from '../../i18n/useI18n'
import { configRequests, errorFor, fieldErrors, useChecks, useConfigMutation } from '../api'
import { Card, ConfigField, ConfirmAction, input, smallButton } from '../controls'
import { splitLines } from '../lists'
import type { CheckInput, ComplianceCheck } from '../types'

const CHANNELS = { ambos: 'cfg.channel.ambos', voz: 'domain.channel.voz', chat: 'domain.channel.chat' } as const

const editable = ({ code, name, description, phrases, channel, active }: ComplianceCheck): CheckInput =>
  ({ code, name, description, phrases, channel, active })

function CheckForm({ check, onDone }: { check?: ComplianceCheck; onDone: () => void }) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<CheckInput>(check ? editable(check)
    : { code: '', name: '', description: '', phrases: [], channel: 'ambos', active: true })
  const [phrases, setPhrases] = useState((check?.phrases ?? []).join('\n'))
  const save = useConfigMutation((body: CheckInput) => check
    ? configRequests.updateCheck({ id: check.id, body })
    : configRequests.createCheck(body))
  const errors = fieldErrors(save.error)
  const title = check ? t('cfg.check.edit', { name: check.name }) : t('cfg.check.new')
  return (
    <form aria-label={title} className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ ...draft, phrases: splitLines(phrases) }, { onSuccess: onDone })
      }}>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      {check?.builtin && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {t('cfg.check.builtin')}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <ConfigField label={t('cfg.code')} error={errors.code} hint={t('cfg.check.codeHint')}>
          <input className={input} value={draft.code} disabled={Boolean(check)} onChange={(e) => setDraft({ ...draft, code: e.target.value })} />
        </ConfigField>
        <ConfigField label={t('cfg.name')} error={errors.name}>
          <input className={input} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </ConfigField>
        <ConfigField label={t('cfg.description')} error={errors.description}>
          <input className={input} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
        </ConfigField>
        <ConfigField label={t('cfg.check.channel')} error={errors.channel}>
          <select className={input} value={draft.channel}
            onChange={(e) => setDraft({ ...draft, channel: e.target.value as CheckInput['channel'] })}>
            {Object.entries(CHANNELS).map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}
          </select>
        </ConfigField>
        <div className="sm:col-span-2">
          <ConfigField label={t('cfg.check.phrases')} error={errorFor(errors, 'phrases')}
            hint={t('cfg.check.phrasesHint')}>
            <textarea className={`${input} h-24 py-1.5`} value={phrases} onChange={(e) => setPhrases(e.target.value)} />
          </ConfigField>
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={save.isPending}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">{t('cfg.save')}</button>
        <button type="button" className="rounded-md border border-slate-300 px-3 py-1.5 text-sm" onClick={onDone}>{t('cfg.cancel')}</button>
      </div>
    </form>
  )
}

export function ComplianceTab({ canEdit }: { canEdit: boolean }) {
  const { t } = useI18n()
  const { data, isError, isPending } = useChecks()
  const [editing, setEditing] = useState<ComplianceCheck | 'new' | null>(null)
  const update = useConfigMutation(configRequests.updateCheck)
  const remove = useConfigMutation(configRequests.deleteCheck)
  return (
    <Card title={t('cfg.check.title')}
      description={t('cfg.check.description')}>
      {canEdit && editing === null && (
        <button type="button" className={smallButton} onClick={() => setEditing('new')}>{t('cfg.check.new')}</button>
      )}
      {editing !== null && (
        <CheckForm key={editing === 'new' ? 'new' : editing.id} check={editing === 'new' ? undefined : editing}
          onDone={() => setEditing(null)} />
      )}
      {isPending && <p className="text-sm text-slate-500">{t('cfg.check.loading')}</p>}
      {isError && <p role="alert" className="text-sm text-red-700">{t('cfg.check.error')}</p>}
      {data && (
        <div className="overflow-x-auto">
          <table aria-label={t('cfg.check.table')} className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {(['cfg.check.col.check', 'cfg.check.col.evaluation', 'cfg.check.col.channel', 'cfg.check.col.phrases', 'cfg.status', ...(canEdit ? ['cfg.actions' as const] : [])] as const).map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 font-medium">{t(label)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((check) => (
                <tr key={check.id} className="border-b border-slate-100 align-top last:border-0">
                  <td className="px-2 py-2">
                    <span className="font-medium text-slate-800">{check.name}</span>
                    {check.description && <span className="block text-xs text-slate-500">{check.description}</span>}
                  </td>
                  <td className="px-2 py-2 text-xs text-slate-600">
                    {check.evaluation === 'analisis' ? t('cfg.check.evalAnalysis') : t('cfg.check.evalPhrases')}
                  </td>
                  <td className="px-2 py-2">{t(CHANNELS[check.channel])}</td>
                  <td className="px-2 py-2 text-xs text-slate-600">{check.phrases.join(' · ')}</td>
                  <td className="px-2 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${check.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                      {check.active ? t('cfg.active') : t('cfg.inactive')}
                    </span>
                  </td>
                  {canEdit && (
                    <td className="px-2 py-2">
                      <span className="inline-flex flex-wrap gap-1">
                        <button type="button" className={smallButton} aria-label={t('cfg.editAria', { name: check.name })} onClick={() => setEditing(check)}>{t('cfg.edit')}</button>
                        {check.active ? (
                          <ConfirmAction label={t('cfg.deactivate')} question={t('cfg.check.deactivateQuestion')}
                            onConfirm={() => update.mutate({ id: check.id, body: { ...editable(check), active: false } })} />
                        ) : (
                          <button type="button" className={smallButton}
                            onClick={() => update.mutate({ id: check.id, body: { ...editable(check), active: true } })}>{t('cfg.activate')}</button>
                        )}
                        {!check.builtin && (
                          <ConfirmAction label={t('cfg.delete')} question={t('cfg.check.deleteQuestion')} onConfirm={() => remove.mutate(check.id)} />
                        )}
                      </span>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(update.isError || remove.isError) && <p role="alert" className="text-sm text-red-700">{t('cfg.actionError')}</p>}
    </Card>
  )
}

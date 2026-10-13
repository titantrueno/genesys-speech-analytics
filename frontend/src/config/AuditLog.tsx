import type { UseQueryResult } from '@tanstack/react-query'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime } from '../lib/format'
import { formatAuditValue } from './format'
import type { AuditEntry } from './types'

/** Registro de auditoría compartido (FE005 y FE006): cada sección pasa su consulta. */
export function AuditLog({ query }: { query: UseQueryResult<{ items: AuditEntry[] }> }) {
  const { t } = useI18n()
  const { data, isError, isPending } = query
  return (
    <section aria-label={t('cfg.audit.title')} className="space-y-2 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">{t('cfg.audit.title')}</h2>
      {isPending && <p className="text-sm text-slate-500">{t('cfg.audit.loading')}</p>}
      {isError && <p className="text-sm text-red-700">{t('cfg.audit.error')}</p>}
      {data && data.items.length === 0 && <p className="text-sm text-slate-500">{t('cfg.audit.empty')}</p>}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {(['cfg.audit.when', 'cfg.audit.who', 'cfg.audit.element', 'cfg.audit.before', 'cfg.audit.after'] as const).map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 font-medium">{t(label)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((entry) => (
                <tr key={entry.id} className="border-b border-slate-100 align-top last:border-0">
                  <td className="px-2 py-1.5 whitespace-nowrap text-slate-600">{formatDateTime(entry.at)}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap">{entry.user.name}</td>
                  <td className="px-2 py-1.5">{entry.element}</td>
                  <td className="px-2 py-1.5 text-slate-500">{formatAuditValue(entry.before, t)}</td>
                  <td className="px-2 py-1.5">{formatAuditValue(entry.after, t)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

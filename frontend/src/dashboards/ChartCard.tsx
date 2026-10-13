import { useState, type ReactNode } from 'react'
import { useI18n } from '../i18n/useI18n'

export function LoadError({ message }: { message?: string }) {
  const { t } = useI18n()
  return <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message ?? t('dash.loadError')}</p>
}

export function PendingNotice() {
  const { t } = useI18n()
  return <p className="rounded-md bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">{t('dash.kpiPending')}</p>
}

interface Props {
  title: string
  subtitle?: string
  actions?: ReactNode
  table?: ReactNode
  loading?: boolean
  error?: boolean
  /** Depende del análisis de la plataforma y las conversaciones reales aún no lo tienen (FE012). */
  pending?: boolean
  children: ReactNode
  className?: string
}

export function ChartCard({ title, subtitle, actions, table, loading, error, pending, children, className = '' }: Props) {
  const { t } = useI18n()
  const [showTable, setShowTable] = useState(false)
  return (
    <section className={`rounded-xl border border-slate-200 bg-[var(--chart-surface)] p-4 ${className}`}>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {table && !pending && (
            <button type="button" onClick={() => setShowTable((v) => !v)}
              className="rounded-md px-2 py-1 text-xs text-brand-600 hover:bg-brand-50">
              {showTable ? t('dash.viewChart') : t('dash.viewTable')}
            </button>
          )}
        </div>
      </header>
      <div className={`transition-opacity ${loading ? 'opacity-50' : ''}`}>
        {error ? <LoadError /> : pending ? <PendingNotice /> : showTable ? table : children}
      </div>
    </section>
  )
}

export function DataTable({ caption, columns, rows }: { caption: string; columns: string[]; rows: Array<Array<ReactNode>> }) {
  return (
    <div className="overflow-x-auto">
      <table aria-label={caption} className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
            {columns.map((c, i) => <th key={c} className={`py-2 pr-3 font-medium ${i > 0 ? 'text-right' : ''}`}>{c}</th>)}
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-slate-100 last:border-0">
              {row.map((cell, i) => <td key={i} className={`py-2 pr-3 ${i > 0 ? 'text-right' : 'text-slate-700'}`}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

import { useState, type ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: string
  actions?: ReactNode
  table?: ReactNode
  loading?: boolean
  children: ReactNode
  className?: string
}

export function ChartCard({ title, subtitle, actions, table, loading, children, className = '' }: Props) {
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
          {table && (
            <button type="button" onClick={() => setShowTable((v) => !v)}
              className="rounded-md px-2 py-1 text-xs text-brand-600 hover:bg-brand-50">
              {showTable ? 'Ver gráfico' : 'Ver tabla'}
            </button>
          )}
        </div>
      </header>
      <div className={`transition-opacity ${loading ? 'opacity-50' : ''}`}>
        {showTable ? table : children}
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

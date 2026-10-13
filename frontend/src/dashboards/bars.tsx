// Barras en HTML, sin Recharts: así las usan también las vistas que no necesitan la librería de gráficos (FE004).
import { Link } from 'react-router'
import { useI18n } from '../i18n/useI18n'

export interface BarItem { key: string; label: string; value: number | null }

export function RankedBars({ label, items, format, maxValue, diverging = false, hrefFor }: {
  label: string
  items: BarItem[]
  format: (value: number | null) => string
  maxValue?: number
  diverging?: boolean
  hrefFor?: (item: BarItem) => string
}) {
  const { t } = useI18n()
  const max = maxValue ?? Math.max(...items.map((i) => Math.abs(i.value ?? 0)), 1)
  if (items.length === 0) return <EmptyState />
  return (
    <ul aria-label={label} className="space-y-2.5">
      {items.map((item) => {
        const value = item.value ?? 0
        const width = `${Math.min(100, (Math.abs(value) / max) * 100)}%`
        const text = format(item.value)
        return (
          <li key={item.key} className="grid grid-cols-[minmax(0,14rem)_1fr] items-center gap-3 text-sm" title={`${item.label}: ${text}`}>
            {hrefFor ? (
              <Link to={hrefFor(item)} aria-label={t('dash.barLink', { label: item.label, text })}
                className="truncate text-slate-700 underline-offset-2 hover:text-brand-700 hover:underline">
                {item.label}
              </Link>
            ) : <span className="truncate text-slate-700">{item.label}</span>}
            {diverging ? (
              <div className="grid grid-cols-2 items-center">
                <div className="flex items-center justify-end gap-1.5 border-r border-[var(--chart-axis)] pr-px">
                  {value < 0 && <><span className="text-xs text-slate-600 tabular-nums">{text}</span>
                    <span className="h-3 rounded-l bg-[var(--diverging-negative)]" style={{ width }} /></>}
                </div>
                <div className="flex items-center gap-1.5 pl-px">
                  {value >= 0 && <><span className="h-3 rounded-r bg-[var(--diverging-positive)]" style={{ width }} />
                    <span className="text-xs text-slate-600 tabular-nums">{text}</span></>}
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="h-3 rounded-r bg-[var(--series-1)]" style={{ width }} />
                <span className="shrink-0 text-xs text-slate-600 tabular-nums">{text}</span>
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export function EmptyState() {
  const { t } = useI18n()
  return <p className="py-8 text-center text-sm text-slate-500">{t('dash.empty')}</p>
}

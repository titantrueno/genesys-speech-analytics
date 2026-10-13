import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router'
import { useI18n } from '../i18n/useI18n'
import type { KpiSummary } from '../api/metrics'
import { formatDelta, formatInteger, formatKpi, trendOf } from '../lib/format'

const TREND_STYLE = {
  mejora: { className: 'text-[var(--status-good-text)]', label: 'dash.trend.mejora' },
  empeora: { className: 'text-[var(--status-critical)]', label: 'dash.trend.empeora' },
  estable: { className: 'text-slate-500', label: 'dash.trend.estable' },
} as const

const STATUS = {
  verde: { label: 'dash.status.verde', className: 'border-l-[var(--status-good-text)] ', badge: 'bg-emerald-50 text-emerald-800' },
  ambar: { label: 'dash.status.ambar', className: 'border-l-amber-500 ', badge: 'bg-amber-50 text-amber-800' },
  rojo: { label: 'dash.status.rojo', className: 'border-l-[var(--status-critical)] ', badge: 'bg-red-50 text-red-800' },
} as const

export function KpiTile({ kpi, href, comparison = true }: { kpi: KpiSummary; href?: string; comparison?: boolean }) {
  const { t, tOr } = useI18n()
  const label = tOr(`kpi.${kpi.code}.label`, kpi.label)
  const delta = formatDelta(kpi)
  const trend = trendOf(kpi)
  const status = kpi.status ? STATUS[kpi.status] : null
  const Arrow = kpi.delta === null || kpi.delta === 0 ? ArrowRight : kpi.delta > 0 ? ArrowUpRight : ArrowDownRight

  const content = (
    <>
      <p className="flex items-start justify-between gap-2 text-sm text-slate-500">
        {label}
        {status && <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[11px] font-medium ${status.badge}`}>{t(status.label)}</span>}
      </p>
      {kpi.pending
        ? <p className="mt-2 text-sm font-medium text-slate-500">{t('dash.kpiPending')}</p>
        : <p className="mt-1 text-2xl font-semibold text-slate-900">{formatKpi(kpi.value, kpi.unit)}</p>}
      {kpi.based_on !== null && kpi.based_on !== undefined && !kpi.pending && (
        <p className="mt-1 text-xs text-slate-500">{t('dash.basedOn', { count: kpi.based_on, n: formatInteger(kpi.based_on) })}</p>
      )}
      {!kpi.pending && kpi.target !== null && kpi.target !== undefined && (
        <p className="mt-1 text-xs text-slate-500">{t('dash.target', { value: formatKpi(kpi.target, kpi.unit) })}</p>
      )}
      {comparison && !kpi.pending && (delta && trend ? (
        <p className={`mt-2 flex flex-wrap items-center gap-x-1 text-xs ${TREND_STYLE[trend].className}`}
          title={t('dash.previous', { value: formatKpi(kpi.previous, kpi.unit) })}>
          <Arrow className="size-3.5" aria-hidden />
          <span className="font-medium">{delta}</span>
          <span>{t(TREND_STYLE[trend].label)}</span>
          <span className="text-slate-400">{t('dash.vsPrevious')}</span>
        </p>
      ) : (
        <p className="mt-2 text-xs text-slate-400">{t('dash.noPrevious')}</p>
      ))}
    </>
  )
  return (
    <div role="group" aria-label={label} data-status={kpi.status ?? undefined}
      className={`rounded-xl border border-slate-200 bg-white ${status ? `border-l-4 ${status.className}` : ''}${href ? 'transition-colors focus-within:ring-2 focus-within:ring-brand-100 hover:border-brand-500' : ''}`}>
      {href
        ? <Link to={href} className="block p-4 focus:outline-none" title={t('dash.kpiDrill')}>{content}</Link>
        : <div className="p-4">{content}</div>}
    </div>
  )
}

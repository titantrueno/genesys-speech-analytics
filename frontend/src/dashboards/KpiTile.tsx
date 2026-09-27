import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react'
import type { KpiSummary } from '../api/metrics'
import { formatDelta, formatKpi, trendOf } from '../lib/format'

const TREND_STYLE = {
  mejora: { className: 'text-[var(--status-good-text)]', label: 'Mejora' },
  empeora: { className: 'text-[var(--status-critical)]', label: 'Empeora' },
  estable: { className: 'text-slate-500', label: 'Estable' },
} as const

export function KpiTile({ kpi }: { kpi: KpiSummary }) {
  const delta = formatDelta(kpi)
  const trend = trendOf(kpi)
  const Arrow = kpi.delta === null || kpi.delta === 0 ? ArrowRight : kpi.delta > 0 ? ArrowUpRight : ArrowDownRight

  return (
    <div role="group" aria-label={kpi.label} className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-sm text-slate-500">{kpi.label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{formatKpi(kpi.value, kpi.unit)}</p>
      {delta && trend ? (
        <p className={`mt-2 flex flex-wrap items-center gap-x-1 text-xs ${TREND_STYLE[trend].className}`}
          title={`Periodo anterior: ${formatKpi(kpi.previous, kpi.unit)}`}>
          <Arrow className="size-3.5" aria-hidden />
          <span className="font-medium">{delta}</span>
          <span>{TREND_STYLE[trend].label}</span>
          <span className="text-slate-400">vs periodo anterior</span>
        </p>
      ) : (
        <p className="mt-2 text-xs text-slate-400">Sin datos del periodo anterior</p>
      )}
    </div>
  )
}

import { Link, useNavigate } from 'react-router'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from 'recharts'
import type { KpiUnit, TimeseriesResponse } from '../api/metrics'
import { formatKpi, formatShortDate } from '../lib/format'
import { EmptyState } from './bars'

export { EmptyState, RankedBars, type BarItem } from './bars'

export function SplitBar({ label, parts, hrefFor }: {
  label: string
  parts: Array<{ key: string; label: string; value: number; color: string }>
  hrefFor: (key: string) => string
}) {
  const navigate = useNavigate()
  const total = parts.reduce((sum, p) => sum + p.value, 0)
  if (total === 0) return <EmptyState />
  return (
    <div>
      <div role="img" aria-label={`${label}: ${parts.map((p) => `${p.label} ${p.value}`).join(', ')}`} className="flex h-6 gap-0.5">
        {parts.map((p) => (
          <div key={p.key} className="h-full cursor-pointer first:rounded-l last:rounded-r hover:opacity-80" title={`${p.label}: ${p.value}`}
            onClick={() => navigate(hrefFor(p.key))}
            style={{ width: `${(p.value / total) * 100}%`, background: p.color }} />
        ))}
      </div>
      <ul aria-label={label} className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {parts.map((p) => (
          <li key={p.key}>
            <Link to={hrefFor(p.key)} className="flex items-center gap-2 text-slate-700 hover:text-brand-700">
              <span aria-hidden className="size-2.5 rounded-sm" style={{ background: p.color }} />
              {p.label}
              <span className="text-slate-500 tabular-nums">{p.value} · {Math.round((p.value / total) * 100)} %</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

function TimeseriesTooltip({ active, payload, unit }: TooltipContentProps & { unit: KpiUnit }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload as TimeseriesResponse['points'][number]
  const days = (Date.parse(point.period_end) - Date.parse(point.period_start)) / 86_400_000 + 1
  const range = point.period_start === point.period_end
    ? formatShortDate(point.period_start)
    : `${formatShortDate(point.period_start)} – ${formatShortDate(point.period_end)}${days < 7 ? ' (semana parcial)' : ''}`
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-md">
      <p className="text-sm font-semibold text-slate-900">{formatKpi(point.value, unit)}</p>
      <p className="text-slate-500">{range}</p>
    </div>
  )
}

export function TimeseriesChart({ points, unit, hrefFor }: {
  points: TimeseriesResponse['points']
  unit: KpiUnit
  hrefFor: (point: TimeseriesResponse['points'][number]) => string
}) {
  const navigate = useNavigate()
  if (points.length === 0) return <EmptyState />
  return (
    <div className="h-60">
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 240 }}>
        <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} className="cursor-pointer"
          onClick={(state) => {
            const point = points[Number(state.activeIndex)]
            if (point) navigate(hrefFor(point))
          }}>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="period_start" tickFormatter={formatShortDate} stroke="var(--chart-axis)"
            tick={{ fill: 'var(--chart-muted)', fontSize: 11 }} tickLine={false} minTickGap={24} />
          <YAxis stroke="var(--chart-axis)" tick={{ fill: 'var(--chart-muted)', fontSize: 11 }} tickLine={false} axisLine={false}
            width={48} tickFormatter={(v: number) => formatKpi(v, unit)} domain={unit === '1-5' ? [1, 5] : ['auto', 'auto']} />
          <Tooltip cursor={{ stroke: 'var(--chart-axis)', strokeWidth: 1 }}
            content={(props) => <TimeseriesTooltip {...props} unit={unit} />} />
          <Area type="monotone" dataKey="value" stroke="var(--series-1)" strokeWidth={2} fill="var(--series-1)"
            fillOpacity={0.1} connectNulls activeDot={{ r: 4, stroke: 'var(--chart-surface)', strokeWidth: 2 }} dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

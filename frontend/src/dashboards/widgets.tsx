import { useBreakdown, useSummary, useTimeseries, type Dimension, type KpiCode } from '../api/metrics'
import { formatKpi, formatShortDate } from '../lib/format'
import { ChartCard, DataTable } from './ChartCard'
import { RankedBars, SplitBar, TimeseriesChart } from './charts'
import { KpiTile } from './KpiTile'
import { KPI_META } from './kpiMeta'
import { useDashboardFilters } from './useDashboardFilters'

const CHANNEL_COLORS: Record<string, { label: string; color: string }> = {
  voz: { label: 'Voz', color: 'var(--series-1)' },
  chat: { label: 'Chat', color: 'var(--series-2)' },
}

export function KpiRow({ codes }: { codes: KpiCode[] }) {
  const { filters } = useDashboardFilters()
  const { data, isFetching } = useSummary(filters)
  if (!data) return <div className="h-28 animate-pulse rounded-xl bg-slate-100" />
  const byCode = new Map(data.kpis.map((k) => [k.code, k]))
  return (
    <div className={`grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6 ${isFetching ? 'opacity-60' : ''}`}>
      {codes.map((code) => byCode.get(code)).filter((k) => k !== undefined).map((kpi) => <KpiTile key={kpi.code} kpi={kpi} />)}
    </div>
  )
}

export function TimeseriesWidget({ kpi, title }: { kpi: KpiCode; title: string }) {
  const { filters, granularity, update } = useDashboardFilters()
  const { data, isFetching } = useTimeseries(kpi, granularity, filters)
  const unit = KPI_META[kpi].unit
  const points = data?.points ?? []
  const toggle = (
    <div className="flex rounded-md border border-slate-200 p-0.5 text-xs">
      {(['day', 'week'] as const).map((g) => (
        <button key={g} type="button" aria-pressed={granularity === g}
          onClick={() => update({ granularity: g === 'week' ? 'week' : undefined })}
          className={`rounded px-2 py-0.5 ${granularity === g ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
          {g === 'day' ? 'Día' : 'Semana'}
        </button>
      ))}
    </div>
  )
  return (
    <ChartCard title={title} subtitle={granularity === 'day' ? 'Por día' : 'Por semana'} actions={toggle} loading={isFetching}
      className="lg:col-span-2"
      table={<DataTable caption={title} columns={[granularity === 'day' ? 'Día' : 'Semana', KPI_META[kpi].short]}
        rows={points.map((p) => [
          p.period_start === p.period_end ? formatShortDate(p.period_start) : `${formatShortDate(p.period_start)} – ${formatShortDate(p.period_end)}`,
          formatKpi(p.value, unit),
        ])} />}>
      <TimeseriesChart points={points} unit={unit} />
    </ChartCard>
  )
}

export function BreakdownBars({ title, dimension, kpi, order = 'desc', diverging = false, subtitle }: {
  title: string; dimension: Dimension; kpi: KpiCode; order?: 'asc' | 'desc'; diverging?: boolean; subtitle?: string
}) {
  const { filters } = useDashboardFilters()
  const { data, isFetching } = useBreakdown(dimension, filters)
  const unit = KPI_META[kpi].unit
  const items = (data?.items ?? [])
    .map((i) => ({ key: i.key, label: i.label, value: i.kpis[kpi] }))
    .sort((a, b) => (order === 'desc' ? (b.value ?? 0) - (a.value ?? 0) : (a.value ?? 0) - (b.value ?? 0)))
  const format = (v: number | null) => formatKpi(v, unit)
  return (
    <ChartCard title={title} subtitle={subtitle} loading={isFetching}
      table={<DataTable caption={title} columns={['', KPI_META[kpi].short]} rows={items.map((i) => [i.label, format(i.value)])} />}>
      <RankedBars label={title} items={items} format={format} diverging={diverging}
        maxValue={unit === '%' ? 100 : unit === '1-5' ? 5 : undefined} />
    </ChartCard>
  )
}

export function ChannelSplit() {
  const { filters } = useDashboardFilters()
  const { data, isFetching } = useBreakdown('channel', filters)
  const parts = ['voz', 'chat'].map((code) => ({
    key: code, label: CHANNEL_COLORS[code].label, color: CHANNEL_COLORS[code].color,
    value: data?.items.find((i) => i.key === code)?.kpis.volume ?? 0,
  }))
  return (
    <ChartCard title="Volumen por canal" loading={isFetching}
      table={<DataTable caption="Volumen por canal" columns={['Canal', 'Volumen']} rows={parts.map((p) => [p.label, formatKpi(p.value, 'conversaciones')])} />}>
      <SplitBar label="Volumen por canal" parts={parts} />
    </ChartCard>
  )
}

export function ComplianceChecks() {
  const { filters } = useDashboardFilters()
  const { data, isFetching } = useSummary(filters)
  const items = (data?.compliance_by_check ?? []).map((c) => ({ key: c.code, label: c.label, value: c.value }))
  const format = (v: number | null) => formatKpi(v, '%')
  return (
    <ChartCard title="Cumplimiento por check" subtitle="% de conversaciones en las que aplica y se cumple" loading={isFetching}
      table={<DataTable caption="Cumplimiento por check" columns={['Check', 'Cumplimiento']} rows={items.map((i) => [i.label, format(i.value)])} />}>
      <RankedBars label="Cumplimiento por check" items={items} format={format} maxValue={100} />
    </ChartCard>
  )
}

export function BreakdownTable({ title, dimension, codes }: { title: string; dimension: Dimension; codes: KpiCode[] }) {
  const { filters } = useDashboardFilters()
  const { data, isFetching } = useBreakdown(dimension, filters)
  return (
    <ChartCard title={title} loading={isFetching} className="lg:col-span-2">
      <DataTable caption={title} columns={['', ...codes.map((c) => KPI_META[c].short)]}
        rows={(data?.items ?? []).map((i) => [i.label, ...codes.map((c) => formatKpi(i.kpis[c], KPI_META[c].unit))])} />
    </ChartCard>
  )
}

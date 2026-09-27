import { NavLink, useParams } from 'react-router'
import { useSummary } from '../api/metrics'
import { NotFoundPage } from '../pages/NotFoundPage'
import { DASHBOARDS } from './definitions'
import { FilterBar } from './FilterBar'
import { useDashboardFilters } from './useDashboardFilters'

export function DashboardsPage() {
  const { dashboardId } = useParams()
  const { filters, search } = useDashboardFilters()
  const { data: summary } = useSummary(filters)
  const dashboard = DASHBOARDS.find((d) => d.id === dashboardId)
  if (!dashboard) return <NotFoundPage />

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Dashboards</h1>
          <p className="text-sm text-slate-500">{dashboard.description}</p>
        </div>
        <nav aria-label="Dashboards" className="flex rounded-lg border border-slate-200 bg-white p-1">
          {DASHBOARDS.map((d) => (
            <NavLink key={d.id} to={{ pathname: `/dashboards/${d.id}`, search }}
              className={({ isActive }) => `rounded-md px-3 py-1.5 text-sm ${isActive ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
              {d.title}
            </NavLink>
          ))}
        </nav>
      </header>
      <FilterBar effectivePeriod={summary?.period} />
      <div className="space-y-4">{dashboard.render()}</div>
    </div>
  )
}

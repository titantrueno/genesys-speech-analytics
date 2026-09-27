import { Navigate, useLocation } from 'react-router'

export const DEFAULT_DASHBOARD_ID = 'vision-general'

export function DashboardsIndex() {
  const { search } = useLocation()
  return <Navigate to={`${DEFAULT_DASHBOARD_ID}${search}`} replace />
}

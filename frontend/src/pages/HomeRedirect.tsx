import { Navigate } from 'react-router'
import { useAuth } from '../auth/useAuth'
import { NAV_ITEMS } from '../layout/navigation'
import { ForbiddenPage } from './ForbiddenPage'

export function HomeRedirect() {
  const { can } = useAuth()
  const first = NAV_ITEMS.find((item) => can(item.permission))
  return first ? <Navigate to={first.path} replace /> : <ForbiddenPage />
}

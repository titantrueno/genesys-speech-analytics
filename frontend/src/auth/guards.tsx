import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { ForbiddenPage } from '../pages/ForbiddenPage'
import { LoadingScreen } from '../layout/LoadingScreen'
import { useAuth } from './useAuth'
import type { Permission } from './types'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <LoadingScreen />
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location }} />
  return children
}

export function RequirePermission({ permission, children }: { permission: Permission; children: ReactNode }) {
  const { can } = useAuth()
  return can(permission) ? children : <ForbiddenPage />
}

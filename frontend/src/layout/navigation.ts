import { LayoutDashboard, ListFilter, MessagesSquare, ScanSearch, Settings, Users, Workflow, type LucideIcon } from 'lucide-react'
import type { Permission } from '../auth/types'
import type { TKey } from '../i18n/dictionaries'

export interface NavItem {
  path: string
  labelKey: TKey
  permission: Permission
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { path: '/dashboards', labelKey: 'layout.nav.dashboards', permission: 'dashboards:view', icon: LayoutDashboard },
  { path: '/conversaciones', labelKey: 'layout.nav.conversations', permission: 'conversations:view', icon: MessagesSquare },
  { path: '/explorador', labelKey: 'layout.nav.explorer', permission: 'explorer:use', icon: ListFilter },
  { path: '/busqueda', labelKey: 'layout.nav.search', permission: 'search:use', icon: ScanSearch },
  { path: '/flujos', labelKey: 'layout.nav.flows', permission: 'flows:view', icon: Workflow },
  { path: '/configuracion', labelKey: 'layout.nav.config', permission: 'config:view', icon: Settings },
  { path: '/usuarios', labelKey: 'layout.nav.users', permission: 'users:admin', icon: Users },
]

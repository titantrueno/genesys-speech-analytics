import { LayoutDashboard, ListFilter, MessagesSquare, ScanSearch, Settings, Users, Workflow, type LucideIcon } from 'lucide-react'
import type { Permission } from '../auth/types'

export interface NavItem {
  path: string
  label: string
  description: string
  permission: Permission
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { path: '/dashboards', label: 'Dashboards', permission: 'dashboards:view', icon: LayoutDashboard,
    description: 'KPIs agregados de la atención al cliente con drill-down a las conversaciones.' },
  { path: '/conversaciones', label: 'Conversaciones', permission: 'conversations:view', icon: MessagesSquare,
    description: 'Listado de conversaciones transcritas y su análisis detallado.' },
  { path: '/explorador', label: 'Explorador', permission: 'explorer:use', icon: ListFilter,
    description: 'Consultas asistidas en tiempo real sobre las conversaciones de un intervalo.' },
  { path: '/busqueda', label: 'Búsqueda semántica', permission: 'search:use', icon: ScanSearch,
    description: 'Encuentra conversaciones por significado, no solo por palabras exactas.' },
  { path: '/flujos', label: 'Flujos de insights', permission: 'flows:view', icon: Workflow,
    description: 'Diseña flujos de sampling, prompting y output para generar insights.' },
  { path: '/configuracion', label: 'Configuración', permission: 'config:view', icon: Settings,
    description: 'Taxonomía, objetivos de KPI, cumplimiento, privacidad y conectores.' },
  { path: '/usuarios', label: 'Usuarios y roles', permission: 'users:admin', icon: Users,
    description: 'Gestión de usuarios, roles y permisos de la plataforma.' },
]

import type { ManagedUser, PermissionOption, RoleItem } from '../users/types'
import { ALL_PERMISSIONS } from './utils'

export const PERMISSION_OPTIONS: PermissionOption[] = [
  { value: 'dashboards:view', label: 'Ver dashboards' },
  { value: 'conversations:view', label: 'Ver conversaciones' },
  { value: 'explorer:use', label: 'Usar el explorador' },
  { value: 'search:use', label: 'Usar la búsqueda semántica' },
  { value: 'flows:view', label: 'Ver flujos' },
  { value: 'flows:edit', label: 'Editar y ejecutar flujos' },
  { value: 'config:view', label: 'Ver configuración' },
  { value: 'config:edit', label: 'Editar configuración' },
  { value: 'users:admin', label: 'Administrar usuarios y roles' },
]

export const ROLES: RoleItem[] = [
  { id: '1RO-00000001-0000-5000-8000-000000000001', code: 'admin', name: 'Administrador', builtin: true, permissions: ALL_PERMISSIONS, users: 1 },
  {
    id: '1RO-00000002-0000-5000-8000-000000000002', code: 'supervisor', name: 'Supervisor', builtin: true, users: 1,
    permissions: ALL_PERMISSIONS.filter((p) => p !== 'config:edit' && p !== 'users:admin'),
  },
  {
    id: '1RO-00000003-0000-5000-8000-000000000003', code: 'analista', name: 'Analista', builtin: true, users: 1,
    permissions: ['dashboards:view', 'conversations:view', 'explorer:use', 'search:use', 'flows:view', 'flows:edit'],
  },
  { id: '1RO-00000004-0000-5000-8000-000000000004', code: 'viewer', name: 'Consulta', builtin: true, permissions: ['dashboards:view', 'conversations:view'], users: 1 },
  { id: '1RO-00000005-0000-5000-8000-000000000005', code: 'auditor', name: 'Auditor', builtin: false, permissions: ['config:view'], users: 0 },
]

export const MANAGED_USERS: ManagedUser[] = [
  { id: '1US-00000001-0000-5000-8000-000000000001', name: 'Admin Demo', email: 'admin@bancohorizonte.demo', role: 'admin', role_name: 'Administrador', active: true, last_login: '2026-10-01T08:15:00+00:00' },
  { id: '1US-00000003-0000-5000-8000-000000000003', name: 'Analista Demo', email: 'analista@bancohorizonte.demo', role: 'analista', role_name: 'Analista', active: true, last_login: null },
  { id: '1US-00000006-0000-5000-8000-000000000006', name: 'Bea Baja', email: 'bea@bancohorizonte.demo', role: 'viewer', role_name: 'Consulta', active: false, last_login: '2026-09-20T10:00:00+00:00' },
]

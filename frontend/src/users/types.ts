import type { Permission } from '../auth/types'

export interface ManagedUser {
  id: string
  name: string
  email: string
  role: string
  role_name: string
  active: boolean
  last_login: string | null
}

export type UserInput = Pick<ManagedUser, 'name' | 'email' | 'role' | 'active'>

export interface RoleItem {
  id: string
  code: string
  name: string
  builtin: boolean
  permissions: Permission[]
  users: number
}

export interface PermissionOption { value: Permission; label: string }

export interface RolesResponse { items: RoleItem[]; permissions: PermissionOption[] }

export interface UserFilters { q: string; role: string; active: '' | 'true' | 'false' }

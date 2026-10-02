export type Permission =
  | 'dashboards:view' | 'conversations:view' | 'explorer:use' | 'search:use'
  | 'flows:view' | 'flows:edit' | 'config:view' | 'config:edit' | 'users:admin'

export interface User {
  id: string
  name: string
  email: string
  role: string
  /** Nombre legible del rol, también de los personalizados (FE006). */
  role_name: string
  permissions: Permission[]
}

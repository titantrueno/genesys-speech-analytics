import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiRequest } from '../api/client'
import type { AuditEntry } from '../config/types'
import type { ManagedUser, RoleItem, RolesResponse, UserFilters, UserInput } from './types'

export function useUsers(filters: UserFilters) {
  return useQuery({
    queryKey: ['users', filters],
    queryFn: ({ signal }) => apiRequest<{ items: ManagedUser[] }>('/api/users', { query: { ...filters }, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useRoles() {
  return useQuery({
    queryKey: ['roles'],
    queryFn: ({ signal }) => apiRequest<RolesResponse>('/api/roles', { signal }),
  })
}

export function useUsersAudit() {
  return useQuery({
    queryKey: ['users-audit'],
    queryFn: ({ signal }) => apiRequest<{ items: AuditEntry[] }>('/api/users/audit', { signal }),
  })
}

/**
 * Escritura de usuarios o roles. Puede cambiar los permisos de quien la hace (y por tanto su menú y lo que puede
 * consultar), así que al guardar se invalidan todas las consultas en caché. La mutación sigue pendiente hasta que
 * termina esa recarga (`onSuccess` devuelve su promesa).
 */
export function useUsersMutation<TBody, TResult = unknown>(request: (body: TBody) => Promise<TResult>) {
  const client = useQueryClient()
  return useMutation({ mutationFn: request, onSuccess: () => client.invalidateQueries() })
}

export type RoleInput = { name: string; permissions: string[] }

export const userRequests = {
  createUser: (body: UserInput) => apiRequest<ManagedUser>('/api/users', { method: 'POST', body }),
  updateUser: ({ id, body }: { id: string; body: UserInput }) => apiRequest<ManagedUser>(`/api/users/${id}`, { method: 'PUT', body }),
  createRole: (body: RoleInput & { code: string }) => apiRequest<RoleItem>('/api/roles', { method: 'POST', body }),
  updateRole: ({ id, body }: { id: string; body: RoleInput }) => apiRequest<RoleItem>(`/api/roles/${id}`, { method: 'PUT', body }),
  deleteRole: (id: string) => apiRequest<void>(`/api/roles/${id}`, { method: 'DELETE' }),
}

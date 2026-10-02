import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { apiRequest, onAuthVersionChange, onUnauthorized, resetAuthVersion, tokenStorage } from '../api/client'
import { AuthContext, type AuthContextValue, type AuthState, type LoginResponse } from './context'
import type { User } from './types'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<AuthState>(() => ({
    status: tokenStorage.get() ? 'loading' : 'anonymous',
    user: null,
  }))

  const logout = useCallback(() => {
    tokenStorage.clear()
    queryClient.clear()
    setState({ status: 'anonymous', user: null })
  }, [queryClient])

  useEffect(() => onUnauthorized(logout), [logout])

  // Si cambian usuarios o roles, se vuelve a pedir el usuario: menú y acciones siguen a sus permisos sin recargar
  // ni mostrar la pantalla de carga (FE006). Un `401` ya cierra la sesión por `onUnauthorized`.
  useEffect(() => onAuthVersionChange(() => {
    apiRequest<User>('/api/auth/me')
      .then((user) => setState((current) => (current.status === 'authenticated' ? { status: 'authenticated', user } : current)))
      .catch(() => undefined)
  }), [])

  useEffect(() => {
    if (state.status !== 'loading') return
    const controller = new AbortController()
    resetAuthVersion()
    apiRequest<User>('/api/auth/me', { signal: controller.signal })
      .then((user) => setState({ status: 'authenticated', user }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          tokenStorage.clear()
          setState({ status: 'anonymous', user: null })
        }
        return error
      })
    return () => controller.abort()
  }, [state.status])

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiRequest<LoginResponse>('/api/auth/login', { method: 'POST', body: { email, password } })
    tokenStorage.set(response.access_token)
    setState({ status: 'authenticated', user: response.user })
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    ...state,
    login,
    logout,
    can: (permission) => state.user?.permissions.includes(permission) ?? false,
  }), [state, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

import { createContext } from 'react'
import type { Permission, User } from './types'

type Status = 'loading' | 'authenticated' | 'anonymous'

export interface AuthState {
  status: Status
  user: User | null
}

export interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  can: (permission: Permission) => boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export const AuthContext = createContext<AuthContextValue | null>(null)

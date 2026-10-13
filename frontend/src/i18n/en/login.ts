import type { login as es } from '../es/login'

export const login: Record<keyof typeof es, string> = {
  'login.subtitle': 'Banco Horizonte · Customer service',
  'login.email': 'Email',
  'login.password': 'Password',
  'login.submit': 'Sign in',
  'login.badCredentials': 'Wrong credentials',
  'login.unreachable': 'Could not connect to the server',
  'login.demo': 'Demo users · password “{password}”',
  'login.demo.admin': 'Administrator',
  'login.demo.supervisor': 'Supervisor',
  'login.demo.analyst': 'Analyst',
  'login.demo.viewer': 'Read-only',
}

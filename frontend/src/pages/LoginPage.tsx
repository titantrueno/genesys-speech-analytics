import { AudioLines, Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate, type Location } from 'react-router'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { DEFAULT_PLATFORM_NAME, usePublicConfig } from '../config/api'

const DEMO_ACCOUNTS = [
  { role: 'Administrador', email: 'admin@bancohorizonte.demo' },
  { role: 'Supervisor', email: 'supervisor@bancohorizonte.demo' },
  { role: 'Analista', email: 'analista@bancohorizonte.demo' },
  { role: 'Consulta', email: 'viewer@bancohorizonte.demo' },
]
const DEMO_PASSWORD = 'demo'

function redirectTarget(location: Location): string {
  const from = (location.state as { from?: Location } | null)?.from
  return from ? `${from.pathname}${from.search}` : '/'
}

export function LoginPage() {
  const { data: settings } = usePublicConfig()
  const { status, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authenticated') return <Navigate to={redirectTarget(location)} replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(redirectTarget(location), { replace: true })
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401
        ? 'Credenciales incorrectas'
        : 'No se ha podido conectar con el servidor')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-900 to-brand-700 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-brand-500 text-white">
            <AudioLines className="size-5" aria-hidden />
          </div>
          <div>
            <h1 className="text-lg font-semibold">{settings?.platform_name ?? DEFAULT_PLATFORM_NAME}</h1>
            <p className="text-sm text-slate-500">Banco Horizonte · Atención al cliente</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">Email</label>
            <input id="email" type="email" autoComplete="username" required value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none" />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">Contraseña</label>
            <input id="password" type="password" autoComplete="current-password" required value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 focus:border-brand-500 focus:ring-2 focus:ring-brand-100 focus:outline-none" />
          </div>
          {error && (
            <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
          )}
          <button type="submit" disabled={submitting}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-60">
            {submitting && <Loader2 className="size-4 animate-spin" aria-hidden />}
            Entrar
          </button>
        </form>

        <div className="mt-8 rounded-lg bg-slate-50 p-4">
          <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">Usuarios demo · contraseña «{DEMO_PASSWORD}»</p>
          <ul className="mt-2 space-y-1">
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.email}>
                <button type="button" onClick={() => { setEmail(account.email); setPassword(DEMO_PASSWORD) }}
                  className="text-left text-sm text-brand-600 hover:underline">
                  {account.role}: {account.email}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

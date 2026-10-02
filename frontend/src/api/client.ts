const TOKEN_KEY = 'sta.token'

export const API_URL: string = import.meta.env.VITE_API_URL ?? ''

const AUTH_VERSION_HEADER = 'X-Auth-Version'
let authVersion: string | null = null

/** Olvida la versión vista: la siguiente respuesta fija la referencia de una sesión nueva. */
export function resetAuthVersion() {
  authVersion = null
}

export const tokenStorage = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => { resetAuthVersion(); sessionStorage.setItem(TOKEN_KEY, token) },
  clear: () => { resetAuthVersion(); sessionStorage.removeItem(TOKEN_KEY) },
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

const unauthorizedListeners = new Set<() => void>()

export function onUnauthorized(listener: () => void): () => void {
  unauthorizedListeners.add(listener)
  return () => unauthorizedListeners.delete(listener)
}

const authVersionListeners = new Set<() => void>()

/** Avisa cuando cambian usuarios o roles en el backend (cabecera `X-Auth-Version`, FE006). */
export function onAuthVersionChange(listener: () => void): () => void {
  authVersionListeners.add(listener)
  return () => authVersionListeners.delete(listener)
}

function trackAuthVersion(response: Response) {
  const version = response.headers.get(AUTH_VERSION_HEADER)
  if (version === null) return
  const changed = authVersion !== null && version !== authVersion
  authVersion = version
  if (changed) authVersionListeners.forEach((listener) => listener())
}

type Query = Record<string, string | number | boolean | Array<string> | null | undefined>

export function buildQuery(params: Query = {}): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    for (const item of Array.isArray(value) ? value : [value]) search.append(key, String(item))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}

export async function apiRequest<T>(
  path: string,
  options: { method?: string; body?: unknown; query?: Query; signal?: AbortSignal } = {},
): Promise<T> {
  const headers = new Headers({ Accept: 'application/json' })
  const token = tokenStorage.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')

  const response = await fetch(`${API_URL}${path}${buildQuery(options.query)}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  })

  trackAuthVersion(response)
  if (!response.ok) {
    const detail = await response.json().then((b) => b?.detail, () => undefined)
    if (response.status === 401 && token) unauthorizedListeners.forEach((listener) => listener())
    throw new ApiError(response.status, typeof detail === 'string' ? detail : `Error ${response.status}`, detail)
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

import { tokenStorage } from '../../api/client'

/** Lo que la pestaña «API» lee de `/openapi.json`; el resto del documento pasa tal cual a Swagger UI. */
export type OpenApiDoc = {
  openapi: string
  info: { title: string; version: string; description?: string }
  paths: Record<string, Record<string, unknown>>
  tags?: Array<{ name: string; description?: string }>
  servers?: Array<{ url: string }>
  [key: string]: unknown
}

type Operation = { summary?: string; description?: string; tags?: string[] }

export type OperationRef = { method: string; path: string; operation: Operation }

export type SpecFilter = { text: string; tag: string }

/** Petición de «Probar» tal como la entrega Swagger UI (`url`, `method`, `headers`, `body`…). */
export type SwaggerRequest = { headers?: Record<string, string>; [key: string]: unknown }

const HTTP_METHODS = new Set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'])

/** Minúsculas y sin tildes, para buscar como en el resto de la app. */
function normalize(value: string): string {
  return value.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

/** Operaciones en el orden del documento; ignora claves comunes de la ruta como `parameters`. */
export function listOperations(spec: OpenApiDoc): OperationRef[] {
  return Object.entries(spec.paths).flatMap(([path, item]) =>
    Object.entries(item)
      .filter(([method]) => HTTP_METHODS.has(method))
      .map(([method, operation]) => ({ method: method.toUpperCase(), path, operation: operation as Operation })),
  )
}

export function countOperations(spec: OpenApiDoc): number {
  return listOperations(spec).length
}

/**
 * Poda la especificación a las operaciones del dominio (`tag`) que contienen el texto en su ruta, método, resumen,
 * descripción (donde está el permiso) o dominio, sin distinguir mayúsculas ni tildes. Quita rutas y dominios vacíos.
 */
export function filterSpec(spec: OpenApiDoc, { text, tag }: SpecFilter): OpenApiDoc {
  const needle = normalize(text.trim())
  const tagText = new Map((spec.tags ?? []).map((t) => [t.name, `${t.name} ${t.description ?? ''}`]))
  const matches = ({ method, path, operation }: OperationRef) => {
    const tags = operation.tags ?? []
    if (tag && !tags.includes(tag)) return false
    if (!needle) return true
    const haystack = [path, method, operation.summary ?? '', operation.description ?? '', ...tags.map((t) => tagText.get(t) ?? t)]
    return normalize(haystack.join(' ')).includes(needle)
  }

  const paths: OpenApiDoc['paths'] = {}
  const usedTags = new Set<string>()
  for (const [path, item] of Object.entries(spec.paths)) {
    const kept = Object.entries(item).filter(([key, operation]) => {
      if (!HTTP_METHODS.has(key)) return true
      const ref = { method: key.toUpperCase(), path, operation: operation as Operation }
      if (!matches(ref)) return false
      ref.operation.tags?.forEach((t) => usedTags.add(t))
      return true
    })
    if (kept.some(([key]) => HTTP_METHODS.has(key))) paths[path] = Object.fromEntries(kept)
  }
  return { ...spec, paths, tags: spec.tags?.filter((t) => usedTags.has(t.name)) }
}

/** «Probar» llama a la misma API que la app: el origen y el proxy, o `VITE_API_URL` si está definida. */
export function withServer(spec: OpenApiDoc, apiUrl: string): OpenApiDoc {
  return apiUrl ? { ...spec, servers: [{ url: apiUrl.replace(/\/+$/, '') }] } : spec
}

/** Añade el token de la sesión vigente, leído en cada petición; respeta uno puesto a mano con «Authorize». */
export function authInterceptor(request: SwaggerRequest): SwaggerRequest {
  const headers = request.headers ?? {}
  request.headers = headers
  const token = tokenStorage.get()
  if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`
  return request
}

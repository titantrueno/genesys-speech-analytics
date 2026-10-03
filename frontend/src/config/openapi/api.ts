import { useQuery } from '@tanstack/react-query'
import { API_URL } from '../../api/client'
import type { OpenApiDoc } from './spec'

/** URL de la especificación que sirve el backend (pública, fuera de `/api`; el proxy de Vite la reenvía). */
export const OPENAPI_URL = `${API_URL}/openapi.json`

/** Especificación OpenAPI de la API en marcha; no cambia mientras corre, así que no se vuelve a pedir. */
export function useOpenApiSpec() {
  return useQuery({
    queryKey: ['openapi-spec'],
    queryFn: async ({ signal }) => {
      const response = await fetch(OPENAPI_URL, { headers: { Accept: 'application/json' }, signal })
      if (!response.ok) throw new Error(`Error ${response.status}`)
      return (await response.json()) as OpenApiDoc
    },
    staleTime: Infinity,
  })
}

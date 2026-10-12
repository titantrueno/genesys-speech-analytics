import { useQueryClient } from '@tanstack/react-query'
import { useSyncExternalStore } from 'react'
import { Link } from 'react-router'
import { isDataUnavailable } from './dataErrors'

export function DataUnavailable({ error }: { error: unknown }) {
  if (!isDataUnavailable(error)) return null
  return (
    <div role="alert" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
      <p className="font-medium">{error.message}</p>
      <p>
        La plataforma está usando las conversaciones reales y PostgreSQL no responde. Puedes volver a los datos
        sintéticos en{' '}
        <Link to="/configuracion?tab=fuentes" className="font-medium underline">Configuración · Fuentes de datos</Link>.
      </p>
    </div>
  )
}

/** Aviso único sobre el contenido: aparece cuando alguna consulta de datos ha caído con `503` y se va al recuperarse. */
export function DataUnavailableBanner() {
  const cache = useQueryClient().getQueryCache()
  const failed = useSyncExternalStore(
    (notify) => cache.subscribe(notify),
    () => cache.findAll({ predicate: (query) => isDataUnavailable(query.state.error) }).find(Boolean)?.state.error ?? null,
  )
  return failed ? <DataUnavailable error={failed} /> : null
}

import SwaggerUI from 'swagger-ui-react'
import 'swagger-ui-react/swagger-ui.css'
import { useOpenApiSpec } from '../openapi/api'
import { SpecLoading } from '../openapi/SpecLoading'
import { countOperations } from '../openapi/spec'

/** Especificación OpenAPI de la API en marcha, con Swagger UI (FE010). */
export function ApiTab() {
  const { data: spec, isError, isPending } = useOpenApiSpec()

  if (isPending) return <SpecLoading />
  if (isError) {
    return <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">No se ha podido cargar la especificación de la API.</p>
  }
  return (
    <section aria-label="Especificación de la API" className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">
        <span className="font-medium text-slate-900">{spec.info.title}</span>
        {` · versión ${spec.info.version} · ${countOperations(spec)} operaciones`}
      </p>
      <SwaggerUI spec={spec} />
    </section>
  )
}

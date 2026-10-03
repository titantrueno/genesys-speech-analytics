import { useDeferredValue, useMemo, useState } from 'react'
import SwaggerUI from 'swagger-ui-react'
import 'swagger-ui-react/swagger-ui.css'
import { API_URL } from '../../api/client'
import { ConfigField, input } from '../controls'
import { useOpenApiSpec } from '../openapi/api'
import { SpecLoading } from '../openapi/SpecLoading'
import { authInterceptor, countOperations, filterSpec, withServer, type OpenApiDoc } from '../openapi/spec'

/** Especificación OpenAPI de la API en marcha, con Swagger UI (FE010). */
export function ApiTab() {
  const { data: spec, isError, isPending } = useOpenApiSpec()

  if (isPending) return <SpecLoading />
  if (isError) {
    return <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">No se ha podido cargar la especificación de la API.</p>
  }
  return <SpecViewer spec={spec} />
}

function SpecViewer({ spec }: { spec: OpenApiDoc }) {
  const [text, setText] = useState('')
  const [tag, setTag] = useState('')
  const deferredText = useDeferredValue(text)
  const filtered = useMemo(() => withServer(filterSpec(spec, { text: deferredText, tag }), API_URL), [spec, deferredText, tag])
  const total = countOperations(spec)
  const shown = countOperations(filtered)

  return (
    <section aria-label="Especificación de la API" className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">
        <span className="font-medium text-slate-900">{spec.info.title}</span>
        {` · versión ${spec.info.version} · ${shown === total ? '' : `${shown} de `}${total} operaciones`}
      </p>
      <p role="note" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
        «Try it out» hace llamadas reales a la API en marcha con tu sesión: las escrituras cambian su estado y quedan en la auditoría.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-72">
          <ConfigField label="Buscar operaciones">
            <input className={input} type="search" placeholder="Ruta, método, descripción o permiso" value={text}
              onChange={(e) => setText(e.target.value)} />
          </ConfigField>
        </div>
        <div className="w-80">
          <ConfigField label="Dominio">
            <select className={input} value={tag} onChange={(e) => setTag(e.target.value)}>
              <option value="">Todos los dominios</option>
              {(spec.tags ?? []).map((t) => (
                <option key={t.name} value={t.name}>{t.description ? `${t.name} · ${t.description}` : t.name}</option>
              ))}
            </select>
          </ConfigField>
        </div>
      </div>
      {shown === 0
        ? <p className="text-sm text-slate-500">Ninguna operación coincide con la búsqueda.</p>
        : (
          // Token de la sesión en cada llamada, sin guardarlo; sin deep linking (no toca la URL de la app) y sin la
          // sección «Schemas», que en React 19 rompe el orden de hooks (los modelos siguen en cada operación).
          <SwaggerUI spec={filtered} requestInterceptor={authInterceptor} persistAuthorization={false} deepLinking={false}
            tryItOutEnabled={false} defaultModelsExpandDepth={-1} />
        )}
    </section>
  )
}

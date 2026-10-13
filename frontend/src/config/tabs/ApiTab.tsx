import { useDeferredValue, useMemo, useState } from 'react'
import SwaggerUI from 'swagger-ui-react'
import 'swagger-ui-react/swagger-ui.css'
import { API_URL } from '../../api/client'
import { useI18n } from '../../i18n/useI18n'
import { ConfigField, input } from '../controls'
import { useOpenApiSpec } from '../openapi/api'
import { SpecLoading } from '../openapi/SpecLoading'
import { authInterceptor, countOperations, filterSpec, withServer, type OpenApiDoc, type SwaggerRequest } from '../openapi/spec'

/** Swagger UI lee el interceptor una sola vez, al montar: una función estable que lee la sesión en cada llamada. */
const requestInterceptor = (request: SwaggerRequest) => authInterceptor(request, API_URL)

/** Especificación OpenAPI de la API en marcha, con Swagger UI (FE010). */
export function ApiTab() {
  const { t } = useI18n()
  const { data: spec, isError, isPending } = useOpenApiSpec()

  if (isPending) return <SpecLoading />
  if (isError) {
    return <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{t('cfg.api.loadError')}</p>
  }
  return <SpecViewer spec={spec} />
}

function SpecViewer({ spec }: { spec: OpenApiDoc }) {
  const { t } = useI18n()
  const [text, setText] = useState('')
  const [tag, setTag] = useState('')
  const deferredText = useDeferredValue(text)
  const filtered = useMemo(() => withServer(filterSpec(spec, { text: deferredText, tag }), API_URL), [spec, deferredText, tag])
  const total = countOperations(spec)
  const shown = countOperations(filtered)

  return (
    <section aria-label={t('cfg.api.aria')} className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">
        <span className="font-medium text-slate-900">{spec.info.title}</span>
        {t('cfg.api.version', { version: spec.info.version })}{shown === total ? t('cfg.api.opsAll', { total }) : t('cfg.api.opsSome', { shown, total })}
      </p>
      <p role="note" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
        {t('cfg.api.note')}
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-72">
          <ConfigField label={t('cfg.api.search')}>
            <input className={input} type="search" placeholder={t('cfg.api.searchPlaceholder')} value={text}
              onChange={(e) => setText(e.target.value)} />
          </ConfigField>
        </div>
        <div className="w-80">
          <ConfigField label={t('cfg.api.domain')}>
            <select className={input} value={tag} onChange={(e) => setTag(e.target.value)}>
              <option value="">{t('cfg.api.allDomains')}</option>
              {(spec.tags ?? []).map((tag) => (
                <option key={tag.name} value={tag.name}>{tag.description ? `${tag.name} · ${tag.description}` : tag.name}</option>
              ))}
            </select>
          </ConfigField>
        </div>
      </div>
      {shown === 0
        ? <p className="text-sm text-slate-500">{t('cfg.api.noMatch')}</p>
        : (
          // Token de la sesión en cada llamada, sin guardarlo; sin deep linking (no toca la URL de la app) y sin la
          // sección «Schemas», que en React 19 rompe el orden de hooks (los modelos siguen en cada operación).
          <SwaggerUI spec={filtered} requestInterceptor={requestInterceptor} persistAuthorization={false} deepLinking={false}
            tryItOutEnabled={false} defaultModelsExpandDepth={-1} />
        )}
    </section>
  )
}

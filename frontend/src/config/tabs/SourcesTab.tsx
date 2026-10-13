import { useState, type ReactNode } from 'react'
import { ApiError } from '../../api/client'
import { useGenesysConnector, useTestGenesys } from '../../downloads/api'
import { CHANNEL_KEYS, DOWNLOAD_STATUS, QUALITY_KEYS, splitCounts } from '../../downloads/labels'
import { useI18n } from '../../i18n/useI18n'
import { StatusBadge } from '../../flows/StatusBadge'
import { formatDateTime, formatInteger } from '../../lib/format'
import { configRequests, useConfigMutation, useConnectors } from '../api'
import { Card } from '../controls'
import type { DataOrigin, PlatformConfig } from '../types'

function MockConnectors({ canEdit }: { canEdit: boolean }) {
  const { t, tOr } = useI18n()
  const { data, isError, isPending } = useConnectors()
  const sync = useConfigMutation(configRequests.sync)
  return (
    <Card title={t('cfg.mock.title')}
      description={t('cfg.mock.description')}>
      {isPending && <p className="text-sm text-slate-500">{t('cfg.mock.loading')}</p>}
      {isError && <p role="alert" className="text-sm text-red-700">{t('cfg.mock.error')}</p>}
      {data && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {(['cfg.mock.col.connector', 'cfg.status', 'cfg.mock.col.lastSync', 'cfg.conversations', ...(canEdit ? ['cfg.actions' as const] : [])] as const).map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 font-medium">{t(label)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((connector) => (
                <tr key={connector.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-2 py-2 font-medium text-slate-800">{connector.name}</td>
                  <td className="px-2 py-2">
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
                      {tOr(`cfg.connector.${connector.status}`, connector.status)}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-slate-600">{formatDateTime(connector.last_sync)}</td>
                  <td className="px-2 py-2 tabular-nums">{formatInteger(connector.conversations)}</td>
                  {canEdit && (
                    <td className="px-2 py-2">
                      <button type="button" disabled={sync.isPending} onClick={() => sync.mutate(connector.id)}
                        aria-label={t('cfg.mock.syncAria', { name: connector.name })}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50">
                        {t('cfg.mock.sync')}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {sync.isError && <p role="alert" className="text-sm text-red-700">{t('cfg.mock.syncError')}</p>}
    </Card>
  )
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[12rem_1fr] gap-2 border-b border-slate-100 py-1.5 last:border-0">
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-800">{children}</dd>
    </div>
  )
}

/** Conector real (FE011): estado del servicio de ingesta, credenciales, última descarga y conversaciones guardadas. */
function GenesysCard({ canEdit }: { canEdit: boolean }) {
  const { t } = useI18n()
  const { data, isError, isPending } = useGenesysConnector()
  const test = useTestGenesys()
  const result = test.data
  return (
    <Card title={t('cfg.gc.title')}
      description={t('cfg.gc.description')}>
      {isPending && <p className="text-sm text-slate-500">{t('cfg.gc.loading')}</p>}
      {isError && <p role="alert" className="text-sm text-red-700">{t('cfg.gc.error')}</p>}
      {data && data.service === 'no_disponible' && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t('cfg.gc.unavailable')}
        </p>
      )}
      {data && data.service === 'disponible' && (
        <dl>
          <Item label={t('cfg.gc.service')}>
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">{t('cfg.gc.available')}</span>
          </Item>
          <Item label={t('cfg.gc.region')}>{data.region ?? '—'}</Item>
          <Item label={t('cfg.gc.credentials')}>{data.credentials_configured ? t('cfg.gc.configured') : t('cfg.gc.notConfigured')}</Item>
          <Item label={t('cfg.gc.lastTest')}>
            {data.last_test
              ? `${data.last_test.ok ? t('cfg.gc.testOk') : t('cfg.gc.testFailed')} · ${formatDateTime(data.last_test.at)}`
                + (data.last_test.organization ? ` · ${data.last_test.organization}` : '')
              : t('cfg.gc.untested')}
          </Item>
          <Item label={t('cfg.gc.lastDownload')}>
            {data.last_download?.finished_at ? (
              <span className="inline-flex items-center gap-2">
                {formatDateTime(data.last_download.finished_at)}
                <StatusBadge label={t(DOWNLOAD_STATUS[data.last_download.status].label)} className={DOWNLOAD_STATUS[data.last_download.status].className} />
              </span>
            ) : t('cfg.gc.none')}
          </Item>
          {data.conversations && (
            <>
              <Item label={t('cfg.gc.saved')}>{formatInteger(data.conversations.total)}</Item>
              <Item label={t('cfg.gc.byChannel')}>{splitCounts(t, data.conversations.by_channel, CHANNEL_KEYS)}</Item>
              <Item label={t('cfg.gc.byQuality')}>{splitCounts(t, data.conversations.by_quality, QUALITY_KEYS)}</Item>
            </>
          )}
        </dl>
      )}
      {canEdit && (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" disabled={test.isPending} onClick={() => test.mutate()}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50">
            {t('cfg.gc.test')}
          </button>
          {result?.ok && (
            <p role="status" className="text-sm text-emerald-700">
              {result.message}: {result.organization} ({result.region})
            </p>
          )}
          {result && !result.ok && <p role="alert" className="text-sm text-red-700">{result.message}</p>}
          {test.isError && (
            <p role="alert" className="text-sm text-red-700">
              {test.error instanceof ApiError && test.error.status === 503
                ? t('cfg.gc.testUnavailable') : t('cfg.gc.testError')}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

const ORIGINS: DataOrigin[] = ['sintetico', 'real']

/** Origen de datos de toda la plataforma (FE012): al cambiarlo, dashboards, listado, explorador, búsqueda y flujos lo siguen. */
function OriginCard({ origin, canEdit }: { origin: DataOrigin; canEdit: boolean }) {
  const { t } = useI18n()
  const [pending, setPending] = useState<DataOrigin | null>(null)
  const change = useConfigMutation(configRequests.sources)
  const target = ORIGINS.find((o) => o === pending)
  return (
    <Card title={t('cfg.origin.title')}
      description={t('cfg.origin.description')}>
      <fieldset disabled={!canEdit || change.isPending} className="space-y-2">
        <legend className="sr-only">{t('cfg.origin.title')}</legend>
        {ORIGINS.map((option) => (
          <label key={option} className="flex items-start gap-3 text-sm text-slate-700">
            <input type="radio" name="data-origin" className="mt-0.5 size-4" checked={(pending ?? origin) === option}
              onChange={() => { change.reset(); setPending(option === origin ? null : option) }} />
            <span>
              <span className="font-medium">{t(`cfg.origin.${option}.label`)}</span>
              <span className="block text-slate-500">{t(`cfg.origin.${option}.description`)}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {canEdit && target && (
        <div role="alertdialog" aria-label={t('cfg.origin.confirmDialog')}
          className="space-y-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p>
            {target === 'real' ? t('cfg.origin.toReal') : t('cfg.origin.toSynthetic')}
          </p>
          <div className="flex gap-2">
            <button type="button" disabled={change.isPending}
              onClick={() => change.mutate({ origin: target }, { onSuccess: () => setPending(null) })}
              className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
              {t('cfg.origin.confirm')}
            </button>
            <button type="button" onClick={() => { change.reset(); setPending(null) }}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50">
              {t('cfg.cancel')}
            </button>
          </div>
        </div>
      )}
      {change.isError && <p role="alert" className="text-sm text-red-700">{t('cfg.origin.error')}</p>}
    </Card>
  )
}

export function SourcesTab({ config, canEdit }: { config: PlatformConfig; canEdit: boolean }) {
  const origin = config.sources.origin
  return (
    <div className="space-y-4">
      <OriginCard origin={origin} canEdit={canEdit} />
      {/* Con el origen real, el estado del conector de Genesys sustituye a los conectores simulados. */}
      {origin === 'sintetico' && <MockConnectors canEdit={canEdit} />}
      <GenesysCard canEdit={canEdit} />
    </div>
  )
}

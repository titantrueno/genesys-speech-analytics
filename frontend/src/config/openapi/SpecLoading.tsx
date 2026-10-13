import { useI18n } from '../../i18n/useI18n'

/** Mientras llegan el chunk de Swagger UI o la especificación. */
export function SpecLoading() {
  const { t } = useI18n()
  return <p role="status" className="text-sm text-slate-500">{t('cfg.api.loadingSpec')}</p>
}

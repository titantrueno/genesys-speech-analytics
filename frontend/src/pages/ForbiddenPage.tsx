import { ShieldAlert } from 'lucide-react'
import { useI18n } from '../i18n/useI18n'

export function ForbiddenPage() {
  const { t } = useI18n()
  return (
    <section className="mx-auto mt-16 max-w-md text-center">
      <ShieldAlert className="mx-auto size-10 text-amber-500" aria-hidden />
      <h1 className="mt-4 text-2xl font-semibold">{t('pages.forbidden.title')}</h1>
      <p className="mt-2 text-slate-600">{t('pages.forbidden.body')}</p>
    </section>
  )
}

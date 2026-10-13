import { Link } from 'react-router'
import { useI18n } from '../i18n/useI18n'

export function NotFoundPage() {
  const { t } = useI18n()
  return (
    <section className="mx-auto mt-16 max-w-md text-center">
      <h1 className="text-2xl font-semibold">{t('pages.notFound.title')}</h1>
      <Link to="/" className="mt-4 inline-block text-brand-600 hover:underline">{t('pages.notFound.home')}</Link>
    </section>
  )
}

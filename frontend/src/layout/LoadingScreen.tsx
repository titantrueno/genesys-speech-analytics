import { Loader2 } from 'lucide-react'
import { useI18n } from '../i18n/useI18n'

export function LoadingScreen({ label }: { label?: string }) {
  const { t } = useI18n()
  return (
    <div className="flex min-h-[50vh] items-center justify-center gap-2 text-slate-500" role="status">
      <Loader2 className="size-5 animate-spin" aria-hidden />
      <span>{label ?? t('common.loading')}</span>
    </div>
  )
}

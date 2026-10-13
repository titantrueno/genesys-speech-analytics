import { Languages } from 'lucide-react'
import { useId } from 'react'
import { useI18n } from './useI18n'
import { LANGUAGES, parseLanguage } from './languages'

/** Idioma personal de este navegador; la primera opción vuelve al idioma de la plataforma (Configuración › General). */
export function LanguageSelect({ tone = 'light' }: { tone?: 'light' | 'dark' }) {
  const { personal, setPersonal, t } = useI18n()
  const id = useId()
  const dark = tone === 'dark'
  return (
    <div className={`flex items-center gap-2 ${dark ? 'text-slate-300' : 'text-slate-500'}`}>
      <Languages className="size-4 shrink-0" aria-hidden />
      <select id={id} aria-label={t('common.language')} value={personal ?? ''}
        onChange={(e) => setPersonal(parseLanguage(e.target.value))}
        className={`w-full rounded-md border px-2 py-1 text-sm ${dark ? 'border-white/20 bg-brand-900 text-slate-100' : 'border-slate-300 bg-white text-slate-700'}`}>
        <option value="">{t('common.language.platform')}</option>
        {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
      </select>
    </div>
  )
}

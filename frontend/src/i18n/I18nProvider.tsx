import { useEffect, useMemo, type ReactNode } from 'react'
import { usePublicConfig } from '../config/api'
import { setDisplayLocale } from '../lib/format'
import { I18nContext, type I18nContextValue } from './context'
import { DICTIONARIES } from './dictionaries'
import { DEFAULT_LANGUAGE, parseLanguage } from './languages'
import { translate } from './translate'

/**
 * Idioma de los menús y textos de la interfaz: el de la plataforma (Configuración › General), también sin sesión.
 * No afecta a los datos: transcripciones, resúmenes, main topics y palabras clave se muestran como llegan.
 */
export function I18nProvider({ children }: { children: ReactNode }) {
  const { data: settings } = usePublicConfig()
  const language = parseLanguage(settings?.language) ?? DEFAULT_LANGUAGE
  // Durante el render, como la zona horaria en `AppLayout`: las páginas de este mismo render ya formatean en este idioma.
  setDisplayLocale(language)

  useEffect(() => { document.documentElement.lang = language.slice(0, 2) }, [language])

  const value = useMemo<I18nContextValue>(() => ({
    language,
    t: (key, params) => translate(DICTIONARIES[language], language, key, params),
    tOr: (key, fallback) => (key in DICTIONARIES[language] ? translate(DICTIONARIES[language], language, key) : fallback),
  }), [language])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

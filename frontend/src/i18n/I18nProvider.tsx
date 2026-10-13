import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { usePublicConfig } from '../config/api'
import { setDisplayLocale } from '../lib/format'
import { I18nContext, type I18nContextValue } from './context'
import { DICTIONARIES } from './dictionaries'
import { DEFAULT_LANGUAGE, parseLanguage, type Language } from './languages'
import { translate } from './translate'

const STORAGE_KEY = 'sta.language'

/** `localStorage` puede faltar o lanzar (ventana privada, datos bloqueados): la interfaz funciona sin él. */
const personalStorage = {
  get(): Language | null {
    try {
      return parseLanguage(localStorage.getItem(STORAGE_KEY))
    } catch {
      return null
    }
  },
  set(language: Language | null) {
    try {
      if (language) localStorage.setItem(STORAGE_KEY, language)
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Sin almacenamiento, la elección vale solo hasta recargar.
    }
  },
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const { data: settings } = usePublicConfig()
  const [personal, setPersonalState] = useState<Language | null>(personalStorage.get)
  const language = personal ?? parseLanguage(settings?.language) ?? DEFAULT_LANGUAGE
  // Durante el render, como la zona horaria en `AppLayout`: las páginas de este mismo render ya formatean en este idioma.
  setDisplayLocale(language)

  useEffect(() => { document.documentElement.lang = language.slice(0, 2) }, [language])

  const setPersonal = useCallback((value: Language | null) => {
    personalStorage.set(value)
    setPersonalState(value)
  }, [])

  const value = useMemo<I18nContextValue>(() => ({
    language,
    personal,
    setPersonal,
    t: (key, params) => translate(DICTIONARIES[language], language, key, params),
  }), [language, personal, setPersonal])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

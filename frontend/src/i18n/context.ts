import { createContext } from 'react'
import { es, type TKey } from './dictionaries'
import { DEFAULT_LANGUAGE, type Language } from './languages'
import { translate, type Params } from './translate'

export interface I18nContextValue {
  /** Idioma en uso: el personal, si existe, y si no el de la plataforma. */
  language: Language
  /** Elección personal (en este navegador), o `null` si se usa el idioma de la plataforma. */
  personal: Language | null
  setPersonal: (language: Language | null) => void
  t: (key: TKey, params?: Params) => string
}

/** Sin `I18nProvider` (un componente aislado) la interfaz sale en español, el idioma base. */
export const I18nContext = createContext<I18nContextValue>({
  language: DEFAULT_LANGUAGE,
  personal: null,
  setPersonal: () => undefined,
  t: (key, params) => translate(es, DEFAULT_LANGUAGE, key, params),
})

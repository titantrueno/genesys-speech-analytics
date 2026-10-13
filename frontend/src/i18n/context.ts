import { createContext } from 'react'
import { es, type TKey } from './dictionaries'
import { DEFAULT_LANGUAGE, type Language } from './languages'
import { translate, type Params } from './translate'

export interface I18nContextValue {
  /** Idioma de la plataforma (Configuración › General). */
  language: Language
  t: (key: TKey, params?: Params) => string
}

/** Sin `I18nProvider` (un componente aislado) la interfaz sale en español, el idioma base. */
export const I18nContext = createContext<I18nContextValue>({
  language: DEFAULT_LANGUAGE,
  t: (key, params) => translate(es, DEFAULT_LANGUAGE, key, params),
})

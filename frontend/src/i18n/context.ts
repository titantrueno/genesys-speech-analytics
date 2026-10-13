import { createContext } from 'react'
import { es, type TKey } from './dictionaries'
import { DEFAULT_LANGUAGE, type Language } from './languages'
import { translate, type Params } from './translate'

export type Translate = (key: TKey, params?: Params) => string

export interface I18nContextValue {
  /** Idioma de la plataforma (Configuración › General). */
  language: Language
  t: Translate
  /** Texto de `key` si existe; si no, `fallback` (códigos que el backend añada y el diccionario aún no conozca). */
  tOr: (key: string, fallback: string) => string
}

/** Sin `I18nProvider` (un componente aislado) la interfaz sale en español, el idioma base. */
export const DEFAULT_I18N: I18nContextValue = {
  language: DEFAULT_LANGUAGE,
  t: (key, params) => translate(es, DEFAULT_LANGUAGE, key, params),
  tOr: (key, fallback) => (key in es ? translate(es, DEFAULT_LANGUAGE, key) : fallback),
}

export const I18nContext = createContext<I18nContextValue>(DEFAULT_I18N)

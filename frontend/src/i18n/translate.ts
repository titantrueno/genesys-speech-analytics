import type { Language } from './languages'

export type Params = Record<string, string | number>
export type Dictionary = Record<string, string>

/**
 * Texto de `key` con `{param}` sustituidos. Si hay `count` y existen `key_one`/`key_other`, elige la forma plural del
 * idioma. Una clave desconocida devuelve la propia clave, para que el fallo se vea sin romper la pantalla.
 */
export function translate(dictionary: Dictionary, language: Language, key: string, params?: Params): string {
  let text = dictionary[key]
  if (text === undefined && typeof params?.count === 'number') {
    text = dictionary[`${key}_${new Intl.PluralRules(language).select(params.count)}`] ?? dictionary[`${key}_other`]
  }
  if (text === undefined) return key
  return params ? text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in params ? String(params[name]) : whole)) : text
}

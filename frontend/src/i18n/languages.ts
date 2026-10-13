/** Idiomas con diccionario. El backend decide cuáles se pueden elegir como idioma de la plataforma (`LANGUAGES`). */
export const LANGUAGES = [
  { value: 'es-ES', label: 'Español (España)' },
  { value: 'en-US', label: 'English (United States)' },
] as const

export type Language = (typeof LANGUAGES)[number]['value']

export const DEFAULT_LANGUAGE: Language = 'es-ES'

export function parseLanguage(value: unknown): Language | null {
  return LANGUAGES.find((l) => l.value === value)?.value ?? null
}

import type { Language } from './languages'
import { en } from './en'
import { es } from './es'

export type TKey = keyof typeof es

export { en, es }

export const DICTIONARIES: Record<Language, Record<string, string>> = { 'es-ES': es, 'en-US': en }

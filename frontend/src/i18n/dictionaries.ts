import type { Language } from './languages'
import { en } from './en'
import { es } from './es'

/** Clave de diccionario; las formas plurales `x_one`/`x_other` se piden como `x` con `count`. */
export type TKey = BaseKey<keyof typeof es>
type BaseKey<K extends string> = K extends `${infer Base}_${'one' | 'other'}` ? Base | K : K

export { en, es }

export const DICTIONARIES: Record<Language, Record<string, string>> = { 'es-ES': es, 'en-US': en }

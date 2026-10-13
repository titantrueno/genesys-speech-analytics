import { describe, expect, it } from 'vitest'
import { en, es } from './dictionaries'
import { translate } from './translate'

const params = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

describe('diccionarios (FE016, criterio 6)', () => {
  it('es y en tienen exactamente las mismas claves', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(es).sort())
  })

  it('cada clave usa los mismos parámetros en los dos idiomas', () => {
    for (const key of Object.keys(es) as (keyof typeof es)[]) {
      expect(params(en[key]), key).toEqual(params(es[key]))
    }
  })

  it('ningún texto está vacío', () => {
    for (const dictionary of [es, en]) {
      for (const [key, text] of Object.entries(dictionary)) expect(text.trim(), key).not.toBe('')
    }
  })
})

describe('translate', () => {
  const dictionary = {
    'a.hello': 'Hola {name}',
    'a.items_one': '{count} elemento',
    'a.items_other': '{count} elementos',
  }

  it('sustituye parámetros', () => {
    expect(translate(dictionary, 'es-ES', 'a.hello', { name: 'Ana' })).toBe('Hola Ana')
  })

  it('elige la forma singular o plural según count', () => {
    expect(translate(dictionary, 'es-ES', 'a.items', { count: 1 })).toBe('1 elemento')
    expect(translate(dictionary, 'es-ES', 'a.items', { count: 3 })).toBe('3 elementos')
    expect(translate(dictionary, 'es-ES', 'a.items', { count: 0 })).toBe('0 elementos')
  })

  it('una clave heredada del objeto (`constructor`) no se toma por una traducción', () => {
    expect(translate(dictionary, 'es-ES', 'constructor')).toBe('constructor')
    expect(translate(dictionary, 'es-ES', '__proto__', { count: 2 })).toBe('__proto__')
  })

  it('una clave desconocida devuelve la propia clave', () => {
    expect(translate(dictionary, 'es-ES', 'a.nope')).toBe('a.nope')
  })
})

describe('plurales del diccionario real (FE016)', () => {
  const t = (key: string, params: Record<string, string | number>, language: 'es-ES' | 'en-US' = 'en-US') =>
    translate(language === 'en-US' ? en : es, language, key, params)

  it('en inglés distingue 0, 1 y varios', () => {
    expect(t('conv.count', { count: 0, n: '0' })).toBe('0 conversations')
    expect(t('conv.count', { count: 1, n: '1' })).toBe('1 conversation')
    expect(t('conv.count', { count: 2, n: '2' })).toBe('2 conversations')
    expect(t('flows.node.errors', { count: 1, n: 1 })).toBe('1 error')
  })

  it('en español conserva los textos de siempre', () => {
    expect(t('conv.count', { count: 1, n: '1' }, 'es-ES')).toBe('1 conversación')
    expect(t('conv.count', { count: 0, n: '0' }, 'es-ES')).toBe('0 conversaciones')
    expect(t('flows.node.errors', { count: 3, n: 3 }, 'es-ES')).toBe('3 errores')
  })
})

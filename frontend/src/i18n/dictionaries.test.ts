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

  it('una clave desconocida devuelve la propia clave', () => {
    expect(translate(dictionary, 'es-ES', 'a.nope')).toBe('a.nope')
  })
})

import { describe, expect, it } from 'vitest'

/**
 * FE016, criterio 7: las pantallas migradas no llevan texto de interfaz en español escrito a mano; sale de los
 * diccionarios. Cubre todo `frontend/src` salvo los diccionarios, los códigos de idioma y los ayudantes de test.
 */
const SKIPPED = ['./es/', './en/', './languages.ts', '../test/']

const SPANISH = /[áéíóúñ¿¡]|\b(de|el|la|los|las|para|con|sin|una|por|del|al|en|se|que|su)\b/i

const sources = import.meta.glob(['../**/*.tsx', '../**/*.ts', '!../**/*.test.*'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>
// `índice` es un código de unidad de la API (`KpiUnit`), no texto de interfaz.
const API_CODES = new Set(['índice'])
const files = Object.entries(sources).filter(([path]) => !SKIPPED.some((skip) => path.startsWith(skip)))

/** Literales de cadena y texto JSX, sin comentarios, imports ni errores de programación (`throw new Error`). */
function literals(source: string): string[] {
  const code = source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/.*$/gm, '$1')
    .replace(/throw new Error\([^)]*\)/g, '')
    .replace(/^\s*(import|export)\b[^\n]*\bfrom\b[^\n]*$/gm, '')
  const found: string[] = []
  for (const m of code.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)) found.push(m[1] ?? m[2] ?? m[3] ?? '')
  for (const m of code.matchAll(/>([^<>{}\n]+)</g)) found.push(m[1])
  // Una cadena sin espacios ni acentos es un identificador (ruta, clave, clase), no una frase de interfaz.
  return found.filter((text) => /\s|[áéíóúñ¿¡]/.test(text))
}

describe('sin texto de interfaz en español escrito a mano (FE016, criterio 7)', () => {
  it('hay archivos migrados que comprobar', () => {
    expect(files.length).toBeGreaterThan(100)
  })

  for (const [path, source] of files) {
    it(path.replace('../', ''), () => {
      expect(literals(source).filter((text) => SPANISH.test(text) && !API_CODES.has(text))).toEqual([])
    })
  }
})

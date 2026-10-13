import { describe, expect, it } from 'vitest'

/**
 * FE016, criterio 7: las pantallas migradas no llevan texto de interfaz en español escrito a mano; sale de los
 * diccionarios. Cada tarea añade sus carpetas a `MIGRATED`.
 */
const MIGRATED = ['layout/', 'pages/', 'auth/', 'components/', 'i18n/I18nProvider.tsx', 'dashboards/', 'conversations/', 'explorer/', 'search/', 'flows/', 'downloads/', 'users/', 'config/']

const SPANISH = /[áéíóúñ¿¡]|\b(de|el|la|los|las|para|con|sin|una|por|del|al|en|se|que|su)\b/i

const sources = import.meta.glob(['../**/*.tsx', '../**/*.ts', '!../**/*.test.*'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>
// `dataErrors.ts` compara con el mensaje en español que devuelve la API (FE012); la fase del backend lo sustituye (T8).
// `kpiMeta.ts` lleva los códigos de unidad de la API (`índice`), no texto de interfaz.
const EXCLUDED = ['../components/dataErrors.ts', '../dashboards/kpiMeta.ts']
const files = Object.entries(sources).filter(([path]) =>
  MIGRATED.some((entry) => path.startsWith(`../${entry}`)) && !EXCLUDED.includes(path))

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
    expect(files.length).toBeGreaterThan(5)
  })

  for (const [path, source] of files) {
    it(path.replace('../', ''), () => {
      expect(literals(source).filter((text) => SPANISH.test(text))).toEqual([])
    })
  }
})

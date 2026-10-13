import { DEFAULT_I18N } from '../i18n/context'
import type { Translate } from '../i18n/context'
import { EMPTY_VALUE } from '../lib/format'

/** Valor anterior o nuevo de una entrada, legible: `clave: valor` para objetos y listas separadas por comas. */
export function formatAuditValue(value: unknown, t: Translate = DEFAULT_I18N.t): string {
  if (value === null || value === undefined) return EMPTY_VALUE
  if (Array.isArray(value)) return value.length ? value.map((item) => formatAuditValue(item, t)).join(', ') : EMPTY_VALUE
  if (typeof value === 'boolean') return t(value ? 'exp.bool.true' : 'exp.bool.false')
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).map(([k, v]) => `${k}: ${formatAuditValue(v, t)}`).join(' · ')
  }
  return String(value)
}

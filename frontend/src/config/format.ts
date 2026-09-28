import { EMPTY_VALUE } from '../lib/format'

/** Valor anterior o nuevo de una entrada, legible: `clave: valor` para objetos y listas separadas por comas. */
export function formatAuditValue(value: unknown): string {
  if (value === null || value === undefined) return EMPTY_VALUE
  if (Array.isArray(value)) return value.length ? value.map(formatAuditValue).join(', ') : EMPTY_VALUE
  if (typeof value === 'boolean') return value ? 'sí' : 'no'
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).map(([k, v]) => `${k}: ${formatAuditValue(v)}`).join(' · ')
  }
  return String(value)
}

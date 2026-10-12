import type { Catalog } from '../api/metrics'
import { formatShortDate } from '../lib/format'

export const RESOLUTION_LABELS: Record<string, string> = { resuelta: 'Resuelta', no_resuelta: 'No resuelta', escalada: 'Escalada' }
export const CHURN_LABELS: Record<string, string> = { bajo: 'Bajo', medio: 'Medio', alto: 'Alto' }
export const CHANNEL_LABELS: Record<string, string> = { voz: 'Voz', chat: 'Chat' }

export interface Chip { id: string; label: string; remove: Record<string, string | string[] | undefined> }

export function activeFilterChips(params: URLSearchParams, catalog?: Catalog): Chip[] {
  const chips: Chip[] = []
  const from = params.get('from')
  const to = params.get('to')
  if (from || to) {
    chips.push({ id: 'period', label: `Periodo: ${from ? formatShortDate(from) : '…'} – ${to ? formatShortDate(to) : '…'}`, remove: { from: undefined, to: undefined } })
  }
  const channel = params.get('channel')
  if (channel) chips.push({ id: 'channel', label: `Canal: ${CHANNEL_LABELS[channel] ?? channel}`, remove: { channel: undefined } })

  const multi = (key: string, title: string, labelOf: (v: string) => string) => {
    const values = params.getAll(key)
    for (const value of values) {
      chips.push({ id: `${key}-${value}`, label: `${title}: ${labelOf(value)}`, remove: { [key]: values.filter((v) => v !== value) } })
    }
  }
  const topicNames = new Map(catalog?.main_topics.map((t) => [t.code, t.name]))
  multi('main_topic', 'Main topic', (v) => topicNames.get(v) ?? v)
  const queueNames = new Map(catalog?.queues.map((q) => [q.id, q.name]))
  const agentNames = new Map(catalog?.agents.map((a) => [a.id, a.name]))
  multi('queue', 'Cola', (v) => queueNames.get(v) ?? (catalog ? 'desconocida' : '…'))
  multi('agent', 'Agente', (v) => agentNames.get(v) ?? (catalog ? 'desconocido' : '…'))
  multi('resolution', 'Resolución', (v) => RESOLUTION_LABELS[v] ?? v)
  multi('churn_risk', 'Riesgo de abandono', (v) => CHURN_LABELS[v] ?? v)

  // Búsqueda exacta en conversaciones reales (FE012).
  const phone = params.get('phone')
  if (phone) chips.push({ id: 'phone', label: `Teléfono: ${phone}`, remove: { phone: undefined } })
  const externalTag = params.get('external_tag')
  if (externalTag) chips.push({ id: 'external_tag', label: `externalTag: ${externalTag}`, remove: { external_tag: undefined } })

  if (params.has('sentiment_lt')) {
    const value = Number(params.get('sentiment_lt'))
    chips.push({ id: 'sentiment', label: value === -0.3 ? 'Sentimiento negativo' : `Sentimiento < ${value}`, remove: { sentiment_lt: undefined } })
  }
  if (params.has('compliant')) {
    chips.push({ id: 'compliant', label: params.get('compliant') === 'true' ? 'Cumple todos los checks' : 'Incumple algún check', remove: { compliant: undefined } })
  }
  if (params.has('repeat_contact')) {
    chips.push({ id: 'repeat', label: params.get('repeat_contact') === 'true' ? 'Con recontacto en 7 días' : 'Sin recontacto en 7 días (FCR)', remove: { repeat_contact: undefined } })
  }
  return chips
}

export function sentimentTone(value: number): { label: string; color: string } {
  if (value < -0.3) return { label: 'Negativo', color: 'var(--diverging-negative)' }
  if (value > 0.3) return { label: 'Positivo', color: 'var(--diverging-positive)' }
  return { label: 'Neutro', color: 'var(--chart-muted)' }
}

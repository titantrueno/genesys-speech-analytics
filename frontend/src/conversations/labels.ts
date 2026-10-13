import type { Catalog } from '../api/metrics'
import type { Translate } from '../i18n/context'
import type { TKey } from '../i18n/dictionaries'
import { formatShortDate } from '../lib/format'

const RESOLUTION_KEYS = { resuelta: 'domain.resolution.resuelta', no_resuelta: 'domain.resolution.no_resuelta', escalada: 'domain.resolution.escalada' } as const satisfies Record<string, TKey>
const CHURN_KEYS = { bajo: 'domain.churn.bajo', medio: 'domain.churn.medio', alto: 'domain.churn.alto' } as const satisfies Record<string, TKey>
const CHANNEL_KEYS = { voz: 'domain.channel.voz', chat: 'domain.channel.chat' } as const satisfies Record<string, TKey>

/** Etiqueta de un código cerrado de la API; un código que el front no conoce se muestra tal cual. */
function labelOf(keys: Record<string, TKey>, t: Translate, value: string): string {
  return value in keys ? t(keys[value]) : value
}

export const resolutionLabel = (t: Translate, value: string) => labelOf(RESOLUTION_KEYS, t, value)
export const churnLabel = (t: Translate, value: string) => labelOf(CHURN_KEYS, t, value)
export const channelLabel = (t: Translate, value: string) => labelOf(CHANNEL_KEYS, t, value)

export interface Chip { id: string; label: string; remove: Record<string, string | string[] | undefined> }

export function activeFilterChips(params: URLSearchParams, t: Translate, catalog?: Catalog): Chip[] {
  const chips: Chip[] = []
  const from = params.get('from')
  const to = params.get('to')
  if (from || to) {
    chips.push({ id: 'period', label: t('conv.chip.period', { from: from ? formatShortDate(from) : '…', to: to ? formatShortDate(to) : '…' }), remove: { from: undefined, to: undefined } })
  }
  const channel = params.get('channel')
  if (channel) chips.push({ id: 'channel', label: t('conv.chip.channel', { value: channelLabel(t, channel) }), remove: { channel: undefined } })

  const multi = (key: string, chip: TKey, labelOf: (v: string) => string) => {
    const values = params.getAll(key)
    for (const value of values) {
      chips.push({ id: `${key}-${value}`, label: t(chip, { value: labelOf(value) }), remove: { [key]: values.filter((v) => v !== value) } })
    }
  }
  const topicNames = new Map(catalog?.main_topics.map((topic) => [topic.code, topic.name]))
  multi('main_topic', 'conv.chip.mainTopic', (v) => topicNames.get(v) ?? v)
  const queueNames = new Map(catalog?.queues.map((q) => [q.id, q.name]))
  const agentNames = new Map(catalog?.agents.map((a) => [a.id, a.name]))
  multi('queue', 'conv.chip.queue', (v) => queueNames.get(v) ?? (catalog ? t('conv.chip.unknownQueue') : '…'))
  multi('agent', 'conv.chip.agent', (v) => agentNames.get(v) ?? (catalog ? t('conv.chip.unknownAgent') : '…'))
  multi('resolution', 'conv.chip.resolution', (v) => resolutionLabel(t, v))
  multi('churn_risk', 'conv.chip.churn', (v) => churnLabel(t, v))

  // Búsqueda exacta en conversaciones reales (FE012).
  const phone = params.get('phone')
  if (phone) chips.push({ id: 'phone', label: t('conv.chip.phone', { value: phone }), remove: { phone: undefined } })
  const externalTag = params.get('external_tag')
  if (externalTag) chips.push({ id: 'external_tag', label: t('conv.chip.externalTag', { value: externalTag }), remove: { external_tag: undefined } })

  if (params.has('sentiment_lt')) {
    const value = Number(params.get('sentiment_lt'))
    chips.push({ id: 'sentiment', label: value === -0.3 ? t('conv.chip.sentimentNegative') : t('conv.chip.sentimentLt', { value }), remove: { sentiment_lt: undefined } })
  }
  if (params.has('compliant')) {
    chips.push({ id: 'compliant', label: params.get('compliant') === 'true' ? t('conv.chip.compliant') : t('conv.chip.nonCompliant'), remove: { compliant: undefined } })
  }
  if (params.has('repeat_contact')) {
    chips.push({ id: 'repeat', label: params.get('repeat_contact') === 'true' ? t('conv.chip.repeat') : t('conv.chip.noRepeat'), remove: { repeat_contact: undefined } })
  }
  return chips
}

export function sentimentTone(value: number, t: Translate): { label: string; color: string } {
  if (value < -0.3) return { label: t('domain.sentiment.negative'), color: 'var(--diverging-negative)' }
  if (value > 0.3) return { label: t('domain.sentiment.positive'), color: 'var(--diverging-positive)' }
  return { label: t('domain.sentiment.neutral'), color: 'var(--chart-muted)' }
}

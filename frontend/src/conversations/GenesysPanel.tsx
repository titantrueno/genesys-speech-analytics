import type { ReactNode } from 'react'
import type { ConversationDetail, GenesysSegment, GenesysInfo } from '../api/conversations'
import type { Translate } from '../i18n/context'
import { useI18n } from '../i18n/useI18n'
import { formatDecimal, formatDuration, formatInteger, formatKpi, formatPercentWhole } from '../lib/format'
import { PendingText } from './badges'
import { Metric, Section } from './panelParts'

const TIMES = [
  'handle_s', 'queue_wait_s', 'talk_s', 'hold_s', 'acw_s', 'bot_time_s', 'first_response_s', 'avg_agent_response_s',
  'avg_customer_response_s',
] as const
const MESSAGES = ['customer_messages', 'agent_messages', 'bot_messages'] as const

const yesNo = (t: Translate, value: boolean) => (value ? t('domain.yes') : t('domain.no'))

function stepLabel(segment: GenesysSegment, t: Translate): string | null {
  switch (segment.kind) {
    case 'flujo_entrada': case 'ivr': return `${t('conv.g.step.bot')}${segment.flow ? ` · ${segment.flow.name}` : ''}`
    case 'cola': return `${t('conv.g.step.queue')}${segment.queue ? ` · ${segment.queue.name}` : ''}`
    case 'agente': return `${t('conv.g.step.agent')}${segment.agent ? ` · ${segment.agent.name}` : ''}`
    case 'externo': return `${t('conv.g.step.external')}${segment.name ? ` · ${segment.name}` : ''}`
    default: return null // el cliente no es un paso del recorrido
  }
}

/** Reparto de un valor por categoría; solo muestra las categorías que el front sabe nombrar (`labelPrefix.<clave>`). */
function Share({ title, values, labelPrefix, format }: {
  title: string; values: Record<string, number>; labelPrefix: string; format: (value: number) => string
}) {
  const { tOr } = useI18n()
  const entries = Object.entries(values).flatMap(([key, value]) => {
    const label = tOr(`${labelPrefix}.${key}`, '')
    return label ? [[key, label, value] as const] : []
  })
  if (entries.length === 0) return null
  return (
    <ul aria-label={title} className="space-y-0.5 text-sm">
      {entries.map(([key, label, value]) => (
        <li key={key} className="flex justify-between gap-2">
          <span className="text-slate-500">{label}</span><span className="font-medium text-slate-800 tabular-nums">{format(value)}</span>
        </li>
      ))}
    </ul>
  )
}

function numericMap(value: unknown): Record<string, number> {
  if (typeof value !== 'object' || value === null) return {}
  return Object.fromEntries(Object.entries(value).filter((entry): entry is [string, number] => typeof entry[1] === 'number'))
}

function Contact({ g }: { g: GenesysInfo }) {
  const { t } = useI18n()
  const rows: Array<[string, ReactNode]> = []
  if (g.ani) rows.push(['ANI', g.ani])
  if (g.dnis) rows.push(['DNIS', g.dnis])
  if (g.external_tag) rows.push(['externalTag', g.external_tag])
  if (rows.length === 0) return null
  return (
    <Section title={t('conv.g.contact')}>
      <dl>{rows.map(([label, value]) => <Metric key={label} label={label}>{value}</Metric>)}</dl>
    </Section>
  )
}

interface Props {
  conversation: ConversationDetail
  onSelectTurn: (turnIndex: number) => void
}

/** Analítica de Genesys de una conversación real (FE012, criterio 5); no muestra los campos que su canal no tiene. */
export function GenesysPanel({ conversation, onSelectTurn }: Props) {
  const { t, tOr } = useI18n()
  const g = conversation.genesys
  if (!g) return null
  const steps = g.segments.map((segment) => ({ segment, label: stepLabel(segment, t) })).filter((s) => s.label !== null)
  const wrapups = [...new Set(g.segments.flatMap((s) => (s.wrapup ? [s.wrapup.name] : [])))]
  const times = TIMES.flatMap((key) => (numericMap(g.metrics)[key] === undefined ? [] : [[t(`conv.g.time.${key}`), numericMap(g.metrics)[key]] as const]))
  const messages = MESSAGES.flatMap((key) => (numericMap(g.metrics)[key] === undefined ? [] : [[t(`conv.g.time.${key}`), numericMap(g.metrics)[key]] as const]))
  const share = numericMap(g.metrics.sta_time_pct)
  const confidence = numericMap(g.metrics.asr_confidence)
  const rFactor = numericMap(g.metrics).r_factor
  const turnCount = conversation.turns.length

  return (
    <aside aria-label={t('conv.g.aria')} className="rounded-xl border border-slate-200 bg-white">
      {conversation.analysis.pending && (
        <div className="border-b border-slate-100 px-4 py-3"><PendingText className="text-sm font-medium" /></div>
      )}
      <Contact g={g} />
      <Section title={t('conv.g.journey')}>
        <ol aria-label={t('conv.g.journey')} className="space-y-1 text-sm text-slate-700">
          {steps.map(({ segment, label }) => (
            <li key={segment.seq} className="flex items-center gap-2">
              <span aria-hidden className="size-1.5 rounded-full bg-brand-500" />{label}
            </li>
          ))}
        </ol>
      </Section>
      <Section title={t('conv.g.closing')}>
        <dl>
          {wrapups.length > 0 && <Metric label={t('conv.g.wrapup')}>{wrapups.join(', ')}</Metric>}
          {g.disconnect_type && <Metric label={t('conv.g.ended')}>{tOr(`conv.g.disconnect.${g.disconnect_type}`, g.disconnect_type)}</Metric>}
          <Metric label={t('conv.g.contained')}>{yesNo(t, g.contained_in_bot)}</Metric>
          <Metric label={t('conv.g.derived')}>{yesNo(t, g.derived_to_agent)}</Metric>
          <Metric label={t('conv.g.reconnected')}>{yesNo(t, g.reconnected)}</Metric>
          <Metric label={t('conv.g.abandoned')}>{yesNo(t, g.abandoned_in_queue)}</Metric>
          {conversation.channel === 'chat' && <Metric label={t('conv.g.undelivered')}>{formatInteger(g.undelivered_messages)}</Metric>}
        </dl>
      </Section>
      {(times.length > 0 || messages.length > 0) && (
        <Section title={t('conv.g.times')}>
          <dl>
            {times.map(([label, value]) => <Metric key={label} label={label}>{formatDuration(value)}</Metric>)}
            {messages.map(([label, value]) => <Metric key={label} label={label}>{formatInteger(value)}</Metric>)}
          </dl>
        </Section>
      )}
      {(g.mos !== null || rFactor !== undefined) && (
        <Section title={t('conv.g.callQuality')}>
          <dl>
            {g.mos !== null && <Metric label={t('conv.g.mos')}>{formatDecimal(g.mos, 1)}</Metric>}
            {rFactor !== undefined && <Metric label={t('conv.g.rFactor')}>{formatInteger(rFactor)}</Metric>}
          </dl>
        </Section>
      )}
      {Object.keys(share).length > 0 && (
        <Section title={t('conv.g.timeSplit')}>
          <Share title={t('conv.g.timeSplit')} values={share} labelPrefix="conv.g.split" format={(v) => formatKpi(v, '%')} />
        </Section>
      )}
      <Section title={t('conv.transcript')}>
        <dl><Metric label={t('conv.g.transcriptQuality')}>{t(`conv.quality.${g.transcript_quality}`)}</Metric></dl>
        <Share title={t('conv.g.confidence')} values={confidence} labelPrefix="conv.g.speaker"
          format={(v) => formatPercentWhole(v * 100)} />
      </Section>
      {g.topics.length > 0 && (
        <Section title={t('conv.g.topics')}>
          <ul className="space-y-1">
            {g.topics.map((topic) => {
              const target = topic.turn_seq !== null && topic.turn_seq < turnCount ? topic.turn_seq : null
              const content = (
                <>
                  <span className="font-medium">{topic.name}</span>
                  {topic.phrase && <span className="block text-xs text-slate-500">«{topic.phrase}»</span>}
                </>
              )
              return (
                <li key={topic.seq}>
                  {target === null
                    ? <span className="block rounded-md px-2 py-1 text-sm text-slate-700">{content}</span>
                    : (
                      <button type="button" onClick={() => onSelectTurn(target)} title={t('conv.g.goTo')}
                        className="block w-full rounded-md px-2 py-1 text-left text-sm text-slate-700 hover:bg-brand-50">
                        {content}
                      </button>
                    )}
                </li>
              )
            })}
          </ul>
        </Section>
      )}
    </aside>
  )
}

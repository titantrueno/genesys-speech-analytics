import type { ReactNode } from 'react'
import type { ConversationDetail, GenesysSegment, GenesysInfo } from '../api/conversations'
import { formatDecimal, formatDuration, formatInteger, formatKpi } from '../lib/format'
import { PendingText } from './badges'
import { Metric, Section } from './panelParts'

const QUALITY_LABELS = { completa: 'Completa', parcial: 'Parcial', sin_transcripcion: 'Sin transcripción' } as const
const DISCONNECT_LABELS: Record<string, string> = {
  client: 'El cliente', peer: 'El agente o el asistente', endpoint: 'Error del extremo', system: 'El sistema',
  error: 'Error', transfer: 'Transferencia', timeout: 'Tiempo agotado',
}
const SPEAKER_LABELS: Record<string, string> = { cliente: 'Cliente', agente: 'Agente', bot: 'Asistente' }
const SPLIT_LABELS: Record<string, string> = {
  customer: 'Cliente', agent: 'Agente', silence: 'Silencio', ivr: 'Asistente', acd: 'Cola', other: 'Otros',
}
const TIMES: Array<[string, string]> = [
  ['handle_s', 'Gestión'], ['queue_wait_s', 'Espera en cola'], ['talk_s', 'Conversación'], ['hold_s', 'En espera'],
  ['acw_s', 'Trabajo posterior'], ['bot_time_s', 'Tiempo con el asistente'], ['first_response_s', 'Primera respuesta'],
  ['avg_agent_response_s', 'Respuesta media del agente'], ['avg_customer_response_s', 'Respuesta media del cliente'],
]
const MESSAGES: Array<[string, string]> = [
  ['customer_messages', 'Mensajes del cliente'], ['agent_messages', 'Mensajes del agente'], ['bot_messages', 'Mensajes del asistente'],
]

const yesNo = (value: boolean) => (value ? 'Sí' : 'No')

function stepLabel(segment: GenesysSegment): string | null {
  switch (segment.kind) {
    case 'flujo_entrada': case 'ivr': return `Asistente virtual${segment.flow ? ` · ${segment.flow.name}` : ''}`
    case 'cola': return `Cola${segment.queue ? ` · ${segment.queue.name}` : ''}`
    case 'agente': return `Agente${segment.agent ? ` · ${segment.agent.name}` : ''}`
    case 'externo': return `Externo${segment.name ? ` · ${segment.name}` : ''}`
    default: return null // el cliente no es un paso del recorrido
  }
}

function Share({ title, values, labels, format }: {
  title: string; values: Record<string, number>; labels: Record<string, string>; format: (value: number) => string
}) {
  const entries = Object.entries(values).filter(([key]) => key in labels)
  if (entries.length === 0) return null
  return (
    <ul aria-label={title} className="space-y-0.5 text-sm">
      {entries.map(([key, value]) => (
        <li key={key} className="flex justify-between gap-2">
          <span className="text-slate-500">{labels[key]}</span><span className="font-medium text-slate-800 tabular-nums">{format(value)}</span>
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
  const rows: Array<[string, ReactNode]> = []
  if (g.ani) rows.push(['ANI', g.ani])
  if (g.dnis) rows.push(['DNIS', g.dnis])
  if (g.external_tag) rows.push(['externalTag', g.external_tag])
  if (rows.length === 0) return null
  return (
    <Section title="Contacto">
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
  const g = conversation.genesys
  if (!g) return null
  const steps = g.segments.map((segment) => ({ segment, label: stepLabel(segment) })).filter((s) => s.label !== null)
  const wrapups = [...new Set(g.segments.flatMap((s) => (s.wrapup ? [s.wrapup.name] : [])))]
  const times = TIMES.flatMap(([key, label]) => (numericMap(g.metrics)[key] === undefined ? [] : [[label, numericMap(g.metrics)[key]] as const]))
  const messages = MESSAGES.flatMap(([key, label]) => (numericMap(g.metrics)[key] === undefined ? [] : [[label, numericMap(g.metrics)[key]] as const]))
  const share = numericMap(g.metrics.sta_time_pct)
  const confidence = numericMap(g.metrics.asr_confidence)
  const rFactor = numericMap(g.metrics).r_factor
  const turnCount = conversation.turns.length

  return (
    <aside aria-label="Analítica de Genesys" className="rounded-xl border border-slate-200 bg-white">
      {conversation.analysis.pending && (
        <div className="border-b border-slate-100 px-4 py-3"><PendingText className="text-sm font-medium" /></div>
      )}
      <Contact g={g} />
      <Section title="Recorrido">
        <ol aria-label="Recorrido" className="space-y-1 text-sm text-slate-700">
          {steps.map(({ segment, label }) => (
            <li key={segment.seq} className="flex items-center gap-2">
              <span aria-hidden className="size-1.5 rounded-full bg-brand-500" />{label}
            </li>
          ))}
        </ol>
      </Section>
      <Section title="Cierre y contención">
        <dl>
          {wrapups.length > 0 && <Metric label="Wrap-up">{wrapups.join(', ')}</Metric>}
          {g.disconnect_type && <Metric label="Terminó">{DISCONNECT_LABELS[g.disconnect_type] ?? g.disconnect_type}</Metric>}
          <Metric label="Contenida en el asistente">{yesNo(g.contained_in_bot)}</Metric>
          <Metric label="Derivada a agente">{yesNo(g.derived_to_agent)}</Metric>
          <Metric label="Reconexión">{yesNo(g.reconnected)}</Metric>
          <Metric label="Abandono en cola">{yesNo(g.abandoned_in_queue)}</Metric>
          {conversation.channel === 'chat' && <Metric label="Mensajes no entregados">{formatInteger(g.undelivered_messages)}</Metric>}
        </dl>
      </Section>
      {(times.length > 0 || messages.length > 0) && (
        <Section title="Tiempos">
          <dl>
            {times.map(([label, value]) => <Metric key={label} label={label}>{formatDuration(value)}</Metric>)}
            {messages.map(([label, value]) => <Metric key={label} label={label}>{formatInteger(value)}</Metric>)}
          </dl>
        </Section>
      )}
      {(g.mos !== null || rFactor !== undefined) && (
        <Section title="Calidad de la llamada">
          <dl>
            {g.mos !== null && <Metric label="MOS">{formatDecimal(g.mos, 1)}</Metric>}
            {rFactor !== undefined && <Metric label="Factor R">{formatInteger(rFactor)}</Metric>}
          </dl>
        </Section>
      )}
      {Object.keys(share).length > 0 && (
        <Section title="Reparto del tiempo">
          <Share title="Reparto del tiempo" values={share} labels={SPLIT_LABELS} format={(v) => formatKpi(v, '%')} />
        </Section>
      )}
      <Section title="Transcripción">
        <dl><Metric label="Calidad de la transcripción">{QUALITY_LABELS[g.transcript_quality]}</Metric></dl>
        <Share title="Confianza media por hablante" values={confidence} labels={SPEAKER_LABELS}
          format={(v) => `${formatInteger(v * 100)} %`} />
      </Section>
      {g.topics.length > 0 && (
        <Section title="Temas detectados">
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
                      <button type="button" onClick={() => onSelectTurn(target)} title="Ir a este momento de la conversación"
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

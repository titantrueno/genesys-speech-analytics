import { useState, type KeyboardEvent } from 'react'
import { Link } from 'react-router'
import { useRowNavigation } from '../conversations/useRowNavigation'
import { channelLabel, churnLabel, resolutionLabel } from '../conversations/labels'
import type { Translate } from '../i18n/context'
import { useI18n } from '../i18n/useI18n'
import { RankedBars } from '../dashboards/bars'
import { ChartCard, DataTable } from '../dashboards/ChartCard'
import { formatDateTime, formatDecimal, formatInteger, shortId } from '../lib/format'
import { useCatalog, optionLabel } from './catalog'
import type { FieldsResult, FieldState, FieldValue, MetricResult, ReportResult, RunOutput, TableResult, TargetField } from './types'

const percent = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

function ResultValue({ value }: { value: unknown }) {
  if (value !== null && typeof value === 'object') {
    return (
      <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-xs">
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key} className="contents">
            <dt className="font-mono text-slate-500">{key}</dt>
            <dd className="text-slate-800">{typeof item === 'boolean' ? (item ? 'sí' : 'no') : String(item)}</dd>
          </div>
        ))}
      </dl>
    )
  }
  return <span>{String(value)}</span>
}

function TableRow({ row }: { row: TableResult['rows'][number] }) {
  const { t } = useI18n()
  const { conversation } = row
  const href = `/conversaciones/${conversation.id}`
  const { onClick, onAuxClick, linkState } = useRowNavigation(href)
  return (
    <tr onClick={onClick} onAuxClick={onAuxClick} className="cursor-pointer border-b border-slate-100 align-top hover:bg-brand-50/60">
      <td className="px-2.5 py-2 whitespace-nowrap">
        <Link to={href} state={linkState} className="font-medium text-brand-700 hover:underline">{formatDateTime(conversation.started_at)}</Link>
        <p className="font-mono text-[11px] text-slate-400" title={conversation.id}>{shortId(conversation.id)}</p>
      </td>
      <td className="px-2.5 py-2 whitespace-nowrap text-slate-700">{channelLabel(t, conversation.channel)}</td>
      <td className="px-2.5 py-2 text-slate-700">{conversation.queue}</td>
      <td className="px-2.5 py-2">
        <span className="inline-block rounded-lg bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">{conversation.main_topic_label}</span>
      </td>
      <td className="min-w-72 px-2.5 py-2 text-slate-800"><ResultValue value={row.result} /></td>
    </tr>
  )
}

function TableOutput({ result, destination }: { result: TableResult; destination: string }) {
  return (
    <div className="overflow-x-auto">
      <p className="mb-2 text-sm text-slate-600">{formatInteger(result.rows.length)} conversaciones</p>
      <table aria-label={`Insights por conversación: ${destination}`} className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
            {['Fecha', 'Canal', 'Cola', 'Main topic', 'Resultado'].map((c) => <th key={c} scope="col" className="px-2.5 py-2 font-medium">{c}</th>)}
          </tr>
        </thead>
        <tbody>{result.rows.map((row) => <TableRow key={row.conversation.id} row={row} />)}</tbody>
      </table>
    </div>
  )
}

function MetricOutput({ result, destination }: { result: MetricResult; destination: string }) {
  const byPercent = result.aggregation === 'porcentaje'
  const items = result.items.map((i) => ({ key: i.label, label: i.label, value: byPercent ? i.percent : i.count }))
  return (
    <ChartCard title={destination}
      subtitle={`${byPercent ? '% de conversaciones' : 'Conversaciones'} por etiqueta · muestra de ${formatInteger(result.total)}`}
      table={<DataTable caption={`Tabla de ${destination}`} columns={['Etiqueta', 'Conversaciones', '%']}
        rows={result.items.map((i) => [i.label, formatInteger(i.count), `${percent.format(i.percent)} %`])} />}>
      <RankedBars label={`Gráfico de ${destination}`} items={items} maxValue={byPercent ? 100 : undefined}
        format={(v) => (byPercent ? `${percent.format(v ?? 0)} %` : formatInteger(v ?? 0))} />
    </ChartCard>
  )
}

const FIELD_STATES: Record<FieldState, { label: string; one: string; many: string; tone: string }> = {
  escrito: { label: 'Escrito', one: 'escrito', many: 'escritos', tone: 'bg-emerald-50 text-emerald-700' },
  omitido: { label: 'Omitido', one: 'omitido', many: 'omitidos', tone: 'bg-slate-100 text-slate-600' },
  rechazado: { label: 'Rechazado', one: 'rechazado', many: 'rechazados', tone: 'bg-amber-50 text-amber-800' },
  sin_valor: { label: 'Sin valor', one: 'sin valor', many: 'sin valor', tone: 'bg-slate-50 text-slate-500' },
  error: { label: 'Error', one: 'con error', many: 'con error', tone: 'bg-red-50 text-red-700' },
}

/** Grupos de columnas de la tabla (FE014): el análisis, cada check, los temas y las entidades. */
type ColumnGroup = 'analisis' | 'cumplimiento' | 'temas' | 'entidades'
const COLUMN_GROUPS: Record<ColumnGroup, string> = { analisis: 'Análisis', cumplimiento: 'Cumplimiento', temas: 'Temas', entidades: 'Entidades' }

function columnGroup(target: TargetField): ColumnGroup {
  if (target.startsWith('compliance:')) return 'cumplimiento'
  if (target.startsWith('entity:')) return 'entidades'
  return target === 'secondary_topics' || target === 'keywords' ? 'temas' : 'analisis'
}

function fieldValue(target: TargetField, value: FieldValue | undefined, t: Translate): string | null {
  if (value === undefined) return null
  if (target.startsWith('compliance:')) return value === true ? 'Cumple' : value === false ? 'No cumple' : 'No aplica'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'number') return formatDecimal(value, 2)
  if (target === 'resolution') return resolutionLabel(t, String(value))
  if (target === 'churn_risk') return churnLabel(t, String(value))
  return String(value)
}

function FieldRow({ row, targets }: { row: FieldsResult['rows'][number]; targets: FieldsResult['targets'] }) {
  const { t } = useI18n()
  const { conversation } = row
  const href = `/conversaciones/${conversation.id}`
  const { onClick, onAuxClick, linkState } = useRowNavigation(href)
  return (
    <tr onClick={onClick} onAuxClick={onAuxClick} className="cursor-pointer border-b border-slate-100 align-top hover:bg-brand-50/60">
      <td className="px-2.5 py-2 whitespace-nowrap">
        <Link to={href} state={linkState} className="font-medium text-brand-700 hover:underline">{formatDateTime(conversation.started_at)}</Link>
        <p className="font-mono text-[11px] text-slate-400" title={conversation.id}>{shortId(conversation.id)}</p>
      </td>
      <td className="px-2.5 py-2 whitespace-nowrap text-slate-700">{channelLabel(t, conversation.channel)}</td>
      {targets.map((target) => {
        const state = row.states[target]
        const value = fieldValue(target, row.values[target], t)
        const reason = row.reasons?.[target]
        return (
          <td key={target} className={`${target === 'summary' ? 'min-w-72' : 'min-w-32'} px-2.5 py-2 text-slate-800`}>
            {state && <span className={`mb-1 inline-block rounded-full px-2 py-0.5 text-xs ${FIELD_STATES[state].tone}`}>{FIELD_STATES[state].label}</span>}
            {value !== null && <p className={target === 'main_topic' ? 'font-mono text-xs' : ''}>{value}</p>}
            {reason && <p className="text-xs text-slate-500">{reason}</p>}
          </td>
        )
      })}
      <td className="px-2.5 py-2 text-xs text-slate-600">{row.reason}</td>
    </tr>
  )
}

/** «Guardar en campos» (FE013 y FE014): qué se escribió en cada conversación, campo a campo. Con campos de varios
 *  grupos, las columnas se agrupan y la tabla se desplaza en horizontal sin desbordar la página. */
function FieldsOutput({ result, destination }: { result: FieldsResult; destination: string }) {
  const catalog = useCatalog()
  const label = (target: string) => optionLabel(catalog.target_fields, target) ?? target
  const order = Object.keys(COLUMN_GROUPS) as ColumnGroup[]
  const targets = [...result.targets].sort((a, b) => order.indexOf(columnGroup(a)) - order.indexOf(columnGroup(b)))
  const spans = order.map((group) => [group, targets.filter((t) => columnGroup(t) === group).length] as const).filter(([, n]) => n > 0)
  return (
    <div className="space-y-3">
      <ul aria-label="Recuentos por campo" className="space-y-1 text-sm text-slate-700">
        {targets.map((target) => {
          const counts = result.counts[target]
          return (
            <li key={target}>
              <span className="font-medium">{label(target)}</span>:{' '}
              {(Object.keys(FIELD_STATES) as FieldState[]).map((state) => {
                const n = counts?.[state] ?? 0
                return `${formatInteger(n)} ${n === 1 ? FIELD_STATES[state].one : FIELD_STATES[state].many}`
              }).join(' · ')}
            </li>
          )
        })}
      </ul>
      <div className="overflow-x-auto">
        <table aria-label={`Campos guardados: ${destination}`} className="w-full text-sm">
          <thead>
            {spans.length > 1 && (
              <tr className="text-left text-xs text-slate-500">
                <th scope="colgroup" colSpan={2} />
                {spans.map(([group, n]) => (
                  <th key={group} scope="colgroup" colSpan={n} className="border-b border-slate-200 px-2.5 pt-2 font-semibold text-slate-600">{COLUMN_GROUPS[group]}</th>
                ))}
                <th scope="colgroup" colSpan={1} />
              </tr>
            )}
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
              {['Fecha', 'Canal', ...targets.map(label), 'Motivo'].map((c, i) => <th key={i} scope="col" className="px-2.5 py-2 font-medium">{c}</th>)}
            </tr>
          </thead>
          <tbody>{result.rows.map((row) => <FieldRow key={row.conversation.id} row={row} targets={targets} />)}</tbody>
        </table>
      </div>
    </div>
  )
}

function ReportOutput({ result }: { result: ReportResult }) {
  return <article className="rounded-lg bg-slate-50 p-4 text-sm leading-relaxed whitespace-pre-wrap text-slate-800">{result.text}</article>
}

/** Una pestaña por output, en el orden del grafo, con el patrón de pestañas de WAI-ARIA (flechas para cambiar). */
export function RunOutputs({ outputs }: { outputs: RunOutput[] }) {
  const [active, setActive] = useState(0)
  const current = outputs[Math.min(active, outputs.length - 1)]

  function onKeyDown(event: KeyboardEvent) {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!delta) return
    const next = (active + delta + outputs.length) % outputs.length
    setActive(next)
    document.getElementById(`output-tab-${outputs[next].node_id}`)?.focus()
  }

  return (
    <section aria-label="Resultados" className="space-y-3">
      <div role="tablist" aria-label="Outputs" className="flex flex-wrap gap-1 border-b border-slate-200" onKeyDown={onKeyDown}>
        {outputs.map((output, i) => {
          const selected = output === current
          return (
            <button key={output.node_id} id={`output-tab-${output.node_id}`} type="button" role="tab" aria-selected={selected}
              aria-controls={`output-panel-${output.node_id}`} tabIndex={selected ? 0 : -1} onClick={() => setActive(i)}
              className={`-mb-px rounded-t-md border px-3 py-1.5 text-sm ${selected ? 'border-slate-200 border-b-white bg-white font-medium text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
              {output.destination}
            </button>
          )
        })}
      </div>
      {current && (
        <div role="tabpanel" id={`output-panel-${current.node_id}`} aria-labelledby={`output-tab-${current.node_id}`}
          className="rounded-xl border border-slate-200 bg-white p-4">
          {current.kind === 'tabla' && <TableOutput result={current.result} destination={current.destination} />}
          {current.kind === 'metrica' && <MetricOutput result={current.result} destination={current.destination} />}
          {current.kind === 'informe' && <ReportOutput result={current.result} />}
          {current.kind === 'campo' && <FieldsOutput result={current.result} destination={current.destination} />}
        </div>
      )}
    </section>
  )
}

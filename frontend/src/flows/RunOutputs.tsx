import { useState, type KeyboardEvent } from 'react'
import { Link } from 'react-router'
import { useRowNavigation } from '../conversations/useRowNavigation'
import { CHANNEL_LABELS } from '../conversations/labels'
import { RankedBars } from '../dashboards/charts'
import { ChartCard, DataTable } from '../dashboards/ChartCard'
import { formatDateTime, formatInteger, shortId } from '../lib/format'
import type { MetricResult, ReportResult, RunOutput, TableResult } from './types'

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
  const { conversation } = row
  const href = `/conversaciones/${conversation.id}`
  const { onClick, onAuxClick, linkState } = useRowNavigation(href)
  return (
    <tr onClick={onClick} onAuxClick={onAuxClick} className="cursor-pointer border-b border-slate-100 align-top hover:bg-brand-50/60">
      <td className="px-2.5 py-2 whitespace-nowrap">
        <Link to={href} state={linkState} className="font-medium text-brand-700 hover:underline">{formatDateTime(conversation.started_at)}</Link>
        <p className="font-mono text-[11px] text-slate-400" title={conversation.id}>{shortId(conversation.id)}</p>
      </td>
      <td className="px-2.5 py-2 whitespace-nowrap text-slate-700">{CHANNEL_LABELS[conversation.channel]}</td>
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
        </div>
      )}
    </section>
  )
}

import { Trash2, Unlink, X } from 'lucide-react'
import { useI18n } from '../../i18n/useI18n'
import type { CanvasEdge, CanvasNode } from '../graph'
import { NODE_LABELS } from '../rules'
import type { DownloadConfig, OutputConfig, PromptConfig, SamplingConfig } from '../types'
import { control, Section } from './controls'
import { DownloadPanel } from './DownloadPanel'
import { useNodeNames } from './nodeNames'
import { OutputPanel } from './OutputPanel'
import { PromptPanel } from './PromptPanel'
import { SamplingPanel } from './SamplingPanel'

interface Props {
  node: CanvasNode
  nodes: CanvasNode[]
  edges: CanvasEdge[]
  editable: boolean
  onChange: (config: CanvasNode['data']['config']) => void
  onDelete: () => void
  onConnect: (source: string, target: string) => void
  onDisconnect: (edgeId: string) => void
  onClose: () => void
}

function Connections({ node, nodes, edges, editable, onConnect, onDisconnect }: Omit<Props, 'onChange' | 'onDelete' | 'onClose'>) {
  const { t } = useI18n()
  const names = useNodeNames(nodes)
  const incoming = edges.filter((e) => e.target === node.id)
  const outgoing = edges.filter((e) => e.source === node.id)
  const others = nodes.filter((n) => n.id !== node.id)
  const row = (edge: CanvasEdge, other: string) => (
    <li key={edge.id} className="flex items-center justify-between gap-2 text-sm text-slate-700">
      <span className="truncate">{names.get(other)}</span>
      {editable && (
        <button type="button" aria-label={t('flows.conn.disconnectFrom', { name: names.get(other) ?? '' })} onClick={() => onDisconnect(edge.id)}
          className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-xs text-slate-500 hover:bg-slate-100">
          <Unlink className="size-3.5" aria-hidden />{t('flows.conn.disconnect')}
        </button>
      )}
    </li>
  )
  const picker = (label: string, pick: (other: string) => void) => (
    <select aria-label={label} className={control} value="" onChange={(e) => e.target.value && pick(e.target.value)}>
      <option value="">{label}…</option>
      {others.map((n) => <option key={n.id} value={n.id}>{names.get(n.id)}</option>)}
    </select>
  )
  return (
    <Section title={t('flows.conn.title')}>
      {node.type !== 'descarga' && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-slate-600">{t('flows.conn.input')}</p>
          {incoming.length ? <ul>{incoming.map((e) => row(e, e.source))}</ul> : <p className="text-xs text-slate-500">{t('flows.conn.noInput')}</p>}
          {editable && incoming.length === 0 && picker(t('flows.conn.connectFrom'), (other) => onConnect(other, node.id))}
        </div>
      )}
      {node.type !== 'output' && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-slate-600">{t('flows.conn.outputs')}</p>
          {outgoing.length ? <ul>{outgoing.map((e) => row(e, e.target))}</ul> : <p className="text-xs text-slate-500">{t('flows.conn.noOutputs')}</p>}
          {editable && picker(t('flows.conn.addOutput'), (other) => onConnect(node.id, other))}
        </div>
      )}
    </Section>
  )
}

export function NodePanel(props: Props) {
  const { t } = useI18n()
  const { node, edges, nodes, editable, onChange, onDelete, onClose } = props
  const chained = edges.some((e) => e.target === node.id && nodes.find((n) => n.id === e.source)?.type === 'prompt')
  // El Prompt de entrada de un Output: sus campos JSON alimentan los campos destino de «Guardar en campos» (FE013).
  // Detrás de una caja «Genesys download», el Sampling trabaja con lo que descarga (FE017).
  const afterDownload = edges.some((e) => e.target === node.id && nodes.find((n) => n.id === e.source)?.type === 'descarga')
  const inputPrompt = nodes.find((n) => n.type === 'prompt' && edges.some((e) => e.source === n.id && e.target === node.id))
  return (
    <section aria-label={t('flows.panel.aria', { node: NODE_LABELS[node.type] })} className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">{NODE_LABELS[node.type]}</h2>
        <div className="flex items-center gap-1">
          {editable && (
            <button type="button" onClick={onDelete}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-red-700 hover:bg-red-50">
              <Trash2 className="size-3.5" aria-hidden />{t('flows.panel.delete')}
            </button>
          )}
          <button type="button" onClick={onClose} aria-label={t('flows.panel.close')} className="rounded p-1 text-slate-400 hover:bg-slate-100">
            <X className="size-4" aria-hidden />
          </button>
        </div>
      </header>
      {!editable && <p className="text-xs text-slate-500">{t('flows.panel.readOnly')}</p>}
      <fieldset disabled={!editable} className="min-w-0 space-y-3">
        <legend className="sr-only">{t('flows.panel.legend')}</legend>
        {node.type === 'descarga' && <DownloadPanel key={node.id} config={node.data.config as DownloadConfig} onChange={onChange} />}
        {node.type === 'sampling' && (
          <SamplingPanel config={node.data.config as SamplingConfig} afterDownload={afterDownload} onChange={onChange} />
        )}
        {node.type === 'prompt' && <PromptPanel config={node.data.config as PromptConfig} chained={chained} onChange={onChange} />}
        {node.type === 'output' && (
          <OutputPanel config={node.data.config as OutputConfig} prompt={inputPrompt?.data.config as PromptConfig | undefined} onChange={onChange} />
        )}
      </fieldset>
      <Connections {...props} />
    </section>
  )
}

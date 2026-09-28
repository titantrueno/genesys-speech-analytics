import { Trash2, Unlink, X } from 'lucide-react'
import type { CanvasEdge, CanvasNode } from '../graph'
import { NODE_LABELS } from '../rules'
import type { OutputConfig, PromptConfig, SamplingConfig } from '../types'
import { control, Section } from './controls'
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
  const names = useNodeNames(nodes)
  const incoming = edges.filter((e) => e.target === node.id)
  const outgoing = edges.filter((e) => e.source === node.id)
  const others = nodes.filter((n) => n.id !== node.id)
  const row = (edge: CanvasEdge, other: string) => (
    <li key={edge.id} className="flex items-center justify-between gap-2 text-sm text-slate-700">
      <span className="truncate">{names.get(other)}</span>
      {editable && (
        <button type="button" aria-label={`Desconectar de ${names.get(other)}`} onClick={() => onDisconnect(edge.id)}
          className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-xs text-slate-500 hover:bg-slate-100">
          <Unlink className="size-3.5" aria-hidden />Desconectar
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
    <Section title="Conexiones">
      {node.type !== 'sampling' && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-slate-600">Entrada</p>
          {incoming.length ? <ul>{incoming.map((e) => row(e, e.source))}</ul> : <p className="text-xs text-slate-500">Sin entrada.</p>}
          {editable && incoming.length === 0 && picker('Conectar entrada desde', (other) => onConnect(other, node.id))}
        </div>
      )}
      {node.type !== 'output' && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-slate-600">Salidas</p>
          {outgoing.length ? <ul>{outgoing.map((e) => row(e, e.target))}</ul> : <p className="text-xs text-slate-500">Sin salidas.</p>}
          {editable && picker('Añadir salida hacia', (other) => onConnect(node.id, other))}
        </div>
      )}
    </Section>
  )
}

export function NodePanel(props: Props) {
  const { node, edges, nodes, editable, onChange, onDelete, onClose } = props
  const chained = edges.some((e) => e.target === node.id && nodes.find((n) => n.id === e.source)?.type === 'prompt')
  return (
    <section aria-label={`Configuración del ${NODE_LABELS[node.type]}`} className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
      <header className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">{NODE_LABELS[node.type]}</h2>
        <div className="flex items-center gap-1">
          {editable && (
            <button type="button" onClick={onDelete}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-red-700 hover:bg-red-50">
              <Trash2 className="size-3.5" aria-hidden />Eliminar nodo
            </button>
          )}
          <button type="button" onClick={onClose} aria-label="Cerrar configuración" className="rounded p-1 text-slate-400 hover:bg-slate-100">
            <X className="size-4" aria-hidden />
          </button>
        </div>
      </header>
      {!editable && <p className="text-xs text-slate-500">Solo lectura: no tienes permiso para editar flujos.</p>}
      <fieldset disabled={!editable} className="min-w-0 space-y-3">
        <legend className="sr-only">Configuración</legend>
        {node.type === 'sampling' && <SamplingPanel config={node.data.config as SamplingConfig} onChange={onChange} />}
        {node.type === 'prompt' && <PromptPanel config={node.data.config as PromptConfig} chained={chained} onChange={onChange} />}
        {node.type === 'output' && <OutputPanel config={node.data.config as OutputConfig} onChange={onChange} />}
      </fieldset>
      <Connections {...props} />
    </section>
  )
}

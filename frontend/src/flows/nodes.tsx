import { Handle, Position, type NodeProps } from '@xyflow/react'
import { AlertCircle, CloudDownload, Filter, MessageSquareCode, Table2, type LucideIcon } from 'lucide-react'
import { useI18n } from '../i18n/useI18n'
import { nodeSummary, useCatalog } from './catalog'
import type { CanvasNode } from './graph'
import { NODE_STATUS } from './labels'
import { NODE_LABELS } from './rules'
import { StatusBadge } from './StatusBadge'
import type { NodeContent, NodeType } from './types'

const ICONS: Record<NodeType, LucideIcon> = { descarga: CloudDownload, sampling: Filter, prompt: MessageSquareCode, output: Table2 }
const ACCENT: Record<NodeType, string> = {
  descarga: 'border-t-amber-500',
  sampling: 'border-t-sky-500',
  prompt: 'border-t-violet-500',
  output: 'border-t-emerald-600',
}
const handle = '!size-3 !border-2 !border-white !bg-slate-500'

export function FlowNodeCard({ type, data, selected, isConnectable }: NodeProps<CanvasNode>) {
  const catalog = useCatalog()
  const i18n = useI18n()
  const { t } = i18n
  const Icon = ICONS[type]
  const [first, second] = nodeSummary({ type, config: data.config } as NodeContent, catalog, i18n)
  const issues = data.issues ?? []
  const state = data.state
  const ring = issues.length ? 'ring-2 ring-red-500' : selected ? 'ring-2 ring-brand-500' : ''

  return (
    <article aria-label={`${NODE_LABELS[type]}: ${first}`}
      className={`w-60 rounded-lg border border-t-4 border-slate-200 bg-white text-left shadow-sm ${ACCENT[type]} ${ring}`}>
      {type !== 'descarga' && <Handle type="target" position={Position.Left} className={handle} isConnectable={isConnectable} />}
      <header className="flex items-center justify-between gap-2 px-3 pt-2">
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
          <Icon className="size-3.5" aria-hidden />{NODE_LABELS[type]}
        </span>
        {state && <StatusBadge label={t(NODE_STATUS[state.status].label)} className={NODE_STATUS[state.status].className} />}
      </header>
      <div className="space-y-0.5 px-3 pt-1 pb-2">
        <p className="line-clamp-2 text-sm font-medium text-slate-800">{first}</p>
        <p className="truncate text-xs text-slate-500">{second}</p>
        {state && (
          <p className="text-xs text-slate-600 tabular-nums">
            {state.total === null ? t('flows.node.notStarted') : t('flows.node.processed', { processed: state.processed, total: state.total })}
          </p>
        )}
        {state?.message && <p className={`text-xs ${state.status === 'omitido' ? 'text-slate-500' : 'text-red-700'}`}>{state.message}</p>}
        {issues.length > 0 && (
          <p className="inline-flex items-center gap-1 text-xs font-medium text-red-700">
            <AlertCircle className="size-3.5" aria-hidden />{t('flows.node.errors', { count: issues.length, n: issues.length })}
          </p>
        )}
      </div>
      {type !== 'output' && <Handle type="source" position={Position.Right} className={handle} isConnectable={isConnectable} />}
    </article>
  )
}


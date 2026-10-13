import type { TKey } from '../i18n/dictionaries'
import type { FlowStatus, NodeStatus, RunStatus } from './types'

export const FLOW_STATUS: Record<FlowStatus, { label: TKey; className: string }> = {
  valido: { label: 'flows.status.valido', className: 'bg-green-50 text-[var(--status-good-text)]' },
  con_errores: { label: 'flows.status.con_errores', className: 'bg-amber-50 text-amber-800' },
}

export const RUN_STATUS: Record<RunStatus, { label: TKey; className: string }> = {
  pendiente: { label: 'flows.runStatus.pendiente', className: 'bg-slate-100 text-slate-600' },
  en_curso: { label: 'flows.runStatus.en_curso', className: 'bg-brand-50 text-brand-700' },
  ok: { label: 'flows.runStatus.ok', className: 'bg-green-50 text-[var(--status-good-text)]' },
  error: { label: 'flows.runStatus.error', className: 'bg-red-50 text-[var(--status-critical)]' },
}
/** Estado de un nodo: el de la ejecución, más `omitido` (FE017). */
export const NODE_STATUS: Record<NodeStatus, { label: TKey; className: string }> = {
  ...RUN_STATUS,
  omitido: { label: 'flows.runStatus.omitido', className: 'bg-slate-100 text-slate-500' },
}

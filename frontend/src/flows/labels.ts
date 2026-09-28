import type { FlowStatus, RunStatus } from './types'

export const FLOW_STATUS: Record<FlowStatus, { label: string; className: string }> = {
  valido: { label: 'Válido', className: 'bg-green-50 text-[var(--status-good-text)]' },
  con_errores: { label: 'Con errores', className: 'bg-amber-50 text-amber-800' },
}

export const RUN_STATUS: Record<RunStatus, { label: string; className: string }> = {
  pendiente: { label: 'Pendiente', className: 'bg-slate-100 text-slate-600' },
  en_curso: { label: 'En curso', className: 'bg-brand-50 text-brand-700' },
  ok: { label: 'OK', className: 'bg-green-50 text-[var(--status-good-text)]' },
  error: { label: 'Error', className: 'bg-red-50 text-[var(--status-critical)]' },
}

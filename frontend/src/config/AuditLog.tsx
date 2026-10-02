import type { UseQueryResult } from '@tanstack/react-query'
import { formatDateTime } from '../lib/format'
import { formatAuditValue } from './format'
import type { AuditEntry } from './types'

/** Registro de auditoría compartido (FE005 y FE006): cada sección pasa su consulta. */
export function AuditLog({ query }: { query: UseQueryResult<{ items: AuditEntry[] }> }) {
  const { data, isError, isPending } = query
  return (
    <section aria-label="Registro de cambios" className="space-y-2 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Registro de cambios</h2>
      {isPending && <p className="text-sm text-slate-500">Cargando registro…</p>}
      {isError && <p className="text-sm text-red-700">No se ha podido cargar el registro.</p>}
      {data && data.items.length === 0 && <p className="text-sm text-slate-500">Sin cambios registrados.</p>}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                {['Cuándo', 'Quién', 'Elemento', 'Antes', 'Después'].map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((entry) => (
                <tr key={entry.id} className="border-b border-slate-100 align-top last:border-0">
                  <td className="px-2 py-1.5 whitespace-nowrap text-slate-600">{formatDateTime(entry.at)}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap">{entry.user.name}</td>
                  <td className="px-2 py-1.5">{entry.element}</td>
                  <td className="px-2 py-1.5 text-slate-500">{formatAuditValue(entry.before)}</td>
                  <td className="px-2 py-1.5">{formatAuditValue(entry.after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

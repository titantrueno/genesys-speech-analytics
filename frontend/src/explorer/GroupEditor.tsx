import { Plus, Trash2 } from 'lucide-react'
import { ConditionRow } from './ConditionRow'
import { isGroup, type Condition, type Group, type GroupOp, type NodePath, type QuerySchema } from './queryModel'

export interface GroupHandlers {
  addCondition: (path: NodePath) => void
  addGroup: (path: NodePath) => void
  setOp: (path: NodePath, op: GroupOp) => void
  update: (path: NodePath, cond: Condition) => void
  remove: (path: NodePath) => void
}

interface Props {
  group: Group
  path: NodePath
  schema: QuerySchema
  from?: string
  to?: string
  errors: Map<string, string>
  handlers: GroupHandlers
}

const MAX_DEPTH = 2

export function GroupEditor({ group, path, schema, from, to, errors, handlers }: Props) {
  const depth = path.length + 1
  const prefix = path.map((i) => i + 1).join('.')
  const name = depth === 1 ? 'Condiciones' : `Subgrupo ${prefix}`

  return (
    <section aria-label={name}
      className={depth === 1 ? 'space-y-2' : 'space-y-2 rounded-lg border border-dashed border-brand-100 bg-brand-50/40 p-2.5'}>
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Combinar con" className="flex rounded-md border border-slate-200 bg-white p-0.5 text-xs">
          {(['and', 'or'] as const).map((op) => (
            <button key={op} type="button" aria-pressed={group.op === op} onClick={() => handlers.setOp(path, op)}
              className={`rounded px-2.5 py-1 font-medium ${group.op === op ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
              {op === 'and' ? 'Y' : 'O'}
            </button>
          ))}
        </div>
        <button type="button" onClick={() => handlers.addCondition(path)}
          className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-sm text-slate-700 hover:bg-slate-50">
          <Plus className="size-3.5" aria-hidden />Añadir condición
        </button>
        {depth < MAX_DEPTH && (
          <button type="button" onClick={() => handlers.addGroup(path)}
            className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-sm text-slate-700 hover:bg-slate-50">
            <Plus className="size-3.5" aria-hidden />Añadir grupo
          </button>
        )}
        {depth > 1 && (
          <button type="button" onClick={() => handlers.remove(path)}
            className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100">
            <Trash2 className="size-3.5" aria-hidden />Quitar grupo
          </button>
        )}
      </div>
      {group.conditions.map((node, i) => {
        const childPath = [...path, i]
        return isGroup(node) ? (
          <GroupEditor key={i} group={node} path={childPath} schema={schema} from={from} to={to} errors={errors} handlers={handlers} />
        ) : (
          <ConditionRow key={i} label={childPath.map((n) => n + 1).join('.')} cond={node} schema={schema} from={from} to={to}
            error={errors.get(childPath.join('.'))}
            onChange={(cond) => handlers.update(childPath, cond)} onRemove={() => handlers.remove(childPath)} />
        )
      })}
      {group.conditions.length === 0 && depth > 1 && <p className="text-xs text-slate-500">Grupo vacío: añade condiciones.</p>}
    </section>
  )
}

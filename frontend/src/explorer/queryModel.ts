export type FieldType = 'categorical' | 'numeric' | 'check' | 'text' | 'boolean'
export type GroupOp = 'and' | 'or'
export type Speaker = 'cliente' | 'agente' | 'bot'
export type ConditionValue = string | number | boolean | string[] | number[] | null | undefined

export interface Condition {
  field: string
  operator: string
  value?: ConditionValue
  speaker?: Speaker
}

export interface Group {
  op: GroupOp
  conditions: QueryNode[]
}

export type QueryNode = Condition | Group

export interface ExplorerQuery {
  from?: string
  to?: string
  root: Group
}

export interface FieldSchema {
  key: string
  label: string
  type: FieldType
  operators: Array<{ key: string; label: string }>
  values?: Array<{ value: string; label: string }>
  min?: number
  max?: number
  speakers?: Speaker[]
}

export interface QuerySchema {
  reference_date: string
  default_period: { from: string; to: string }
  fields: FieldSchema[]
}

export type NodePath = number[]

export const DEFAULT_QUERY: ExplorerQuery = { root: { op: 'and', conditions: [] } }

export function isGroup(node: QueryNode): node is Group {
  return 'op' in node
}

function toBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text)
  let binary = ''
  bytes.forEach((b) => { binary += String.fromCharCode(b) })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function fromBase64Url(value: string): string {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
  const binary = atob(padded)
  return new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0)))
}

function isValidNode(node: unknown, depth: number): boolean {
  if (typeof node !== 'object' || node === null) return false
  if ('op' in node) {
    const group = node as Group
    return depth <= 3 && (group.op === 'and' || group.op === 'or') && Array.isArray(group.conditions)
      && group.conditions.every((child) => isValidNode(child, depth + 1))
  }
  const cond = node as Condition
  return typeof cond.field === 'string' && typeof cond.operator === 'string'
}

export function encodeQuery(query: ExplorerQuery): string {
  return toBase64Url(JSON.stringify(query))
}

export function decodeQuery(value: string | null): { query: ExplorerQuery; error: boolean } {
  if (!value) return { query: DEFAULT_QUERY, error: false }
  try {
    const parsed = JSON.parse(fromBase64Url(value)) as ExplorerQuery
    if (isValidNode(parsed?.root, 1) && isGroup(parsed.root)) return { query: parsed, error: false }
  } catch {
    // cae a la consulta por defecto
  }
  return { query: DEFAULT_QUERY, error: true }
}

const numberFormat = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 })

function valueLabel(field: FieldSchema | undefined, value: unknown): string {
  if (typeof value === 'number') return numberFormat.format(value)
  if (typeof value === 'boolean') return value ? 'sí' : 'no'
  return field?.values?.find((v) => v.value === value)?.label ?? String(value)
}

function conditionText(cond: Condition, schema: QuerySchema): string {
  const field = schema.fields.find((f) => f.key === cond.field)
  const label = `${field?.label ?? cond.field}${cond.speaker ? ` (${cond.speaker})` : ''}`
  const operator = field?.operators.find((o) => o.key === cond.operator)?.label ?? cond.operator
  if (field?.type === 'check') return `${label} ${operator}`
  if (field?.type === 'text') return `${label} ${operator} «${cond.value ?? ''}»`
  if (cond.operator === 'between' && Array.isArray(cond.value)) {
    return `${label} ${operator} ${valueLabel(field, cond.value[0])} y ${valueLabel(field, cond.value[1])}`
  }
  const values = Array.isArray(cond.value) ? cond.value : [cond.value]
  return `${label} ${operator} ${values.map((v) => valueLabel(field, v)).join(', ')}`
}

function groupText(group: Group, schema: QuerySchema, nested: boolean): string {
  const parts = group.conditions.map((node) => (isGroup(node) ? groupText(node, schema, true) : conditionText(node, schema)))
  const text = parts.join(group.op === 'and' ? ' Y ' : ' O ')
  return nested && parts.length > 1 ? `(${text})` : text
}

export function queryToText(query: ExplorerQuery, schema: QuerySchema): string {
  return query.root.conditions.length === 0 ? 'Todas las conversaciones del periodo' : groupText(query.root, schema, false)
}

function mapGroup(group: Group, path: NodePath, update: (group: Group) => Group): Group {
  if (path.length === 0) return update(group)
  const [head, ...rest] = path
  return {
    ...group,
    conditions: group.conditions.map((child, i) => (i === head && isGroup(child) ? mapGroup(child, rest, update) : child)),
  }
}

export function addCondition(query: ExplorerQuery, groupPath: NodePath, condition: Condition): ExplorerQuery {
  return { ...query, root: mapGroup(query.root, groupPath, (g) => ({ ...g, conditions: [...g.conditions, condition] })) }
}

export function addGroup(query: ExplorerQuery, groupPath: NodePath, op: GroupOp): ExplorerQuery {
  return { ...query, root: mapGroup(query.root, groupPath, (g) => ({ ...g, conditions: [...g.conditions, { op, conditions: [] }] })) }
}

export function setGroupOp(query: ExplorerQuery, groupPath: NodePath, op: GroupOp): ExplorerQuery {
  return { ...query, root: mapGroup(query.root, groupPath, (g) => ({ ...g, op })) }
}

export function updateCondition(query: ExplorerQuery, path: NodePath, patch: Partial<Condition>): ExplorerQuery {
  const index = path[path.length - 1]
  return {
    ...query,
    root: mapGroup(query.root, path.slice(0, -1), (g) => ({
      ...g,
      conditions: g.conditions.map((child, i) => (i === index && !isGroup(child) ? { ...child, ...patch } : child)),
    })),
  }
}

export function removeNode(query: ExplorerQuery, path: NodePath): ExplorerQuery {
  const index = path[path.length - 1]
  return {
    ...query,
    root: mapGroup(query.root, path.slice(0, -1), (g) => ({ ...g, conditions: g.conditions.filter((_, i) => i !== index) })),
  }
}

export function pathFromApi(apiPath: string): NodePath | null {
  if (!apiPath.startsWith('root')) return null
  return [...apiPath.matchAll(/conditions\[(\d+)\]/g)].map((m) => Number(m[1]))
}

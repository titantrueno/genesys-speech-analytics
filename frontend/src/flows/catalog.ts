import { createContext, useContext } from 'react'
import type { FlowCatalog, NodeContent, Option } from './types'

export const CatalogContext = createContext<FlowCatalog | null>(null)

export function useCatalog(): FlowCatalog {
  const catalog = useContext(CatalogContext)
  if (!catalog) throw new Error('useCatalog debe usarse dentro de CatalogContext')
  return catalog
}

export function optionLabel(options: Option[], value: string | undefined): string | undefined {
  return options.find((o) => o.value === value)?.label
}

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** Líneas que resumen la configuración de un nodo en el lienzo. */
export function nodeSummary(node: NodeContent, catalog: FlowCatalog): string[] {
  if (node.type === 'sampling') {
    const { method, stratify_by, order_by, order, size, query } = node.config
    let how = optionLabel(catalog.sampling_methods, method) ?? 'Sin método'
    if (method === 'estratificado' && stratify_by) how += ` por ${optionLabel(catalog.strata, stratify_by)?.toLowerCase()}`
    if (method === 'primeros_n' && order_by) how += ` por ${optionLabel(catalog.order_keys, order_by)?.toLowerCase()} (${order === 'asc' ? 'asc.' : 'desc.'})`
    const conditions = query?.root.conditions.length ?? 0
    return [
      size ? `${how} · ${count(size, 'conversación', 'conversaciones')}` : how,
      conditions ? count(conditions, 'filtro', 'filtros') : 'Sin filtros',
    ]
  }
  if (node.type === 'prompt') {
    const { template, model, temperature, output } = node.config
    const format = optionLabel(catalog.output_formats, output?.type) ?? 'Sin formato'
    const detail = output?.type === 'etiqueta' ? ` (${count(output.labels?.length ?? 0, 'etiqueta', 'etiquetas')})`
      : output?.type === 'json' ? ` (${count(output.fields?.length ?? 0, 'campo', 'campos')})` : ''
    return [
      template?.trim() ? template.trim() : 'Sin plantilla',
      `${optionLabel(catalog.models, model) ?? 'Sin modelo'} · T ${temperature ?? '—'} · ${format}${detail}`,
    ]
  }
  const { kind, aggregation, destination } = node.config
  const kindLabel = optionLabel(catalog.output_kinds, kind) ?? 'Sin tipo'
  return [
    kind === 'metrica' && aggregation ? `${kindLabel} · ${optionLabel(catalog.aggregations, aggregation)}` : kindLabel,
    destination?.trim() ? `→ ${destination.trim()}` : 'Sin destino',
  ]
}

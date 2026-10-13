import { createContext, useContext } from 'react'
import type { Labeler } from '../explorer/labels'
import { CHANNEL_KEYS, describeInterval, describeSchedule } from '../downloads/labels'
import { DEFAULT_I18N } from '../i18n/context'
import type { FlowCatalog, NodeContent, Option } from './types'

export const CatalogContext = createContext<FlowCatalog | null>(null)

export function useCatalog(): FlowCatalog {
  const catalog = useContext(CatalogContext)
  if (!catalog) throw new Error('useCatalog debe usarse dentro de CatalogContext')
  return catalog
}

/**
 * El catálogo de flujos llega del backend con etiquetas en español. Las opciones fijas (métodos, formatos, tipos de
 * output…) se traducen por clave `flows.cat.<grupo>.<valor>`; las que dependen de datos (checks, modelos nuevos) se
 * muestran como llegan (FE016).
 */
export function catalogLabel(i18n: Labeler, group: string, option: Option): string {
  return i18n.tOr(`flows.cat.${group}.${option.value}`, option.label)
}

export function optionLabel(options: Option[], value: string | undefined, i18n?: Labeler, group?: string): string | undefined {
  const option = options.find((o) => o.value === value)
  if (!option) return undefined
  return i18n && group ? catalogLabel(i18n, group, option) : option.label
}

/** Líneas que resumen la configuración de un nodo en el lienzo; sin traductor, en español. */
export function nodeSummary(node: NodeContent, catalog: FlowCatalog, i18n: Labeler = DEFAULT_I18N): string[] {
  const { t } = i18n
  const count = (n: number, key: 'flows.sum.conversations' | 'flows.sum.filters' | 'flows.sum.labels' | 'flows.sum.fields') => t(key, { count: n, n })
  if (node.type === 'descarga') {
    const { interval, channels, schedule } = node.config
    const channelList = (channels ?? []).map((c) => t(CHANNEL_KEYS[c])).join(' + ')
    return [
      interval ? describeInterval(t, interval) : t('flows.sum.noInterval'),
      [channelList || t('flows.sum.noChannels'), describeSchedule(t, schedule ?? { type: 'desactivada' })].join(' · '),
    ]
  }
  if (node.type === 'sampling') {
    const { method, stratify_by, order_by, order, size, query } = node.config
    let how = optionLabel(catalog.sampling_methods, method, i18n, 'sampling_methods') ?? t('flows.sum.noMethod')
    if (method === 'estratificado' && stratify_by) how += t('flows.sum.by', { value: optionLabel(catalog.strata, stratify_by, i18n, 'strata')?.toLowerCase() ?? '' })
    if (method === 'primeros_n' && order_by) {
      how += `${t('flows.sum.by', { value: optionLabel(catalog.order_keys, order_by, i18n, 'order_keys')?.toLowerCase() ?? '' })} (${t(order === 'asc' ? 'flows.sum.asc' : 'flows.sum.desc')})`
    }
    const conditions = query?.root.conditions.length ?? 0
    return [
      size ? `${how} · ${count(size, 'flows.sum.conversations')}` : how,
      conditions ? count(conditions, 'flows.sum.filters') : t('flows.sum.noFilters'),
    ]
  }
  if (node.type === 'prompt') {
    const { template, model, temperature, output } = node.config
    const format = optionLabel(catalog.output_formats, output?.type, i18n, 'output_formats') ?? t('flows.sum.noFormat')
    const detail = output?.type === 'etiqueta' ? ` (${count(output.labels?.length ?? 0, 'flows.sum.labels')})`
      : output?.type === 'json' ? ` (${count(output.fields?.length ?? 0, 'flows.sum.fields')})` : ''
    return [
      template?.trim() ? template.trim() : t('flows.sum.noTemplate'),
      `${optionLabel(catalog.models, model, i18n, 'models') ?? t('flows.sum.noModel')} · ${t('flows.sum.temperature', { value: temperature ?? '—' })} · ${format}${detail}`,
    ]
  }
  const { kind, aggregation, destination, mappings } = node.config
  const kindLabel = optionLabel(catalog.output_kinds, kind, i18n, 'output_kinds') ?? t('flows.sum.noKind')
  if (kind === 'campo') {
    const targets = (mappings ?? []).map((m) => optionLabel(catalog.target_fields, m.target, i18n, 'target_fields') ?? m.target)
    return [kindLabel, targets.length ? `→ ${targets.join(' + ')}` : t('flows.sum.noTargets')]
  }
  return [
    kind === 'metrica' && aggregation ? `${kindLabel} · ${optionLabel(catalog.aggregations, aggregation, i18n, 'aggregations')}` : kindLabel,
    destination?.trim() ? `→ ${destination.trim()}` : t('flows.sum.noDestination'),
  ]
}

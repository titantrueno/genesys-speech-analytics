import type { I18nContextValue } from '../i18n/context'
import type { FieldSchema } from './queryModel'

/** Traductor mínimo que necesitan las etiquetas del catálogo (`useI18n()` o el español por defecto). */
export type Labeler = Pick<I18nContextValue, 't' | 'tOr'>

/**
 * El catálogo del explorador llega del backend con etiquetas en español. Los campos, operadores y valores fijos se
 * traducen por clave; lo demás (checks, colas, agentes, main topics, temas…) son datos y se muestra como llega (FE016).
 */
export const fieldLabel = (i18n: Labeler, field: Pick<FieldSchema, 'key' | 'label'>) => i18n.tOr(`exp.field.${field.key}`, field.label)
export const operatorLabel = (i18n: Labeler, operator: { key: string; label: string }) => i18n.tOr(`exp.op.${operator.key}`, operator.label)
export const valueLabel = (i18n: Labeler, fieldKey: string, option: { value: string; label: string }) =>
  i18n.tOr(`exp.value.${fieldKey}.${option.value}`, option.label)

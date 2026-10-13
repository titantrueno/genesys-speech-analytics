import { ApiError } from '../api/client'
import type { Translate } from '../i18n/context'

/** Motivo de un rechazo de la API (protecciones, rol en uso…; el backend responde en inglés) o un mensaje genérico. */
export function actionError(error: unknown, t: Translate): string {
  return error instanceof ApiError && typeof error.detail === 'string' ? error.detail : t('usr.actionError')
}

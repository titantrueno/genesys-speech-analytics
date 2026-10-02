import { ApiError } from '../api/client'

/** Motivo de un rechazo de la API (protecciones, rol en uso…) o un mensaje genérico. */
export function actionError(error: unknown): string {
  return error instanceof ApiError && typeof error.detail === 'string' ? error.detail : 'No se ha podido completar la acción.'
}

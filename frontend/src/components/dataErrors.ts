import { ApiError } from '../api/client'

const MESSAGE = 'Los datos reales no están disponibles'

/** El origen real no responde (FE012): la API contesta `503` con este mensaje. El `503` del servicio de ingesta es otro. */
export function isDataUnavailable(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 503 && error.message === MESSAGE
}

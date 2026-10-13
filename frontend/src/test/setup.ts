import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Con la suite completa en paralelo, un debounce de 300 ms más el render pueden pasar de 1 s (el valor por defecto):
// `findBy…` y `waitFor` esperan el mismo estado, solo con más margen.
configure({ asyncUtilTimeout: 3000 })

// Swagger UI (pestaña «API», FE010) no se carga en jsdom: todos los tests usan el doble.
vi.mock('swagger-ui-react', () => import('./swaggerStub'))

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

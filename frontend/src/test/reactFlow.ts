/**
 * React Flow mide nodos y lienzo con el DOM, y jsdom no tiene layout. Mock según la guía de testing de React Flow
 * (https://reactflow.dev/learn/advanced-use/testing): un ResizeObserver que informa al observar, DOMMatrixReadOnly
 * y medidas a partir del estilo en línea. La guía no incluye `contentRect`, que la versión 12.12 necesita.
 */
class ResizeObserverMock {
  private readonly callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }

  observe(target: Element) {
    // React Flow 12.12 también lee `contentRect` (el lienzo usa su tamaño como extensión del zoom).
    const { offsetWidth: width, offsetHeight: height } = target as HTMLElement
    this.callback([{ target, contentRect: { width, height } } as ResizeObserverEntry], this as unknown as ResizeObserver)
  }

  unobserve() {}
  disconnect() {}
}

class DOMMatrixReadOnlyMock {
  m22: number

  constructor(transform?: string) {
    const scale = transform?.match(/scale\(([\d.]+)\)/)?.[1]
    this.m22 = scale !== undefined ? Number(scale) : 1
  }
}

let installed = false

export function mockReactFlow() {
  if (installed) return
  installed = true
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
  globalThis.DOMMatrixReadOnly = DOMMatrixReadOnlyMock as unknown as typeof DOMMatrixReadOnly
  Object.defineProperties(HTMLElement.prototype, {
    offsetHeight: { get() { return parseFloat((this as HTMLElement).style.height) || 1 } },
    offsetWidth: { get() { return parseFloat((this as HTMLElement).style.width) || 1 } },
  })
  ;(SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () => ({ x: 0, y: 0, width: 0, height: 0 }) as DOMRect
}

import type { MouseEvent } from 'react'
import { useLocation, useNavigate } from 'react-router'

const INTERACTIVE = 'a, button, input, select, textarea, label'

/**
 * Patrón «fila navegable» (vault/ingenieria/patrones-de-interfaz.md): el contenedor entero abre `href`,
 * Ctrl/Cmd+clic y clic central abren una pestaña nueva, y no se navega si hay texto seleccionado
 * o el clic sale de un elemento interactivo interno.
 */
export function useRowNavigation(href: string) {
  const location = useLocation()
  const navigate = useNavigate()
  const openInNewTab = () => window.open(href, '_blank', 'noopener')

  function onClick(event: MouseEvent<HTMLElement>) {
    if ((event.target as Element).closest(INTERACTIVE)) return
    if (window.getSelection()?.toString()) return
    if (event.ctrlKey || event.metaKey) {
      openInNewTab()
      return
    }
    navigate(href, { state: { from: location } })
  }

  function onAuxClick(event: MouseEvent<HTMLElement>) {
    if (event.button !== 1 || (event.target as Element).closest(INTERACTIVE)) return
    event.preventDefault()
    openInNewTab()
  }

  return { onClick, onAuxClick, linkState: { from: location } }
}

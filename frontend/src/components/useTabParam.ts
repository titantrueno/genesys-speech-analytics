import { useSearchParams } from 'react-router'
import type { TabItem } from './Tabs'

/** Pestaña actual en `?tab=` (la primera no aparece en la URL), para que recargar mantenga la pestaña. */
export function useTabParam<T extends string, Tab extends TabItem<T>>(tabs: Tab[]): [Tab, (code: T) => void] {
  const [params, setParams] = useSearchParams()
  const current = tabs.find((t) => t.code === params.get('tab')) ?? tabs[0]
  const select = (code: T) => setParams(code === tabs[0].code ? {} : { tab: code }, { replace: true })
  return [current, select]
}

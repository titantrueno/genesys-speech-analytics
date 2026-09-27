import type { SortKey, SortOrder } from '../api/conversations'

export interface SortState { sort: SortKey; order: SortOrder }

export function nextSort(current: SortState, key: SortKey): SortState {
  return { sort: key, order: current.sort === key && current.order === 'desc' ? 'asc' : 'desc' }
}

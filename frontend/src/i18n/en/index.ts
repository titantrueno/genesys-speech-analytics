import type { es as spanish } from '../es'
import { common } from './common'
import { layout } from './layout'
import { login } from './login'
import { pages } from './pages'

export const en: Record<keyof typeof spanish, string> = { ...common, ...layout, ...login, ...pages }

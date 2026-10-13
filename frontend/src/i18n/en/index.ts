import type { es as spanish } from '../es'
import { common } from './common'
import { conv } from './conv'
import { dash } from './dash'
import { domain } from './domain'
import { explorer } from './explorer'
import { flows } from './flows'
import { layout } from './layout'
import { login } from './login'
import { pages } from './pages'
import { search } from './search'

export const en: Record<keyof typeof spanish, string> = { ...common, ...domain, ...layout, ...login, ...pages, ...dash, ...conv, ...explorer, ...search, ...flows }

import { common } from './common'
import { conv } from './conv'
import { dash } from './dash'
import { domain } from './domain'
import { explorer } from './explorer'
import { layout } from './layout'
import { login } from './login'
import { pages } from './pages'
import { search } from './search'

export const es = { ...common, ...domain, ...layout, ...login, ...pages, ...dash, ...conv, ...explorer, ...search }

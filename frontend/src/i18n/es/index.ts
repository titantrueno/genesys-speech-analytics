import { common } from './common'
import { conv } from './conv'
import { dash } from './dash'
import { domain } from './domain'
import { downloads } from './downloads'
import { explorer } from './explorer'
import { flows } from './flows'
import { layout } from './layout'
import { login } from './login'
import { pages } from './pages'
import { search } from './search'
import { users } from './users'

export const es = { ...common, ...domain, ...layout, ...login, ...pages, ...dash, ...conv, ...explorer, ...search, ...flows, ...downloads, ...users }

import { common } from './common'
import { conv } from './conv'
import { dash } from './dash'
import { domain } from './domain'
import { layout } from './layout'
import { login } from './login'
import { pages } from './pages'

export const es = { ...common, ...domain, ...layout, ...login, ...pages, ...dash, ...conv }

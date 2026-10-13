import type { layout as es } from '../es/layout'

export const layout: Record<keyof typeof es, string> = {
  'layout.nav.label': 'Main',
  'layout.nav.dashboards': 'Dashboards',
  'layout.nav.conversations': 'Conversations',
  'layout.nav.explorer': 'Explorer',
  'layout.nav.search': 'Semantic search',
  'layout.nav.flows': 'Insight flows',
  'layout.nav.config': 'Settings',
  'layout.nav.users': 'Users and roles',
  'layout.logout': 'Sign out',
  'layout.org': 'Banco Horizonte',
  'dataUnavailable.help':
    'The platform is using the real conversations and PostgreSQL is not responding. You can go back to the synthetic data in',
  'dataUnavailable.link': 'Settings · Data sources',
}

import type { pages as es } from '../es/pages'

export const pages: Record<keyof typeof es, string> = {
  'pages.forbidden.title': 'No access',
  'pages.forbidden.body': 'Your role does not have permission to view this section. If you need it, ask an administrator.',
  'pages.notFound.title': 'Page not found',
  'pages.notFound.home': 'Back to home',
}

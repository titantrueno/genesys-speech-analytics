import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { conversationRoutes, metricsRoutes, QUEUE } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'

async function openDashboard(path: string) {
  signedInAs(USERS.admin, { ...metricsRoutes, ...conversationRoutes })
  const result = renderApp(path)
  await screen.findByRole('heading', { level: 1, name: 'Dashboards' })
  return result
}

function params(router: ReturnType<typeof renderApp>['router']) {
  return new URLSearchParams(router.state.location.search)
}

describe('drill-down desde dashboards', () => {
  it('una tarjeta de KPI lleva al listado con los filtros del dashboard y el filtro del KPI', async () => {
    const { router } = await openDashboard('/dashboards/vision-general?channel=chat&from=2026-09-01&to=2026-09-20')
    const tile = await screen.findByRole('group', { name: 'Tasa de escalado' })
    await userEvent.setup().click(within(tile).getByRole('link'))

    await waitFor(() => expect(router.state.location.pathname).toBe('/conversaciones'))
    const p = params(router)
    expect(p.get('resolution')).toBe('escalada')
    expect(p.get('channel')).toBe('chat')
    expect(p.get('from')).toBe('2026-09-01')
    expect(p.get('to')).toBe('2026-09-20')
  })

  it.each([
    ['Riesgo de abandono alto', 'experiencia-de-cliente', 'churn_risk', 'alto'],
    ['Conversaciones negativas', 'experiencia-de-cliente', 'sentiment_lt', '-0.3'],
    ['Cumplimiento', 'calidad-y-cumplimiento', 'compliant', 'true'],
    ['Primera respuesta (chat)', 'experiencia-de-cliente', 'channel', 'chat'],
  ])('la tarjeta %s añade su filtro', async (kpi, dashboard, key, value) => {
    const { router } = await openDashboard(`/dashboards/${dashboard}`)
    await userEvent.setup().click(within(await screen.findByRole('group', { name: kpi })).getByRole('link'))
    await waitFor(() => expect(router.state.location.pathname).toBe('/conversaciones'))
    expect(params(router).get(key)).toBe(value)
  })

  it('una barra de main topic sustituye el filtro de main topic del dashboard', async () => {
    const { router } = await openDashboard(`/dashboards/vision-general?main_topic=cajeros&main_topic=acceso_banca_digital&queue=${QUEUE.tarjetas.id}`)
    const list = await screen.findByRole('list', { name: 'Distribución por main topic' })
    await userEvent.setup().click(within(list).getByRole('link', { name: /Cargo no reconocido/ }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/conversaciones'))
    expect(params(router).getAll('main_topic')).toEqual(['cargo_no_reconocido'])
    expect(params(router).get('queue')).toBe(QUEUE.tarjetas.id)
  })

  it('una barra de un KPI por cola combina la cola y el filtro del KPI', async () => {
    const { router } = await openDashboard('/dashboards/calidad-y-cumplimiento')
    const list = await screen.findByRole('list', { name: 'Cumplimiento por cola' })
    await userEvent.setup().click(within(list).getByRole('link', { name: /Fraude y seguridad/ }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/conversaciones'))
    expect(params(router).get('queue')).toBe(QUEUE.fraude.id)
    expect(params(router).get('compliant')).toBe('true')
  })

  it('un punto de la serie (vía su tabla) filtra por su periodo', async () => {
    const { router } = await openDashboard('/dashboards/vision-general?granularity=week')
    const card = (await screen.findByRole('heading', { level: 2, name: 'Volumen de conversaciones' })).closest('section')!
    const user = userEvent.setup()
    await user.click(within(card).getByRole('button', { name: 'Ver tabla' }))
    const table = await within(card).findByRole('table')
    await user.click(within(table).getAllByRole('link')[1])
    await waitFor(() => expect(router.state.location.pathname).toBe('/conversaciones'))
    expect(params(router).get('from')).toBe('2026-09-14')
    expect(params(router).get('to')).toBe('2026-09-14')
    expect(params(router).has('granularity')).toBe(false)
  })

  it('una fila de la tabla por main topic y un segmento de canal llevan al listado', async () => {
    const { router } = await openDashboard('/dashboards/vision-general')
    const table = await screen.findByRole('table', { name: 'KPIs por main topic' })
    await userEvent.setup().click(within(table).getByRole('link', { name: 'Incidencia en cajero' }))
    await waitFor(() => expect(params(router).get('main_topic')).toBe('cajeros'))

    router.navigate('/dashboards/vision-general')
    const legend = await screen.findByRole('list', { name: 'Volumen por canal' })
    await userEvent.setup().click(within(legend).getByRole('link', { name: /Chat/ }))
    await waitFor(() => expect(params(router).get('channel')).toBe('chat'))
  })
})

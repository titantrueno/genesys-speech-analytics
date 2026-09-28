import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { formatDateTime, formatDateTimeLong, setDisplayTimeZone } from '../lib/format'
import {
  catalogFixture, conversationDetailFixture, conversationItem, DETAIL_ID, detailRoutes, metricsRoutes, searchResponse,
  summaryFixture,
} from '../test/fixtures'
import { setupEditor } from '../test/flowEditor'
import { renderApp, signedInAs, USERS } from '../test/utils'

const PUBLIC = { platform_name: 'Analítica Horizonte', timezone: 'Asia/Tokyo', language: 'es-ES' }
const publicRoute = (config = PUBLIC) => ({ 'GET /api/config/public': () => ({ status: 200, body: config }) })
// 21:30 en Madrid (UTC+2) son las 04:30 del día siguiente en Tokio (UTC+9).
const LATE = '2026-09-26T21:30:00+02:00'

afterEach(() => setDisplayTimeZone(undefined))

describe('Zona horaria configurada', () => {
  it('los formateadores compartidos usan la zona configurada', () => {
    setDisplayTimeZone('Europe/Madrid')
    expect(formatDateTime(LATE)).toBe('26 sept, 21:30')
    setDisplayTimeZone('Asia/Tokyo')
    expect(formatDateTime(LATE)).toBe('27 sept, 04:30')
    expect(formatDateTimeLong(LATE)).toMatch(/27 de septiembre de 2026.*4:30/)
  })

  it('ningún componente formatea fechas por su cuenta', () => {
    const sources = import.meta.glob(['../**/*.tsx', '../**/*.ts', '!../**/*.test.*', '!../lib/format.ts'],
      { query: '?raw', import: 'default', eager: true }) as Record<string, string>
    const offenders = Object.entries(sources).filter(([, code]) => /Intl\.DateTimeFormat|toLocale(Date|Time)String\(/.test(code))
    expect(offenders.map(([path]) => path)).toEqual([])
  })

  it('el listado muestra la hora en la zona configurada', async () => {
    signedInAs(USERS.admin, {
      ...publicRoute(),
      'GET /api/conversations': () => ({ status: 200, body: {
        total: 1, page: 1, page_size: 25, pages: 1, items: [{ ...conversationItem(0), started_at: LATE }] } }),
      'GET /api/catalog': () => ({ status: 200, body: catalogFixture }),
    })
    renderApp('/conversaciones')
    const cell = await screen.findByText('27 sept, 04:30')
    expect(cell.closest('tr')).toHaveTextContent(conversationItem(0).queue)
  })

  it('el detalle muestra la hora en la zona configurada', async () => {
    signedInAs(USERS.admin, {
      ...detailRoutes, ...publicRoute(),
      [`GET /api/conversations/${DETAIL_ID}`]: () => ({ status: 200, body: { ...conversationDetailFixture, started_at: LATE } }),
    })
    renderApp(`/conversaciones/${DETAIL_ID}`)
    expect(await screen.findByText(/27 de septiembre de 2026/)).toBeInTheDocument()
  })

  it('los resultados de búsqueda muestran la hora en la zona configurada', async () => {
    const response = searchResponse(1)
    response.results[0].conversation.started_at = LATE
    signedInAs(USERS.admin, {
      ...publicRoute(), 'GET /api/search/semantic': () => ({ status: 200, body: response }),
      'GET /api/catalog': () => ({ status: 200, body: catalogFixture }),
    })
    renderApp('/busqueda?q=cargo')
    expect(await screen.findByText(/27 sept 2026, 4:30|27 sept 2026, 04:30/)).toBeInTheDocument()
  })
})

describe('Nombre de la plataforma', () => {
  it('aparece en la cabecera', async () => {
    signedInAs(USERS.viewer, { ...metricsRoutes, ...publicRoute() })
    renderApp('/dashboards/vision-general')
    const aside = (await screen.findByRole('navigation', { name: /principal/i })).closest('aside')!
    await waitFor(() => expect(aside).toHaveTextContent('Analítica Horizonte'))
  })

  it('aparece en el login', async () => {
    sessionStorage.clear()
    signedInAs(USERS.viewer, publicRoute())
    sessionStorage.clear()
    renderApp('/login')
    expect(await screen.findByRole('heading', { name: 'Analítica Horizonte' })).toBeInTheDocument()
  })
})

describe('KPIs según la configuración', () => {
  function summaryWith(statuses: Record<string, string | null>, codes?: string[]) {
    return {
      ...summaryFixture,
      kpis: summaryFixture.kpis
        .filter((k) => !codes || codes.includes(k.code))
        .map((k) => ({ ...k, target: k.code === 'resolution_rate' ? 75 : null, status: statuses[k.code] ?? null })),
    }
  }

  it('las tarjetas muestran su estado y el objetivo, y el dashboard pide solo sus KPIs', async () => {
    const requests: string[] = []
    signedInAs(USERS.viewer, {
      ...metricsRoutes,
      'GET /api/metrics/summary': ({ url }) => {
        const dashboard = new URL(url, 'http://localhost').searchParams.get('dashboard')
        requests.push(dashboard ?? '')
        return { status: 200, body: dashboard
          ? summaryWith({ resolution_rate: 'ambar', aht_s: 'verde' }, ['volume', 'resolution_rate', 'aht_s', 'churn_high_pct'])
          : summaryWith({}) }
      },
    })
    renderApp('/dashboards/vision-general')
    const tile = await screen.findByRole('group', { name: 'Tasa de resolución' })
    expect(tile).toHaveAttribute('data-status', 'ambar')
    expect(tile).toHaveTextContent(/ámbar/i)
    expect(tile).toHaveTextContent(/objetivo: 75,0 %/i)
    expect(screen.getByRole('group', { name: 'Duración media (AHT)' })).toHaveAttribute('data-status', 'verde')
    expect(screen.getByRole('group', { name: 'Volumen' })).not.toHaveAttribute('data-status')
    expect(requests).toContain('vision-general')
    // Un KPI oculto no aparece; uno añadido en Configuración, sí (al final de la fila).
    const row = tile.parentElement!
    const labels = within(row).getAllByRole('group').map((g) => g.getAttribute('aria-label'))
    expect(labels).toEqual(['Volumen', 'Duración media (AHT)', 'Tasa de resolución', 'Riesgo de abandono alto'])
  })
})

describe('Taxonomía y modelo por defecto', () => {
  it('un main topic desactivado no se ofrece en el filtro del dashboard', async () => {
    signedInAs(USERS.viewer, {
      ...metricsRoutes,
      'GET /api/catalog': () => ({ status: 200, body: { ...catalogFixture, main_topics: [
        { code: 'cargo_no_reconocido', name: 'Cargo no reconocido', active: true },
        { code: 'cajeros', name: 'Incidencia en cajero', active: false },
        { code: 'criptoactivos', name: 'Criptoactivos', active: true },
      ] } }),
    })
    renderApp('/dashboards/vision-general')
    await userEvent.click(await screen.findByRole('button', { name: /main topic/i }))
    expect(await screen.findByRole('checkbox', { name: 'Criptoactivos' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Incidencia en cajero' })).not.toBeInTheDocument()
  })

  it('un nodo Prompt nuevo toma el modelo por defecto', async () => {
    setupEditor({ catalog: { default_model: 'mock-preciso' } })
    await userEvent.click(await screen.findByRole('button', { name: 'Añadir Prompt' }))
    expect(await screen.findByLabelText('Modelo')).toHaveValue('mock-preciso')
  })
})

describe('Propagación sin recargar', () => {
  it('un main topic creado en Configuración aparece en el filtro del dashboard, aunque el catálogo estuviera en caché', async () => {
    const { platformConfig, TAXONOMY } = await import('../test/configFixtures')
    let topics = catalogFixture.main_topics.map((t) => ({ ...t, active: true }))
    signedInAs(USERS.admin, {
      ...metricsRoutes,
      'GET /api/catalog': () => ({ status: 200, body: { ...catalogFixture, main_topics: topics } }),
      'GET /api/config': () => ({ status: 200, body: platformConfig() }),
      'GET /api/config/audit': () => ({ status: 200, body: { items: [] } }),
      'GET /api/config/taxonomy': () => ({ status: 200, body: TAXONOMY }),
      'POST /api/config/taxonomy/main-topics': (init) => {
        const body = JSON.parse(String(init.body))
        topics = [...topics, { code: body.code, name: body.name, active: true }]
        return { status: 201, body: { ...body, id: 'x', conversations: 0 } }
      },
    })
    const { router } = renderApp('/dashboards/vision-general')
    await userEvent.click(await screen.findByRole('button', { name: /main topic/i }))
    expect(await screen.findByRole('checkbox', { name: 'Cargo no reconocido' })).toBeInTheDocument()

    await router.navigate('/configuracion?tab=taxonomia')
    const panel = await screen.findByRole('tabpanel')
    await userEvent.click(await within(panel).findByRole('button', { name: 'Nuevo main topic' }))
    const form = within(panel).getByRole('form', { name: 'Nuevo main topic' })
    await userEvent.type(within(form).getByLabelText('Código'), 'criptoactivos')
    await userEvent.type(within(form).getByLabelText('Nombre'), 'Criptoactivos')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(within(panel).queryByRole('form')).not.toBeInTheDocument())

    await router.navigate('/dashboards/vision-general')
    await screen.findByRole('group', { name: 'Volumen' })  // el dashboard se carga en diferido
    await userEvent.click(screen.getByRole('button', { name: /main topic/i }))
    expect(await screen.findByRole('checkbox', { name: 'Criptoactivos' })).toBeInTheDocument()
  })
})

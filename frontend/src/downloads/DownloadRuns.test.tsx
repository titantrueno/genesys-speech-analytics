import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { COUNTERS, downloadFlow, downloadRun } from '../test/downloadFixtures'
import { fakeId } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from '../auth/types'
import type { DownloadRun, LogEntry } from './types'

const FLOW = downloadFlow(1, { name: 'Descarga del día' })
const RUN = downloadRun(1)
const BASE = `/api/download-flows/${FLOW.id}`

function entry(id: number, level: LogEntry['level'], message: string): LogEntry {
  return { id, at: '2026-10-12T11:32:05+00:00', level, stage: level === 'info' ? 'búsqueda' : 'normalización', message,
    genesys_id: level === 'info' ? null : '687f2225-6f3b-4446-bfd3-f5d2b3416814' }
}
const LOG = [entry(1, 'info', '13 encontradas, 13 por descargar, 0 omitidas'),
  entry(2, 'aviso', 'Transcripción parcial: intervino agente y bot sin frases'),
  entry(3, 'info', '13 insertadas, 0 actualizadas')]

type Call = { method: string; path: string; query?: string }

function setup(options: {
  user?: User; path?: string; runs?: DownloadRun[]; runSequence?: DownloadRun[]; startStatus?: number
} = {}) {
  const calls: Call[] = []
  const sequence = [...(options.runSequence ?? [RUN])]
  const track = (method: string, init: { url: string }) => {
    const url = new URL(init.url, 'http://localhost')
    calls.push({ method, path: url.pathname, query: url.search })
    return url
  }
  signedInAs(options.user ?? USERS.analista, {
    'GET /api/flows': () => ({ status: 200, body: { items: [] } }),
    'GET /api/download-flows': () => ({ status: 200, body: { items: [FLOW] } }),
    [`GET ${BASE}`]: () => ({ status: 200, body: FLOW }),
    [`GET ${BASE}/runs`]: () => ({ status: 200, body: { items: options.runs ?? [RUN] } }),
    [`POST ${BASE}/runs`]: (init) => {
      track('POST', init)
      return options.startStatus
        ? { status: options.startStatus, body: { detail: 'Ya hay una ejecución en curso de este flujo' } }
        : { status: 202, body: downloadRun(1, { status: 'pendiente' }) }
    },
    [`GET ${BASE}/runs/${RUN.id}`]: (init) => {
      track('GET', init)
      return { status: 200, body: sequence.length > 1 ? sequence.shift() : sequence[0] }
    },
    [`GET ${BASE}/runs/${RUN.id}/log`]: (init) => {
      const url = track('GET', init)
      if (url.searchParams.get('format') === 'text') return { status: 200, body: 'log' }
      const after = Number(url.searchParams.get('after') ?? 0)
      const level = url.searchParams.get('level')
      return { status: 200, body: { items: LOG.filter((e) => e.id > after && (!level || e.level === level)) } }
    },
  })
  return { ...renderApp(options.path ?? `/flujos/descargas/${FLOW.id}`), calls }
}

describe('Flujos de descarga: ejecutar y su historial', () => {
  it('«Ejecutar ahora» lanza la descarga y abre su ejecución', async () => {
    const { calls, router } = setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Ejecutar ahora' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/descargas/${FLOW.id}/ejecuciones/${RUN.id}`))
    expect(calls[0]).toMatchObject({ method: 'POST', path: `${BASE}/runs` })
  })

  it('si ya hay una descarga en curso lo explica', async () => {
    setup({ startStatus: 409 })
    await userEvent.click(await screen.findByRole('button', { name: 'Ejecutar ahora' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ya hay una descarga en curso')
  })

  it('el historial muestra cada ejecución y la abre al pulsar su fila', async () => {
    const scheduled = downloadRun(2, { id: fakeId('1RN', 102), origin: 'programada', started_by: null, status: 'error',
      error: 'Credenciales de Genesys no válidas', counters: { ...COUNTERS, found: 0, inserted: 0, downloaded: 0 } })
    const { router } = setup({ runs: [RUN, scheduled] })
    const history = await screen.findByRole('region', { name: 'Historial de descargas' })
    const rows = await within(history).findAllByRole('row')
    expect(rows).toHaveLength(3)
    expect(rows[1]).toHaveTextContent('Manual')
    expect(rows[1]).toHaveTextContent('Admin Demo')
    expect(rows[1]).toHaveTextContent('13 insertadas')
    expect(rows[1]).toHaveTextContent('Con avisos')
    expect(rows[2]).toHaveTextContent('Programada')
    expect(rows[2]).toHaveTextContent('Error')
    await userEvent.click(within(rows[1]).getByText(/^Manual/))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/descargas/${FLOW.id}/ejecuciones/${RUN.id}`))
  })

  it('sin flows:edit se ve el historial, pero no se puede ejecutar', async () => {
    setup({ user: USERS.lector })
    await screen.findByRole('region', { name: 'Historial de descargas' })
    expect(screen.queryByRole('button', { name: 'Ejecutar ahora' })).not.toBeInTheDocument()
  })
})

describe('Flujos de descarga: ejecución y log', () => {
  const path = `/flujos/descargas/${FLOW.id}/ejecuciones/${RUN.id}`

  it('sigue el progreso por polling hasta que termina y después deja de consultar', async () => {
    const running = downloadRun(1, { status: 'en_curso', finished_at: null, duration_s: null,
      counters: { ...COUNTERS, downloaded: 5, inserted: 5 } })
    const { calls } = setup({ path, runSequence: [running, RUN] })
    expect(await screen.findByText('En curso')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Contadores' })).toHaveTextContent('5 de 13 descargadas')
    expect(await screen.findByText('Con avisos', {}, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Contadores' })).toHaveTextContent('13 de 13 descargadas')
    const polls = () => calls.filter((c) => c.path === `${BASE}/runs/${RUN.id}`).length
    const settled = polls()
    await new Promise((resolve) => setTimeout(resolve, 2500))
    expect(polls()).toBe(settled)
  }, 12_000)

  it('carga el log por tramos con `after` y lo filtra por nivel', async () => {
    const running = downloadRun(1, { status: 'en_curso', finished_at: null, duration_s: null })
    const { calls } = setup({ path, runSequence: [running, running, running, RUN] })
    const log = await screen.findByRole('region', { name: 'Log' })
    const afters = () => calls.filter((c) => c.path.endsWith('/log')).map((c) => new URLSearchParams(c.query).get('after'))
    // Tres lecturas: la respuesta (vacía) de la segunda ya se ha aplicado cuando sale la tercera.
    await waitFor(() => expect(afters().length).toBeGreaterThanOrEqual(3), { timeout: 8000 })
    expect(afters()[0]).toBe('0')
    expect(afters().slice(1).every((after) => after === '3')).toBe(true)  // solo pide lo nuevo
    expect(within(log).getAllByRole('row')).toHaveLength(4)  // sin duplicar ni perder entradas
    expect(within(log).getAllByRole('row')[2]).toHaveTextContent('687f2225')
    await userEvent.selectOptions(within(log).getByLabelText('Nivel'), 'aviso')
    await waitFor(() => expect(within(log).getAllByRole('row')).toHaveLength(2))
    expect(within(log).getAllByRole('row')[1]).toHaveTextContent('Transcripción parcial')
  }, 15_000)

  it('al terminar recoge las últimas entradas del log', async () => {
    let finished = false
    const running = downloadRun(1, { status: 'en_curso', finished_at: null, duration_s: null })
    signedInAs(USERS.analista, {
      [`GET ${BASE}`]: () => ({ status: 200, body: FLOW }),
      [`GET ${BASE}/runs/${RUN.id}`]: () => {
        const body = finished ? RUN : running
        finished = true  // la segunda consulta ya la ve terminada
        return { status: 200, body }
      },
      [`GET ${BASE}/runs/${RUN.id}/log`]: (init) => {
        const after = Number(new URL(init.url, 'http://localhost').searchParams.get('after') ?? 0)
        // La entrada final solo existe cuando la ejecución ha terminado.
        return { status: 200, body: { items: LOG.filter((e) => e.id > after && (e.id < 3 || finished)) } }
      },
    })
    renderApp(path)
    const log = await screen.findByRole('region', { name: 'Log' })
    expect(await within(log).findByText('13 insertadas, 0 actualizadas', {}, { timeout: 6000 })).toBeInTheDocument()
  }, 12_000)

  it('descarga el log en texto', async () => {
    const createObjectURL = vi.fn(() => 'blob:log')
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }))
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const { calls } = setup({ path })
    await userEvent.click(await screen.findByRole('button', { name: 'Descargar log' }))
    await waitFor(() => expect(click).toHaveBeenCalled())
    expect(calls.some((c) => c.path.endsWith('/log') && c.query === '?format=text')).toBe(true)
    expect((click.mock.contexts[0] as HTMLAnchorElement).download).toBe(`log-${RUN.id}.txt`)
  })

  it('muestra el error de una ejecución fallida', async () => {
    setup({ path, runSequence: [downloadRun(1, { status: 'error', error: 'Credenciales de Genesys no válidas' })] })
    expect(await screen.findByRole('alert')).toHaveTextContent('Credenciales de Genesys no válidas')
  })
})

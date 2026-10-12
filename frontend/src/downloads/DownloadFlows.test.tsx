import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { downloadFlow } from '../test/downloadFixtures'
import { fakeId } from '../test/fixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from '../auth/types'
import type { FlowSummary } from '../flows/types'
import type { DownloadFlow } from './types'

const INSIGHTS: FlowSummary = {
  id: fakeId('1FL', 1), name: 'Motivos de fraude', author: { id: fakeId('1US', 3), name: 'Analista Demo' },
  created_at: '2026-10-01T08:00:00+00:00', updated_at: '2026-10-10T10:30:00+00:00', status: 'valido', last_run: null,
}
const SCHEDULED = downloadFlow(1, {
  name: 'Descarga cada 6 horas', schedule: { type: 'cada_horas', hours: 6 }, next_run_at: '2026-10-12T16:00:00+00:00',
  last_run: { id: fakeId('1RN', 101), status: 'completada_con_avisos', created_at: '2026-10-12T10:00:00+00:00' },
})

type Call = { method: string; path: string; body?: unknown }
type Reply = { status: number; body?: unknown }

function setup(options: {
  user?: User; downloads?: DownloadFlow[]; downloadsStatus?: number; path?: string
  save?: (body: Record<string, unknown>) => Reply
} = {}) {
  let downloads = [...(options.downloads ?? [SCHEDULED])]
  const calls: Call[] = []
  const record = (method: string, path: string, init: RequestInit) => {
    const body = init.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    return body
  }
  const routes: Record<string, (init: RequestInit & { url: string }) => Reply> = {
    'GET /api/flows': () => ({ status: 200, body: { items: [INSIGHTS] } }),
    'POST /api/flows': (init) => {
      record('POST', '/api/flows', init)
      return { status: 201, body: { ...INSIGHTS, id: fakeId('1FL', 50), graph: { version: 1, nodes: [], edges: [] } } }
    },
    [`GET /api/flows/${fakeId('1FL', 50)}`]: () => ({ status: 404, body: { detail: 'No existe' } }),
    'GET /api/flows/catalog': () => ({ status: 404 }),
    'GET /api/download-flows': () => (options.downloadsStatus
      ? { status: options.downloadsStatus, body: { detail: 'El servicio de ingesta no está disponible' } }
      : { status: 200, body: { items: downloads } }),
    'POST /api/download-flows': (init) => {
      const body = record('POST', '/api/download-flows', init)
      const created = downloadFlow(9, { ...body, id: fakeId('1FL', 109) })
      downloads = [created, ...downloads]
      return { status: 201, body: created }
    },
  }
  for (const n of [1, 9]) {
    const id = fakeId('1FL', 100 + n)
    routes[`GET /api/download-flows/${id}`] = () => ({ status: 200, body: downloads.find((d) => d.id === id) })
    routes[`PUT /api/download-flows/${id}`] = (init) => {
      const body = record('PUT', id, init)
      if (options.save) return options.save(body)
      downloads = downloads.map((d) => (d.id === id ? { ...d, ...body } : d))
      return { status: 200, body: downloads.find((d) => d.id === id) }
    }
    routes[`DELETE /api/download-flows/${id}`] = (init) => {
      record('DELETE', id, init)
      downloads = downloads.filter((d) => d.id !== id)
      return { status: 204 }
    }
    routes[`GET /api/download-flows/${id}/runs`] = () => ({ status: 200, body: { items: [] } })
  }
  signedInAs(options.user ?? USERS.analista, routes)
  return { ...renderApp(options.path ?? '/flujos'), calls }
}

async function rowOf(name: string) {
  return (await screen.findByRole('link', { name })).closest('tr')!
}

describe('Flujos: listado con flujos de descarga', () => {
  it('muestra los dos tipos con su columna «Tipo» y la próxima ejecución de las descargas', async () => {
    setup()
    const download = await rowOf('Descarga cada 6 horas')
    expect(download).toHaveTextContent('Descarga de transcripciones')
    expect(download).toHaveTextContent('Cada 6 horas')
    expect(download).toHaveTextContent('12 oct, 16:00')  // próxima ejecución (sin configuración pública, en UTC)
    expect(download).toHaveTextContent('Con avisos')
    expect(within(download).getByRole('link', { name: 'Descarga cada 6 horas' })).toHaveAttribute(
      'href', `/flujos/descargas/${SCHEDULED.id}`)
    const insights = await rowOf('Motivos de fraude')
    expect(insights).toHaveTextContent('Insights')
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(
      ['Nombre', 'Tipo', 'Autor', 'Última modificación', 'Última ejecución', 'Próxima ejecución', 'Estado', 'Acciones'])
  })

  it('si el servicio de ingesta no responde, avisa y sigue mostrando los flujos de insights', async () => {
    setup({ downloadsStatus: 503 })
    expect(await screen.findByRole('link', { name: 'Motivos de fraude' })).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(/descargas de Genesys no están disponibles/i)
    expect(screen.queryByText('Descarga cada 6 horas')).not.toBeInTheDocument()
  })

  it('crea un flujo de insights o uno de descarga eligiendo el tipo', async () => {
    const { calls, router } = setup()
    await userEvent.click(await screen.findByRole('button', { name: /nuevo flujo/i }))
    await userEvent.type(screen.getByLabelText('Nombre del flujo'), 'Descarga de ayer')
    await userEvent.click(screen.getByRole('radio', { name: 'Descarga de transcripciones' }))
    await userEvent.click(screen.getByRole('button', { name: 'Crear' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/flujos/descargas/${fakeId('1FL', 109)}`))
    expect(calls).toEqual([{ method: 'POST', path: '/api/download-flows', body: {
      name: 'Descarga de ayer', interval: { type: 'relativo', unit: 'hoy' }, channels: ['voz', 'chat'],
      schedule: { type: 'desactivada' }, active: true, overwrite: false } }])

    await router.navigate('/flujos')
    await userEvent.click(await screen.findByRole('button', { name: /nuevo flujo/i }))
    expect(screen.getByRole('radio', { name: 'Insights' })).toBeChecked()
    await userEvent.type(screen.getByLabelText('Nombre del flujo'), 'Quejas')
    await userEvent.click(screen.getByRole('button', { name: 'Crear' }))
    await waitFor(() => expect(calls.at(-1)).toEqual({ method: 'POST', path: '/api/flows', body: { name: 'Quejas' } }))
  })

  it('borra un flujo de descarga tras confirmar', async () => {
    const { calls } = setup()
    const row = await rowOf('Descarga cada 6 horas')
    await userEvent.click(within(row).getByRole('button', { name: /borrar/i }))
    await userEvent.click(within(row).getByRole('button', { name: /confirmar borrado/i }))
    await waitFor(() => expect(screen.queryByText('Descarga cada 6 horas')).not.toBeInTheDocument())
    expect(calls).toEqual([{ method: 'DELETE', path: SCHEDULED.id, body: undefined }])
    expect(within(await rowOf('Motivos de fraude')).queryByRole('button', { name: /renombrar/i })).toBeInTheDocument()
  })
})

describe('Flujos de descarga: formulario', () => {
  const path = `/flujos/descargas/${SCHEDULED.id}`

  it('guarda el intervalo, los canales y la programación sin enviar zona horaria ni autoría', async () => {
    const { calls } = setup({ path })
    const name = await screen.findByLabelText('Nombre')
    expect(name).toHaveValue('Descarga cada 6 horas')
    expect(screen.getByText(/zona horaria de la plataforma/i)).toHaveTextContent('Europe/Madrid')
    await userEvent.clear(name)
    await userEvent.type(name, 'Últimas 12 horas')
    await userEvent.selectOptions(screen.getByLabelText('Periodo'), 'horas')
    await userEvent.clear(screen.getByLabelText('Cantidad'))
    await userEvent.type(screen.getByLabelText('Cantidad'), '12')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Chat' }))
    await userEvent.selectOptions(screen.getByLabelText('Programación'), 'diaria')
    await userEvent.type(screen.getByLabelText('Hora'), '07:30')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toEqual([{ method: 'PUT', path: SCHEDULED.id, body: {
      name: 'Últimas 12 horas', interval: { type: 'relativo', unit: 'horas', amount: 12 }, channels: ['voz'],
      schedule: { type: 'diaria', time: '07:30' }, active: true, overwrite: false } }]))
    expect(await screen.findByRole('status')).toHaveTextContent(/cambios guardados/i)
  })

  it('desmarcar y volver a marcar un canal no cuenta como cambio', async () => {
    setup({ path })
    await screen.findByLabelText('Nombre')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Voz' }))
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeEnabled()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Voz' }))
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeDisabled()
  })

  it('un intervalo específico se envía en hora local, y con programación se rechaza antes de enviar', async () => {
    const { calls } = setup({ path })
    await screen.findByLabelText('Nombre')
    await userEvent.click(screen.getByRole('radio', { name: 'Específico' }))
    expect(screen.getByLabelText('Programación')).toHaveValue('cada_horas')
    expect(screen.getByText('Una descarga programada necesita un intervalo relativo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeDisabled()
    await userEvent.selectOptions(screen.getByLabelText('Programación'), 'desactivada')
    // user-event no simula `datetime-local` (solo `date` y `time`): el cambio equivale a elegir en el selector.
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-10-01T08:00' } })
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-10-02T20:30' } })
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].body).toMatchObject({ interval: { type: 'especifico', from: '2026-10-01T08:00', to: '2026-10-02T20:30' },
      schedule: { type: 'desactivada' } })
  })

  it('un 422 muestra el error junto a su campo y conserva lo escrito', async () => {
    setup({ path, save: () => ({ status: 422, body: { detail: [
      { loc: ['body', 'interval', 'relativo'], msg: 'La cantidad de horas debe estar entre 1 y 720', type: 'value_error' },
      { loc: ['body', 'name'], msg: 'El nombre no puede estar vacío', type: 'value_error' },
    ] } }) })
    await screen.findByLabelText('Nombre')
    await userEvent.selectOptions(screen.getByLabelText('Periodo'), 'horas')
    await userEvent.clear(screen.getByLabelText('Cantidad'))
    await userEvent.type(screen.getByLabelText('Cantidad'), '900')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByText('La cantidad de horas debe estar entre 1 y 720')).toBeInTheDocument()
    expect(screen.getByLabelText('Cantidad')).toHaveValue(900)
    expect(screen.getByLabelText('Cantidad')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Nombre')).toHaveAccessibleDescription('El nombre no puede estar vacío')
  })

  it('«Sobrescribir» aparece desmarcado, explica que borra lo del LLM y se envía al guardar', async () => {
    const { calls } = setup({ path })
    const overwrite = await screen.findByRole('checkbox', { name: /sobrescribir/i })
    expect(overwrite).not.toBeChecked()
    expect(screen.getByText(/vuelve a descargar las conversaciones que ya existen y borra su summary y main topic/i))
      .toBeInTheDocument()
    await userEvent.click(overwrite)
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toEqual([{ method: 'PUT', path: SCHEDULED.id, body: expect.objectContaining({
      overwrite: true }) }]))
  })

  it('sin flows:edit el formulario es de solo lectura y el listado no tiene acciones', async () => {
    setup({ user: USERS.lector, path })
    expect(await screen.findByLabelText('Nombre')).toBeDisabled()
    expect(screen.getByLabelText('Periodo')).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: /sobrescribir/i })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument()
  })
})

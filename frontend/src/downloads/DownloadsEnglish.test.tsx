import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { downloadFlow, downloadRun } from '../test/downloadFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { LogEntry } from './types'

const english = { 'GET /api/config/public': () => ({ status: 200, body: { platform_name: 'Speech & Text Analytics', timezone: 'UTC', language: 'en-US' } }) }
const FLOW = downloadFlow(1, {
  name: 'Descarga del día', schedule: { type: 'diaria', time: '08:00' }, next_run_at: '2026-10-13T08:00:00+00:00',
  interval: { type: 'relativo', unit: 'dias', amount: 3 },
})
const RUN = downloadRun(1)
const BASE = `/api/download-flows/${FLOW.id}`
const LOG: LogEntry[] = [
  { id: 1, at: '2026-10-12T11:32:05+00:00', level: 'info', stage: 'búsqueda', message: '13 encontradas, 13 por descargar, 0 omitidas', genesys_id: null },
  { id: 2, at: '2026-10-12T11:32:06+00:00', level: 'aviso', stage: 'normalización', message: 'Transcripción parcial: intervino agente y bot sin frases', genesys_id: '687f2225-6f3b-4446-bfd3-f5d2b3416814' },
]

function setup(path: string) {
  signedInAs(USERS.analista, {
    ...english,
    'GET /api/flows': () => ({ status: 200, body: { items: [] } }),
    'GET /api/download-flows': () => ({ status: 200, body: { items: [FLOW] } }),
    [`GET ${BASE}`]: () => ({ status: 200, body: FLOW }),
    [`GET ${BASE}/runs`]: () => ({ status: 200, body: { items: [RUN] } }),
    [`GET ${BASE}/runs/${RUN.id}`]: () => ({ status: 200, body: RUN }),
    [`GET ${BASE}/runs/${RUN.id}/log`]: () => ({ status: 200, body: { items: LOG } }),
  })
  return renderApp(path)
}

describe('Descargas de Genesys con la interfaz en inglés (FE016, T6)', () => {
  it('flujo de descarga: formulario, programación e historial en inglés; el nombre del flujo no cambia', async () => {
    setup(`/flujos/descargas/${FLOW.id}`)
    expect(await screen.findByRole('heading', { name: 'Descarga del día' })).toBeInTheDocument()
    expect(screen.getByText(/Genesys Cloud transcript download · Daily at 08:00 · next run:/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run now' })).toBeInTheDocument()

    const config = screen.getByRole('region', { name: 'Download configuration' })
    for (const label of ['Name', 'Interval', 'Channels', 'Schedule']) expect(within(config).getByText(label)).toBeInTheDocument()
    expect(within(config).getByText('Relative')).toBeInTheDocument()
    expect(within(config).getByRole('option', { name: 'Last days' })).toBeInTheDocument()
    expect(within(config).getByText('1 to 90 days.')).toBeInTheDocument()
    expect(within(config).getByText('Voice')).toBeInTheDocument()
    expect(within(config).getByRole('option', { name: 'Daily' })).toBeInTheDocument()
    expect(within(config).getByText('Overwrite')).toBeInTheDocument()
    expect(within(config).getByText(/the platform time zone \(Europe\/Madrid\)/)).toBeInTheDocument()

    const history = await screen.findByRole('region', { name: 'Download history' })
    expect(within(history).getByText('Manual · Admin Demo')).toBeInTheDocument()
    expect(within(history).getByText('13 inserted · 0 updated')).toBeInTheDocument()
    expect(within(history).getByText('With warnings')).toBeInTheDocument()
    for (const column of ['Date', 'Origin', 'Interval', 'Conversations', 'Duration', 'Status']) {
      expect(within(history).getByRole('columnheader', { name: column })).toBeInTheDocument()
    }
  })

  it('ejecución: contadores, estado y log en inglés; los mensajes y etapas del log llegan tal cual', async () => {
    setup(`/flujos/descargas/${FLOW.id}/ejecuciones/${RUN.id}`)
    expect(await screen.findByRole('heading', { name: /^Download / })).toBeInTheDocument()
    expect(screen.getByText(/Descarga del día · Manual · started by Admin Demo · interval .* · Voice and Chat · skips the conversations that already exist/)).toBeInTheDocument()

    const counters = screen.getByRole('region', { name: 'Counters' })
    expect(within(counters).getByText('13 of 13 downloaded')).toBeInTheDocument()
    expect(within(counters).getByText('13 inserted · 0 updated')).toBeInTheDocument()
    expect(within(counters).getByText('Voice 7 · Chat 6')).toBeInTheDocument()
    expect(within(counters).getByText('Complete 9 · Partial 2 · No transcript 2')).toBeInTheDocument()
    expect(within(counters).getByText('Undelivered messages')).toBeInTheDocument()

    const log = await screen.findByRole('region', { name: 'Log' })
    expect(within(log).getByLabelText('Level')).toBeInTheDocument()
    expect(within(log).getByRole('option', { name: 'Warning' })).toBeInTheDocument()
    expect(within(log).getByRole('button', { name: 'Download log' })).toBeInTheDocument()
    expect(await within(log).findByText('Transcripción parcial: intervino agente y bot sin frases')).toBeInTheDocument()
    expect(within(log).getByText('normalización')).toBeInTheDocument()
  })
})

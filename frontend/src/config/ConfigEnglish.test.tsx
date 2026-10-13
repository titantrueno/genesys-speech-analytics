import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fakeId } from '../test/fixtures'
import { AI_STATUS, auditEntry, CHECKS, CONNECTORS, platformConfig, TAXONOMY } from '../test/configFixtures'
import { openApiDoc } from '../test/openapiFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { GenesysConnector } from '../downloads/types'

const english = { 'GET /api/config/public': () => ({ status: 200, body: { platform_name: 'Speech & Text Analytics', timezone: 'UTC', language: 'en-US' } }) }
const GENESYS: GenesysConnector = {
  service: 'disponible', region: 'eu-west-1', credentials_configured: true, database: 'ok',
  last_test: { ok: true, at: '2026-10-12T11:51:25+00:00', organization: 'SGTO', region: 'eu-west-1', message: 'ok' },
  last_download: { run_id: fakeId('1RN', 1), flow_id: fakeId('1FL', 1), status: 'completada_con_avisos', finished_at: '2026-10-12T11:32:14+00:00' },
  conversations: { total: 13, by_channel: { voz: 7, chat: 6 }, by_quality: { completa: 9, parcial: 2, sin_transcripcion: 2 } },
}

function setup(tab: string) {
  signedInAs(USERS.admin, {
    ...english,
    'GET /api/config': () => ({ status: 200, body: platformConfig() }),
    'GET /api/config/audit': () => ({ status: 200, body: { items: [auditEntry(1, { before: { pii_masking: false }, after: { pii_masking: true } })] } }),
    'GET /api/config/connectors': () => ({ status: 200, body: { items: CONNECTORS } }),
    'GET /api/config/connectors/genesys': () => ({ status: 200, body: GENESYS }),
    'GET /api/config/ai/status': () => ({ status: 200, body: AI_STATUS }),
    'GET /api/config/taxonomy': () => ({ status: 200, body: TAXONOMY }),
    'GET /api/config/compliance-checks': () => ({ status: 200, body: { items: CHECKS } }),
    'GET /openapi.json': () => ({ status: 200, body: openApiDoc() }),
  })
  return renderApp(`/configuracion?tab=${tab}`)
}

describe('Configuración con la interfaz en inglés (FE016, T7)', () => {
  it('estructura: título, pestañas y registro de cambios en inglés', async () => {
    setup('privacidad')
    expect(await screen.findByRole('heading', { level: 1, name: 'Settings' })).toBeInTheDocument()
    const tabs = within(await screen.findByRole('tablist', { name: 'Settings sections' })).getAllByRole('tab').map((t) => t.textContent)
    expect(tabs).toEqual(['General', 'Data sources', 'Taxonomy', 'KPIs and targets', 'Compliance', 'Privacy', 'AI models', 'API'])
    expect(screen.getByText('Mask personal data')).toBeInTheDocument()
    const log = await screen.findByRole('region', { name: 'Change log' })
    for (const column of ['When', 'Who', 'Element', 'Before', 'After']) expect(within(log).getByRole('columnheader', { name: column })).toBeInTheDocument()
    expect(within(log).getByText('pii_masking: no')).toBeInTheDocument()
    expect(within(log).getByText('pii_masking: yes')).toBeInTheDocument()
  })

  it('General: el idioma se llama «Interface language» y ofrece los dos idiomas con su propio nombre', async () => {
    setup('general')
    const language = await screen.findByLabelText('Interface language')
    expect(within(language).getByRole('option', { name: 'Español (España)' })).toBeInTheDocument()
    expect(within(language).getByRole('option', { name: 'English (United States)' })).toBeInTheDocument()
    for (const label of ['Platform name', 'Time zone']) expect(screen.getByLabelText(label)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
  })

  it('Fuentes de datos: origen, conectores y Genesys en inglés', async () => {
    setup('fuentes')
    const origin = await screen.findByRole('region', { name: 'Data origin' })
    expect(within(origin).getByText('Synthetic')).toBeInTheDocument()
    expect(within(origin).getByText('Real (Genesys Cloud)')).toBeInTheDocument()
    await userEvent.click(within(origin).getByRole('radio', { name: /Real \(Genesys Cloud\)/ }))
    expect(await screen.findByRole('alertdialog', { name: 'Confirm origin change' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm change' })).toBeInTheDocument()

    const connectors = await screen.findByRole('region', { name: 'Data sources' })
    expect(within(connectors).getAllByText('Connected').length).toBe(2)
    expect(within(connectors).getByRole('button', { name: 'Sync Genesys Cloud · voz transcrita' })).toBeInTheDocument()

    const genesys = await screen.findByRole('region', { name: 'Genesys Cloud · real data' })
    expect(await within(genesys).findByText('Available')).toBeInTheDocument()
    expect(within(genesys).getByText('Voice 7 · Chat 6')).toBeInTheDocument()
    expect(within(genesys).getByText('Complete 9 · Partial 2 · No transcript 2')).toBeInTheDocument()
    expect(within(genesys).getByText('With warnings')).toBeInTheDocument()
    expect(within(genesys).getByRole('button', { name: 'Test connection' })).toBeInTheDocument()
  })

  it('Taxonomía y Cumplimiento: textos en inglés; los nombres de temas y checks son datos', async () => {
    setup('taxonomia')
    const main = await screen.findByRole('table', { name: 'Main topics' })
    expect(within(main).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(
      ['Code', 'Name', 'Keywords', 'Conversations', 'Status', 'Actions'])
    expect(within(main).getByText('Incidencia en cajero')).toBeInTheDocument()
    expect(within(main).getByText('Dinero no entregado.')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Secondary topics' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New main topic' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'New secondary topic' }))
    expect(await screen.findByRole('form', { name: 'New secondary topic' })).toBeInTheDocument()
  })

  it('Cumplimiento: checks, evaluación y canal en inglés', async () => {
    setup('cumplimiento')
    const table = await screen.findByRole('table', { name: 'Compliance checks' })
    expect(within(table).getByText('Analysis result')).toBeInTheDocument()
    expect(within(table).getByText('By agent phrases')).toBeInTheDocument()
    expect(within(table).getByText('Voice and chat')).toBeInTheDocument()
    expect(within(table).getByText('Saludo e identificación del agente')).toBeInTheDocument()
    expect(within(table).getByText('valore la atención · encuesta')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'New check' }))
    const form = await screen.findByRole('form', { name: 'New check' })
    expect(within(form).getByLabelText('Expected phrases')).toBeInTheDocument()
  })

  it('KPIs y Modelos de IA: nombres de KPI, unidades, dashboards y proveedores en inglés', async () => {
    setup('kpis')
    const volume = await screen.findByRole('group', { name: 'Volume' })
    expect(within(volume).getByText(/Unit: conversations\./)).toBeInTheDocument()
    expect(within(volume).getByLabelText('Target')).toBeInTheDocument()
    expect(within(volume).getByText('Overview')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Average handling time (AHT)' })).toBeInTheDocument()
  })

  it('Modelos de IA: proveedor, estado del servicio y claves en inglés', async () => {
    setup('modelos')
    expect(await screen.findByLabelText('Provider')).toBeInTheDocument()
    const status = await screen.findByRole('region', { name: 'LLM service status' })
    expect(await within(status).findByText('Key configured')).toBeInTheDocument()
    expect(within(status).getByText('No key')).toBeInTheDocument()
    expect(within(status).getByText('No key needed')).toBeInTheDocument()
    expect(within(status).getByText('Simulated (no LLM)')).toBeInTheDocument()
    expect(within(status).getByRole('button', { name: 'Test Gemini (Google)' })).toBeInTheDocument()
  })

  it('API: buscador y resumen en inglés', async () => {
    setup('api')
    const api = await screen.findByRole('region', { name: 'API specification' })
    expect(within(api).getByLabelText('Search operations')).toBeInTheDocument()
    expect(within(api).getByLabelText('Domain')).toBeInTheDocument()
    expect(api.textContent).toMatch(/ · version .+ · \d+ operations/)
    expect(within(api).getByText(/Try it out/)).toBeInTheDocument()
  })
})

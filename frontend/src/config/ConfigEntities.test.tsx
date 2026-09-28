import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CHECKS, platformConfig, TAXONOMY } from '../test/configFixtures'
import { renderApp, signedInAs, USERS } from '../test/utils'
import type { User } from '../auth/types'

type Call = { method: string; path: string; body?: unknown }
type Reply = { status: number; body?: unknown }

function setup(options: { user?: User; tab: string; reply?: Record<string, (body: unknown) => Reply> }) {
  const calls: Call[] = []
  const handler = (method: string, path: string, fallback: (body: unknown) => Reply) => (init: RequestInit) => {
    const body = init.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    return (options.reply?.[`${method} ${path}`] ?? fallback)(body)
  }
  const ok = (status = 200) => (body: unknown) => ({ status, body })
  const routes: Record<string, (init: RequestInit) => Reply> = {
    'GET /api/config': () => ({ status: 200, body: platformConfig() }),
    'GET /api/config/audit': () => ({ status: 200, body: { items: [] } }),
    'GET /api/config/taxonomy': () => ({ status: 200, body: TAXONOMY }),
    'GET /api/config/compliance-checks': () => ({ status: 200, body: { items: CHECKS } }),
    'POST /api/config/taxonomy/main-topics': handler('POST', 'main-topics', ok(201)),
    'POST /api/config/taxonomy/secondary-topics': handler('POST', 'secondary-topics', ok(201)),
    'POST /api/config/compliance-checks': handler('POST', 'checks', ok(201)),
    'PUT /api/config/kpis/resolution_rate': handler('PUT', 'kpi resolution_rate', () => ({ status: 200, body: platformConfig() })),
  }
  for (const t of [...TAXONOMY.main_topics]) {
    routes[`PUT /api/config/taxonomy/main-topics/${t.id}`] = handler('PUT', t.code, ok())
    routes[`DELETE /api/config/taxonomy/main-topics/${t.id}`] = handler('DELETE', t.code, () => ({ status: 204 }))
  }
  for (const c of CHECKS) {
    routes[`PUT /api/config/compliance-checks/${c.id}`] = handler('PUT', c.code, ok())
    routes[`DELETE /api/config/compliance-checks/${c.id}`] = handler('DELETE', c.code, () => ({ status: 204 }))
  }
  signedInAs(options.user ?? USERS.admin, routes)
  renderApp(`/configuracion?tab=${options.tab}`)
  return { calls }
}

const panel = () => screen.findByRole('tabpanel')

describe('Configuración: Taxonomía', () => {
  it('lista main topics y temas secundarios con su uso y estado', async () => {
    setup({ tab: 'taxonomia' })
    const main = await within(await panel()).findByRole('table', { name: 'Main topics' })
    const rows = within(main).getAllByRole('row')
    expect(rows[1]).toHaveTextContent('cajeros')
    expect(rows[1]).toHaveTextContent('Incidencia en cajero')
    expect(rows[1]).toHaveTextContent('41')
    expect(rows[1]).toHaveTextContent('Activo')
    expect(within(await panel()).getByRole('table', { name: 'Temas secundarios' })).toHaveTextContent('compras online')
  })

  it('crea un main topic con palabras clave separadas por comas', async () => {
    const { calls } = setup({ tab: 'taxonomia' })
    const p = await panel()
    await userEvent.click(await within(p).findByRole('button', { name: 'Nuevo main topic' }))
    const form = within(p).getByRole('form', { name: 'Nuevo main topic' })
    await userEvent.type(within(form).getByLabelText('Código'), 'hipotecas_verdes')
    await userEvent.type(within(form).getByLabelText('Nombre'), 'Hipotecas verdes')
    await userEvent.type(within(form).getByLabelText('Palabras clave'), 'hipoteca verde, eficiencia ,')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toEqual([{ method: 'POST', path: 'main-topics', body: {
      code: 'hipotecas_verdes', name: 'Hipotecas verdes', description: '', keywords: ['hipoteca verde', 'eficiencia'], active: true,
    } }]))
  })

  it('al editar, el código no se puede cambiar y los errores salen junto al campo', async () => {
    setup({ tab: 'taxonomia', reply: { 'PUT cajeros': () => ({ status: 422, body: { detail: [
      { loc: ['body', 'name'], msg: 'Ya existe otro con ese nombre', type: 'value_error' }] } }) } })
    const p = await panel()
    const row = within(await within(p).findByRole('table', { name: 'Main topics' })).getAllByRole('row')[1]
    await userEvent.click(within(row).getByRole('button', { name: /editar/i }))
    const form = within(p).getByRole('form', { name: /editar main topic/i })
    expect(within(form).getByLabelText('Código')).toBeDisabled()
    const name = within(form).getByLabelText('Nombre')
    await userEvent.clear(name)
    await userEvent.type(name, 'Criptoactivos')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    expect(await within(form).findByText('Ya existe otro con ese nombre')).toBeInTheDocument()
    expect(name).toHaveValue('Criptoactivos')
  })

  it('un main topic en uso no ofrece Borrar y desactivar pide confirmación', async () => {
    const { calls } = setup({ tab: 'taxonomia' })
    const rows = within(await within(await panel()).findByRole('table', { name: 'Main topics' })).getAllByRole('row')
    expect(within(rows[1]).queryByRole('button', { name: /borrar/i })).not.toBeInTheDocument()
    await userEvent.click(within(rows[1]).getByRole('button', { name: /desactivar/i }))
    expect(calls).toEqual([])
    await userEvent.click(within(rows[1]).getByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(calls).toEqual([{ method: 'PUT', path: 'cajeros', body: {
      code: 'cajeros', name: 'Incidencia en cajero', description: 'Dinero no entregado.', keywords: ['cajero'], active: false,
    } }]))
  })

  it('un main topic sin uso se puede borrar tras confirmar', async () => {
    const { calls } = setup({ tab: 'taxonomia' })
    const rows = within(await within(await panel()).findByRole('table', { name: 'Main topics' })).getAllByRole('row')
    await userEvent.click(within(rows[2]).getByRole('button', { name: /borrar/i }))
    await userEvent.click(within(rows[2]).getByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(calls).toEqual([{ method: 'DELETE', path: 'criptoactivos', body: undefined }]))
  })

  it('en solo lectura no hay acciones', async () => {
    setup({ tab: 'taxonomia', user: USERS.supervisor })
    const p = await panel()
    await within(p).findByRole('table', { name: 'Main topics' })
    expect(within(p).queryByRole('button', { name: /nuevo|editar|desactivar|borrar/i })).not.toBeInTheDocument()
  })
})

describe('Configuración: KPIs y objetivos', () => {
  it('muestra el sentido de cada KPI y guarda objetivo, umbrales y dashboards', async () => {
    const { calls } = setup({ tab: 'kpis' })
    const p = await panel()
    const row = await within(p).findByRole('group', { name: 'Tasa de resolución' })
    expect(row).toHaveTextContent(/más es mejor/i)
    expect(within(p).getByRole('group', { name: 'Duración media (AHT)' })).toHaveTextContent(/más es peor/i)
    const amber = within(row).getByLabelText('Umbral ámbar')
    await userEvent.clear(amber)
    await userEvent.type(amber, '65')
    await userEvent.click(within(row).getByRole('checkbox', { name: 'Experiencia de cliente' }))
    await userEvent.click(within(row).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toEqual([{ method: 'PUT', path: 'kpi resolution_rate', body: {
      target: 75, green: 75, amber: 65, dashboards: ['vision-general', 'calidad-y-cumplimiento', 'experiencia-de-cliente'],
    } }]))
  })

  it('un umbral vacío se envía como null y un umbral incoherente muestra su error', async () => {
    const { calls } = setup({ tab: 'kpis', reply: { 'PUT kpi resolution_rate': () => ({ status: 422, body: { detail: [
      { loc: ['body', 'amber'], msg: 'Debe ser menor que el umbral verde (más es mejor)', type: 'value_error' }] } }) } })
    const row = await within(await panel()).findByRole('group', { name: 'Tasa de resolución' })
    await userEvent.clear(within(row).getByLabelText('Objetivo'))
    await userEvent.click(within(row).getByRole('button', { name: 'Guardar' }))
    expect(await within(row).findByText(/menor que el umbral verde/i)).toBeInTheDocument()
    expect(within(row).getByLabelText('Umbral ámbar')).toHaveAttribute('aria-invalid', 'true')
    expect(calls[0].body).toMatchObject({ target: null })
  })
})

describe('Configuración: Cumplimiento', () => {
  it('distingue los checks del análisis de los evaluados por frases', async () => {
    setup({ tab: 'cumplimiento' })
    const table = await within(await panel()).findByRole('table', { name: 'Checks de cumplimiento' })
    const rows = within(table).getAllByRole('row')
    expect(rows[1]).toHaveTextContent(/resultado del análisis/i)
    expect(rows[2]).toHaveTextContent(/por frases/i)
    expect(rows[2]).toHaveTextContent('Voz')
    expect(within(rows[1]).queryByRole('button', { name: /borrar/i })).not.toBeInTheDocument()
    expect(within(rows[2]).getByRole('button', { name: /borrar/i })).toBeInTheDocument()
  })

  it('crea un check con una frase por línea', async () => {
    const { calls } = setup({ tab: 'cumplimiento' })
    const p = await panel()
    await userEvent.click(await within(p).findByRole('button', { name: 'Nuevo check' }))
    const form = within(p).getByRole('form', { name: 'Nuevo check' })
    await userEvent.type(within(form).getByLabelText('Código'), 'aviso_grabacion')
    await userEvent.type(within(form).getByLabelText('Nombre'), 'Aviso de grabación')
    await userEvent.type(within(form).getByLabelText('Frases esperadas'), 'esta llamada puede ser grabada{Enter}{Enter}  grabación ')
    await userEvent.selectOptions(within(form).getByLabelText('Canal'), 'voz')
    await userEvent.click(within(form).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(calls).toEqual([{ method: 'POST', path: 'checks', body: {
      code: 'aviso_grabacion', name: 'Aviso de grabación', description: '',
      phrases: ['esta llamada puede ser grabada', 'grabación'], channel: 'voz', active: true,
    } }]))
  })

  it('editar las frases de un check del análisis avisa de que no cambia su resultado', async () => {
    setup({ tab: 'cumplimiento' })
    const p = await panel()
    const row = within(await within(p).findByRole('table', { name: 'Checks de cumplimiento' })).getAllByRole('row')[1]
    await userEvent.click(within(row).getByRole('button', { name: /editar/i }))
    const form = within(p).getByRole('form', { name: /editar check/i })
    expect(form).toHaveTextContent(/sus frases no cambian su resultado/i)
    expect(within(form).getByLabelText('Frases esperadas')).toHaveValue('le atiende')
  })

  it('borrar un check por frases pide confirmación', async () => {
    const { calls } = setup({ tab: 'cumplimiento' })
    const row = within(await within(await panel()).findByRole('table', { name: 'Checks de cumplimiento' })).getAllByRole('row')[2]
    await userEvent.click(within(row).getByRole('button', { name: /borrar/i }))
    expect(calls).toEqual([])
    await userEvent.click(within(row).getByRole('button', { name: /confirmar/i }))
    await waitFor(() => expect(calls).toEqual([{ method: 'DELETE', path: 'oferta_encuesta', body: undefined }]))
  })
})

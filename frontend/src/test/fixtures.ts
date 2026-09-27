export function fakeId(prefix: string, n: number): string {
  return `${prefix}-${n.toString(16).toUpperCase().padStart(8, '0')}-0000-4000-8000-${String(n).padStart(12, '0')}`
}

export const QUEUE = {
  particulares: { id: fakeId('1QU', 1), name: 'Particulares' },
  tarjetas: { id: fakeId('1QU', 2), name: 'Tarjetas' },
  fraude: { id: fakeId('1QU', 3), name: 'Fraude y seguridad' },
}
export const AGENT = {
  sergio: { id: fakeId('1AG', 1), name: 'Sergio Molina', queue_id: QUEUE.fraude.id, queue: 'Fraude y seguridad' },
  irene: { id: fakeId('1AG', 2), name: 'Irene Vidal', queue_id: fakeId('1QU', 4), queue: 'Banca digital' },
}
export const DETAIL_ID = fakeId('1CO', 5)
export const MISSING_ID = fakeId('1CO', 999999)

const KPI_META: Array<[string, string, string, boolean]> = [
  ['volume', 'Volumen', 'conversaciones', true],
  ['aht_s', 'Duración media (AHT)', 's', false],
  ['sentiment_avg', 'Sentimiento medio', 'índice', true],
  ['negative_pct', 'Conversaciones negativas', '%', false],
  ['resolution_rate', 'Tasa de resolución', '%', true],
  ['escalation_rate', 'Tasa de escalado', '%', false],
  ['fcr_rate', 'Resolución en primer contacto (FCR)', '%', true],
  ['csat_avg', 'CSAT predicho', '1-5', true],
  ['effort_avg', 'Esfuerzo del cliente', '1-5', false],
  ['compliance_rate', 'Cumplimiento', '%', true],
  ['churn_high_pct', 'Riesgo de abandono alto', '%', false],
  ['first_response_s', 'Primera respuesta (chat)', 's', false],
  ['avg_turns', 'Turnos medios', 'turnos', false],
]

const VALUES: Record<string, [number, number]> = {
  volume: [1319, 1370], aht_s: [232.02, 230.42], sentiment_avg: [0.03, -0.01], negative_pct: [26.96, 29.73],
  resolution_rate: [65.52, 61.62], escalation_rate: [15.99, 14.49], fcr_rate: [81.5, 77.84], csat_avg: [3.71, 3.59],
  effort_avg: [2.69, 2.76], compliance_rate: [61.76, 62.7], churn_high_pct: [26.33, 27.03],
  first_response_s: [44.91, 44.85], avg_turns: [15.45, 15.41],
}

export function kpiValues(scale = 1): Record<string, number> {
  return Object.fromEntries(Object.entries(VALUES).map(([code, [value]]) => [code, code === 'volume' ? Math.round(value * scale) : value]))
}

export const summaryFixture = {
  period: { from: '2026-08-28', to: '2026-09-26' },
  previous_period: { from: '2026-07-29', to: '2026-08-27' },
  kpis: KPI_META.map(([code, label, unit, higher]) => {
    const [value, previous] = VALUES[code]
    return {
      code, label, unit, higher_is_better: higher, value, previous,
      delta: Math.round((value - previous) * 100) / 100,
      delta_pct: unit === 'índice' ? null : Math.round((10000 * (value - previous)) / previous) / 100,
    }
  }),
  compliance_by_check: [
    { code: 'saludo', label: 'Saludo e identificación del agente', value: 95.1, applicable: 1319 },
    { code: 'verificacion_identidad', label: 'Verificación de identidad del cliente', value: 88.3, applicable: 1319 },
    { code: 'bloqueo_preventivo', label: 'Ofrecimiento de bloqueo preventivo en casos de fraude', value: 79.4, applicable: 220 },
  ],
}

export function timeseriesFixture(url: string) {
  const params = new URL(url, 'http://localhost').searchParams
  const granularity = params.get('granularity') ?? 'day'
  const starts = granularity === 'week' ? ['2026-09-07', '2026-09-14', '2026-09-21'] : ['2026-09-24', '2026-09-25', '2026-09-26']
  return {
    kpi: params.get('kpi'), granularity, period: { from: starts[0], to: '2026-09-26' },
    points: starts.map((start, i) => ({ period_start: start, period_end: start, value: [12, 18, 9][i] })),
  }
}

const BREAKDOWN_KEYS: Record<string, Array<[string, string]>> = {
  main_topic: [['cargo_no_reconocido', 'Cargo no reconocido'], ['acceso_banca_digital', 'Acceso a banca digital'], ['cajeros', 'Incidencia en cajero']],
  channel: [['voz', 'voz'], ['chat', 'chat']],
  queue: [[QUEUE.particulares.id, QUEUE.particulares.name], [QUEUE.fraude.id, QUEUE.fraude.name]],
  agent: [[AGENT.sergio.id, AGENT.sergio.name], [AGENT.irene.id, AGENT.irene.name]],
}

export function breakdownFixture(url: string) {
  const dimension = new URL(url, 'http://localhost').searchParams.get('dimension') ?? 'main_topic'
  return {
    dimension, period: summaryFixture.period,
    items: BREAKDOWN_KEYS[dimension].map(([key, label], i) => ({
      key, label, kpis: { ...kpiValues(1 / (i + 2)), sentiment_avg: i === 0 ? -0.42 : 0.18, csat_avg: 3.1 + i * 0.4 },
    })),
  }
}

export const catalogFixture = {
  channels: [{ code: 'voz', label: 'Voz' }, { code: 'chat', label: 'Chat' }],
  queues: [QUEUE.particulares, QUEUE.tarjetas, QUEUE.fraude],
  agents: [AGENT.sergio, AGENT.irene],
  main_topics: [
    { code: 'cargo_no_reconocido', name: 'Cargo no reconocido' },
    { code: 'acceso_banca_digital', name: 'Acceso a banca digital' },
    { code: 'cajeros', name: 'Incidencia en cajero' },
  ],
  compliance_checks: [{ code: 'saludo', label: 'Saludo e identificación del agente' }],
  resolutions: [{ code: 'resuelta', label: 'Resuelta' }, { code: 'no_resuelta', label: 'No resuelta' }, { code: 'escalada', label: 'Escalada' }],
  churn_risks: [{ code: 'bajo', label: 'Bajo' }, { code: 'medio', label: 'Medio' }, { code: 'alto', label: 'Alto' }],
}

export const metricsRoutes = {
  'GET /api/metrics/summary': () => ({ status: 200, body: summaryFixture }),
  'GET /api/metrics/timeseries': ({ url }: { url: string }) => ({ status: 200, body: timeseriesFixture(url) }),
  'GET /api/metrics/breakdown': ({ url }: { url: string }) => ({ status: 200, body: breakdownFixture(url) }),
  'GET /api/catalog': () => ({ status: 200, body: catalogFixture }),
}

const LIST_TOPICS: Array<[string, string]> = [
  ['cargo_no_reconocido', 'Cargo no reconocido'], ['acceso_banca_digital', 'Acceso a banca digital'], ['cajeros', 'Incidencia en cajero'],
]

export function conversationItem(i: number) {
  const [code, label] = LIST_TOPICS[i % LIST_TOPICS.length]
  return {
    id: fakeId('1CO', 1000 - i),
    started_at: `2026-09-${String(26 - (i % 20)).padStart(2, '0')}T10:${String(i % 60).padStart(2, '0')}:00`,
    channel: i % 2 ? 'chat' : 'voz',
    queue_id: (i % 3 ? QUEUE.particulares : QUEUE.fraude).id,
    queue: (i % 3 ? QUEUE.particulares : QUEUE.fraude).name,
    agent_id: (i % 2 ? AGENT.irene : AGENT.sergio).id,
    agent: (i % 2 ? AGENT.irene : AGENT.sergio).name,
    main_topic: code,
    main_topic_label: label,
    summary: `La clienta llama porque no reconoce un cargo número ${i}. El agente revisa el movimiento. Queda resuelta con una reclamación abierta.`,
    sentiment: i % 3 ? 0.35 : -0.52,
    resolution: ['resuelta', 'no_resuelta', 'escalada'][i % 3],
    csat: 3.4,
    duration_s: 180 + i,
  }
}

export function conversationListFixture(url: string, total = 60) {
  const params = new URL(url, 'http://localhost').searchParams
  const page = Number(params.get('page') ?? 1)
  const pageSize = Number(params.get('page_size') ?? 25)
  const start = (page - 1) * pageSize
  const items = Array.from({ length: Math.max(0, Math.min(pageSize, total - start)) }, (_, k) => conversationItem(start + k))
  return { total, page, page_size: pageSize, pages: Math.ceil(total / pageSize), items }
}

export const conversationRoutes = {
  'GET /api/conversations': ({ url }: { url: string }) => ({ status: 200, body: conversationListFixture(url) }),
  'GET /api/catalog': () => ({ status: 200, body: catalogFixture }),
}

export const conversationDetailFixture = {
  id: DETAIL_ID,
  channel: 'chat',
  started_at: '2026-06-29T13:27:01',
  duration_s: 494,
  queue_id: QUEUE.fraude.id,
  queue: 'Fraude y seguridad',
  agent_id: AGENT.sergio.id,
  agent: 'Sergio Molina',
  customer_id: fakeId('1CU', 123),
  main_topic_label: 'Cargo no reconocido',
  turns: [
    { speaker: 'bot', text: 'Hola, soy el asistente virtual de Banco Horizonte. ¿En qué puedo ayudarle?', offset_s: 0, sentiment: 0.1 },
    { speaker: 'cliente', text: 'Hola, me ha aparecido un cargo de 366,12 € en TiendaYa Online que no reconozco.', offset_s: 2, sentiment: -0.5 },
    { speaker: 'sistema', text: 'Sergio se ha unido a la conversación.', offset_s: 60, sentiment: 0 },
    { speaker: 'agente', text: 'Hola, soy Sergio de Banco Horizonte. Ya he leído su consulta, lo reviso ahora mismo.', offset_s: 63, sentiment: 0.26 },
    { speaker: 'cliente', text: 'No, nadie más la usa y la tengo aquí conmigo.', offset_s: 142, sentiment: -0.54 },
    { speaker: 'agente', text: 'De acuerdo, voy a marcar el movimiento como posible fraude y abrir una reclamación.', offset_s: 159, sentiment: 0.44 },
    { speaker: 'cliente', text: 'Pues vaya, tendré que ir a comisaría.', offset_s: 358, sentiment: -0.66 },
    { speaker: 'sistema', text: 'La conversación ha finalizado.', offset_s: 491, sentiment: 0 },
  ],
  analysis: {
    summary: 'La clienta escribe porque no reconoce un cargo de 366,12 € en TiendaYa Online. El agente revisa el movimiento y lo marca como posible fraude. Queda pendiente de que aporte la denuncia para abrir la reclamación.',
    main_topic: 'cargo_no_reconocido',
    secondary_topics: ['devolución', 'reiteración del problema'],
    sentiment: -0.67,
    sentiment_timeline: [0.1, -0.5, 0, 0.26, -0.54, 0.44, -0.66, 0],
    resolution: 'no_resuelta',
    csat: 1.3,
    effort: 4.4,
    churn_risk: 'alto',
    compliance: { saludo: true, verificacion_identidad: false, proteccion_datos: true, no_solicitar_pin: true, bloqueo_preventivo: null, despedida: true },
    entities: [{ type: 'importe', value: '366,12 €' }, { type: 'comercio', value: 'TiendaYa Online' }],
    keywords: ['no reconozco', 'fraude'],
  },
}

export const detailCatalog = {
  ...catalogFixture,
  compliance_checks: [
    { code: 'saludo', label: 'Saludo e identificación del agente' },
    { code: 'verificacion_identidad', label: 'Verificación de identidad del cliente' },
    { code: 'proteccion_datos', label: 'Aviso de protección de datos' },
    { code: 'no_solicitar_pin', label: 'No solicitar PIN ni claves completas' },
    { code: 'bloqueo_preventivo', label: 'Ofrecimiento de bloqueo preventivo en casos de fraude' },
    { code: 'despedida', label: 'Despedida con resumen de la gestión' },
  ],
}

export const detailRoutes = {
  ...conversationRoutes,
  'GET /api/catalog': () => ({ status: 200, body: detailCatalog }),
  [`GET /api/conversations/${DETAIL_ID}`]: () => ({ status: 200, body: conversationDetailFixture }),
  [`GET /api/conversations/${MISSING_ID}`]: () => ({ status: 404, body: { detail: 'Conversación no encontrada' } }),
}

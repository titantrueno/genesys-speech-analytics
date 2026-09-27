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
  queue: [['Particulares', 'Particulares'], ['Fraude y seguridad', 'Fraude y seguridad']],
  agent: [['Sergio Molina', 'Sergio Molina'], ['Irene Vidal', 'Irene Vidal']],
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
  queues: ['Particulares', 'Tarjetas', 'Fraude y seguridad'],
  agents: [{ name: 'Sergio Molina', queue: 'Fraude y seguridad' }, { name: 'Irene Vidal', queue: 'Banca digital' }],
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
    id: `CNV-${String(1000 - i).padStart(6, '0')}`,
    started_at: `2026-09-${String(26 - (i % 20)).padStart(2, '0')}T10:${String(i % 60).padStart(2, '0')}:00`,
    channel: i % 2 ? 'chat' : 'voz',
    queue: i % 3 ? 'Particulares' : 'Fraude y seguridad',
    agent: i % 2 ? 'Irene Vidal' : 'Sergio Molina',
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

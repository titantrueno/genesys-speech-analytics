import { conversationDetailFixture, conversationItem, fakeId, QUEUE } from './fixtures'

/** Conversaciones reales (FE012): el análisis de la plataforma está pendiente y Genesys da su propia analítica. */

const PENDING = {
  summary: '', main_topic: null, secondary_topics: [], sentiment: 0.0, sentiment_timeline: [], resolution: null,
  csat: null, effort: null, churn_risk: null, compliance: {}, compliance_pending: ['saludo'], entities: [], keywords: [],
  pending: true,
}

const BASE_GENESYS = {
  genesys_id: '7b94988a-807b-4a59-8767-ed445ba9f12b', direction: 'inbound', ani: '+34675075376', dnis: '+34919187266',
  external_tag: 'Javier Del Olmo', transcript_quality: 'completa', disconnect_type: 'peer', transferred: true,
  reconnected: false, contained_in_bot: false, derived_to_agent: true, abandoned_in_queue: false,
  undelivered_messages: 0, customer_sentiment: 0.12, mos: 4.3, divisions: [],
}

const segment = (seq: number, kind: string, extra: Record<string, unknown> = {}) => ({
  seq, kind, name: null, started_at: '2026-10-12T08:55:00Z', ended_at: '2026-10-12T08:56:00Z', disconnect_type: null,
  exit_reason: null, transfer_target: null, queue: null, agent: null, flow: null, wrapup: null, ...extra,
})

export const REAL_VOICE_ID = fakeId('1CO', 71)
export const REAL_CHAT_ID = fakeId('1CO', 72)
export const REAL_UNDELIVERED_ID = fakeId('1CO', 73)
export const REAL_RECONNECT_ID = fakeId('1CO', 74)

const agent = { id: fakeId('1AG', 9), genesys_id: 'ag-1', name: 'Javier Del Olmo' }
const queue = { id: QUEUE.fraude.id, genesys_id: 'q-1', name: 'AIT_Transcription' }
const flow = { id: 'flow-1', name: 'Sierra VoiceAgent', type: 'INBOUNDCALL' }

const BOT_AGENT_SEGMENTS = [
  segment(0, 'cliente'), segment(1, 'ivr', { flow, name: 'Sierra VoiceAgent' }),
  segment(2, 'cola', { queue }), segment(3, 'agente', { agent, wrapup: { id: 'w-1', name: 'Default Wrap-up Code' } }),
]

export const realVoiceDetail = {
  ...conversationDetailFixture, id: REAL_VOICE_ID, channel: 'voz', queue_id: queue.id, queue: queue.name,
  agent_id: agent.id, agent: agent.name, main_topic_label: null, customer_id: fakeId('1CU', 5),
  turns: [
    { speaker: 'bot', text: 'Hola, soy el asistente virtual. ¿En qué puedo ayudarle?', offset_s: 0, sentiment: null, delivered: true },
    { speaker: 'cliente', text: 'Quiero hablar con una persona, tengo un problema con un pago.', offset_s: 6, sentiment: -0.4, delivered: true },
    { speaker: 'bot', text: 'Le paso con un agente.', offset_s: 12, sentiment: null, delivered: true },
    { speaker: 'agente', text: 'Buenos días, soy Javier, ¿en qué le ayudo?', offset_s: 40, sentiment: 0.3, delivered: true },
    { speaker: 'cliente', text: 'Un pago de Amazon Brasil que no reconozco.', offset_s: 48, sentiment: -0.2, delivered: true },
  ],
  analysis: { ...PENDING, sentiment: 0.12, sentiment_timeline: [-0.4, -0.2] },
  genesys: {
    ...BASE_GENESYS,
    metrics: {
      handle_s: 212.4, queue_wait_s: 31.2, talk_s: 160.5, hold_s: 8.5, acw_s: 12, ivr_s: 86.5, bot_time_s: 86.5,
      sta_time_pct: { agent: 38.4, customer: 41.2, silence: 14.9, ivr: 5.5 }, asr_confidence: { cliente: 0.87, agente: 0.93, bot: 0.99 },
      r_factor: 92,
    },
    segments: BOT_AGENT_SEGMENTS,
    topics: [
      { seq: 0, topic_id: 't1', name: 'Saludos', phrase: 'hola soy el asistente', speaker: 'bot', turn_seq: 0, offset_s: 0, confidence: 0.9 },
      { seq: 1, topic_id: 't2', name: 'Realización de pagos', phrase: 'un pago de Amazon', speaker: 'cliente', turn_seq: 4, offset_s: 48, confidence: 0.8 },
    ],
  },
}

export const realChatDetail = {
  ...realVoiceDetail, id: REAL_CHAT_ID, channel: 'chat',
  turns: [
    { speaker: 'bot', text: 'Hola, ¿en qué puedo ayudarle?', offset_s: 0, sentiment: null, delivered: true },
    { speaker: 'cliente', text: 'Necesito ayuda con un cargo.', offset_s: 5, sentiment: -0.1, delivered: true },
    { speaker: 'agente', text: 'Claro, lo reviso.', offset_s: 30, sentiment: 0.2, delivered: true },
  ],
  genesys: {
    ...BASE_GENESYS, ani: null, dnis: null, mos: null,
    metrics: { handle_s: 120, queue_wait_s: 20, first_response_s: 14.5, avg_agent_response_s: 22.1, avg_customer_response_s: 40,
      customer_messages: 1, agent_messages: 1, bot_messages: 1, undelivered_messages: 0 },
    segments: BOT_AGENT_SEGMENTS, topics: [],
  },
}

export const realUndeliveredDetail = {
  ...realChatDetail, id: REAL_UNDELIVERED_ID,
  turns: [
    { speaker: 'cliente', text: 'Hola, me cobraron dos veces.', offset_s: 0, sentiment: -0.3, delivered: true },
    { speaker: 'agente', text: 'lo estoy revisando, un segundo', offset_s: 20, sentiment: null, delivered: false },
    { speaker: 'agente', text: 'Ya lo tengo, le devolvemos un cargo.', offset_s: 60, sentiment: 0.4, delivered: true },
  ],
  genesys: { ...realChatDetail.genesys, undelivered_messages: 1, derived_to_agent: true,
    segments: [segment(0, 'cliente'), segment(1, 'cola', { queue }), segment(2, 'agente', { agent })] },
}

export const realReconnectDetail = {
  ...realChatDetail, id: REAL_RECONNECT_ID,
  turns: [
    { speaker: 'bot', text: 'Hola, ¿en qué puedo ayudarle?', offset_s: 0, sentiment: null, delivered: true },
    { speaker: 'cliente', text: 'Quiero hablar con alguien.', offset_s: 5, sentiment: -0.1, delivered: true },
    { speaker: 'agente', text: 'Hola, soy Javier.', offset_s: 30, sentiment: 0.2, delivered: true },
    { speaker: 'bot', text: 'Bienvenido de nuevo. ¿En qué puedo ayudarle?', offset_s: 300, sentiment: null, delivered: true },
    { speaker: 'cliente', text: 'Me he desconectado.', offset_s: 305, sentiment: -0.2, delivered: true },
    { speaker: 'agente', text: 'Retomamos donde lo dejamos.', offset_s: 330, sentiment: 0.3, delivered: true },
  ],
  genesys: { ...realChatDetail.genesys, reconnected: true,
    segments: [segment(0, 'cliente'), segment(1, 'flujo_entrada', { flow }), segment(2, 'cola', { queue }),
      segment(3, 'agente', { agent }), segment(4, 'flujo_entrada', { flow }), segment(5, 'cola', { queue }),
      segment(6, 'agente', { agent })] },
}

export const realCatalog = {
  reference_date: '2026-10-13', origin: 'real',
  channels: [{ code: 'voz', label: 'Voz' }, { code: 'chat', label: 'Chat' }],
  queues: [{ id: queue.id, name: queue.name }], agents: [{ id: agent.id, name: agent.name, queue_id: queue.id, queue: queue.name }],
  main_topics: [], compliance_checks: [{ code: 'saludo', label: 'Saludo e identificación del agente' }],
  resolutions: [], churn_risks: [],
}

export function realListItem(i: number, overrides: Record<string, unknown> = {}) {
  return {
    ...conversationItem(i), queue_id: queue.id, queue: queue.name, agent_id: i % 2 ? agent.id : null, agent: i % 2 ? agent.name : null,
    main_topic: null, main_topic_label: null, summary: '', sentiment: i % 3 ? 0.2 : null, resolution: null, csat: null,
    analysis_pending: true, ani: i % 2 ? '+34675075376' : null, external_tag: i % 2 ? 'Javier Del Olmo' : null,
    contained_in_bot: i % 2 === 0, transcript_quality: i === 2 ? 'parcial' : 'completa', ...overrides,
  }
}

import type { AuditEntry, ComplianceCheck, Connector, KpiConfig, PlatformConfig, Taxonomy, Topic } from '../config/types'
import { fakeId } from './fixtures'

export const KPI_CONFIG: KpiConfig[] = [
  { code: 'volume', label: 'Volumen', unit: 'conversaciones', higher_is_better: true, target: null, green: null, amber: null, dashboards: ['vision-general'] },
  { code: 'resolution_rate', label: 'Tasa de resolución', unit: '%', higher_is_better: true, target: 75, green: 75, amber: 60, dashboards: ['vision-general', 'calidad-y-cumplimiento'] },
  { code: 'aht_s', label: 'Duración media (AHT)', unit: 's', higher_is_better: false, target: 240, green: 240, amber: 300, dashboards: ['vision-general'] },
]

export function platformConfig(overrides: Partial<PlatformConfig> = {}): PlatformConfig {
  return {
    version: 0,
    general: { platform_name: 'Speech & Text Analytics', timezone: 'Europe/Madrid', language: 'es-ES' },
    sources: { origin: 'sintetico' },
    privacy: { pii_masking: true },
    ai: { provider: 'gemini', model: 'gemini-3.5-flash-lite', simulated: false },
    kpis: KPI_CONFIG,
    options: {
      languages: [{ value: 'es-ES', label: 'Español (España)' }],
      timezones: ['America/Los_Angeles', 'Asia/Tokyo', 'Europe/Madrid', 'UTC'],
      providers: [
        { value: 'gemini', label: 'Gemini (Google)', models: [
          { value: 'gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash-Lite', temperature: true },
          { value: 'gemini-3.8-flash', label: 'Gemini 3.8 Flash', temperature: true }] },
        { value: 'anthropic', label: 'Anthropic (Claude)', models: [
          { value: 'claude-opus-5-5', label: 'Claude Opus 5.5', temperature: false }] },
        { value: 'simulado', label: 'Simulado (sin LLM)', models: [
          { value: 'mock-rapido', label: 'Simulado rápido', temperature: true },
          { value: 'mock-preciso', label: 'Simulado preciso', temperature: true }] },
      ],
      sections: [
        { value: 'general', label: 'General' }, { value: 'fuentes', label: 'Fuentes de datos' },
        { value: 'taxonomia', label: 'Taxonomía' }, { value: 'kpis', label: 'KPIs y objetivos' },
        { value: 'cumplimiento', label: 'Cumplimiento' }, { value: 'privacidad', label: 'Privacidad' },
        { value: 'modelos', label: 'Modelos de IA' },
      ],
      dashboards: [
        { value: 'vision-general', label: 'Visión general' },
        { value: 'calidad-y-cumplimiento', label: 'Calidad y cumplimiento' },
        { value: 'experiencia-de-cliente', label: 'Experiencia de cliente' },
      ],
    },
    ...overrides,
  }
}

/** Igual que `GET /api/config/ai/status`: si cada proveedor tiene clave en el servicio de LLM (nunca la clave). */
export const AI_STATUS = {
  service: 'disponible',
  providers: [
    { value: 'gemini', label: 'Gemini (Google)', key_configured: true },
    { value: 'anthropic', label: 'Anthropic (Claude)', key_configured: false },
    { value: 'simulado', label: 'Simulado (sin LLM)', key_configured: true },
  ],
}

export const CONNECTORS: Connector[] = [
  { id: fakeId('1CN', 1), name: 'Genesys Cloud · voz transcrita', channel: 'voz', status: 'conectado', last_sync: '2026-09-27T08:00:00+00:00', conversations: 642 },
  { id: fakeId('1CN', 2), name: 'Genesys Cloud · chat', channel: 'chat', status: 'conectado', last_sync: '2026-09-27T08:00:00+00:00', conversations: 358 },
]

export function auditEntry(n: number, overrides: Partial<AuditEntry> = {}): AuditEntry {
  return {
    id: fakeId('1AU', n), user: { id: fakeId('1US', 1), name: 'Admin Demo' }, at: '2026-09-27T10:30:00+00:00',
    section: 'general', element: 'General',
    before: { platform_name: 'Speech & Text Analytics', timezone: 'Europe/Madrid', language: 'es-ES' },
    after: { platform_name: 'Analítica Horizonte', timezone: 'Europe/Madrid', language: 'es-ES' },
    ...overrides,
  }
}

export function topic(n: number, overrides: Partial<Topic> = {}): Topic {
  return {
    id: fakeId('1TP', n), code: `topic_${n}`, name: `Topic ${n}`, description: '', keywords: [], active: true,
    conversations: 0, ...overrides,
  }
}

export const TAXONOMY: Taxonomy = {
  main_topics: [
    topic(1, { code: 'cajeros', name: 'Incidencia en cajero', description: 'Dinero no entregado.', keywords: ['cajero'], conversations: 41 }),
    topic(2, { code: 'criptoactivos', name: 'Criptoactivos', keywords: ['bitcoin'], conversations: 0 }),
  ],
  secondary_topics: [
    topic(3, { id: fakeId('1TS', 3), code: 'compras online', name: 'compras online', conversations: 120 }),
  ],
}

export const CHECKS: ComplianceCheck[] = [
  { id: fakeId('1CK', 1), code: 'saludo', name: 'Saludo e identificación del agente', description: 'Saluda.',
    phrases: ['le atiende'], channel: 'ambos', active: true, evaluation: 'analisis', builtin: true },
  { id: fakeId('1CK', 2), code: 'oferta_encuesta', name: 'Ofrecimiento de encuesta', description: '',
    phrases: ['valore la atención', 'encuesta'], channel: 'voz', active: true, evaluation: 'frases', builtin: false },
]

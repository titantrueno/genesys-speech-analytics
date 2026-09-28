import type { AuditEntry, Connector, KpiConfig, PlatformConfig } from '../config/types'
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
    privacy: { pii_masking: true },
    ai: { provider: 'simulado', model: 'mock-rapido', simulated: true },
    kpis: KPI_CONFIG,
    options: {
      languages: [{ value: 'es-ES', label: 'Español (España)' }],
      timezones: ['America/Los_Angeles', 'Asia/Tokyo', 'Europe/Madrid', 'UTC'],
      providers: [{ value: 'simulado', label: 'Simulado (sin LLM)', models: [
        { value: 'mock-rapido', label: 'Simulado rápido' }, { value: 'mock-preciso', label: 'Simulado preciso' }] }],
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

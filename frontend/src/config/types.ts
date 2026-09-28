import type { KpiCode } from '../api/metrics'

export type SectionCode = 'general' | 'fuentes' | 'taxonomia' | 'kpis' | 'cumplimiento' | 'privacidad' | 'modelos'
export type Option<T extends string = string> = { value: T; label: string }

export interface GeneralConfig { platform_name: string; timezone: string; language: string }
export interface PrivacyConfig { pii_masking: boolean }
export interface AiConfig { provider: string; model: string }

export interface KpiConfig {
  code: KpiCode
  label: string
  unit: string
  higher_is_better: boolean
  target: number | null
  green: number | null
  amber: number | null
  dashboards: string[]
}

export interface PlatformConfig {
  version: number
  general: GeneralConfig
  privacy: PrivacyConfig
  ai: AiConfig & { simulated: boolean }
  kpis: KpiConfig[]
  options: {
    languages: Option[]
    timezones: string[]
    providers: Array<Option & { models: Option[] }>
    sections: Option<SectionCode>[]
    dashboards: Option[]
  }
}

export interface Connector {
  id: string
  name: string
  channel: 'voz' | 'chat'
  status: string
  last_sync: string
  conversations: number
}

export interface AuditEntry {
  id: string
  user: { id: string; name: string }
  at: string
  section: SectionCode
  element: string
  before: unknown
  after: unknown
}

export interface Topic {
  id: string
  code: string
  name: string
  description: string
  keywords: string[]
  active: boolean
  conversations: number
}

export interface Taxonomy { main_topics: Topic[]; secondary_topics: Topic[] }

export interface ComplianceCheck {
  id: string
  code: string
  name: string
  description: string
  phrases: string[]
  channel: 'voz' | 'chat' | 'ambos'
  active: boolean
  evaluation: 'analisis' | 'frases'
  builtin: boolean
}

/** Error de validación de FastAPI (`422`): ruta del campo y mensaje. */
export interface FieldIssue { loc: Array<string | number>; msg: string; type: string }

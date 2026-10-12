import type { KpiCode } from '../api/metrics'

export type SectionCode = 'general' | 'fuentes' | 'taxonomia' | 'kpis' | 'cumplimiento' | 'privacidad' | 'modelos'

/** Pestañas de Configuración: las secciones editables y la especificación de la API (FE010), que no tiene auditoría. */
export type ConfigTabCode = SectionCode | 'api'
export type Option<T extends string = string> = { value: T; label: string }

export interface GeneralConfig { platform_name: string; timezone: string; language: string }
/** Origen de datos de toda la plataforma (FE012). */
export type DataOrigin = 'sintetico' | 'real'
export interface SourcesConfig { origin: DataOrigin }
export interface PrivacyConfig { pii_masking: boolean }
export interface AiConfig { provider: string; model: string }

/** Modelo de un proveedor; `temperature` dice si la admite (si no, el nodo Prompt no se la envía). */
export type ModelOption = Option & { temperature: boolean }
export type ProviderOption = Option & { models: ModelOption[] }

/** `GET /api/config/ai/status`: si cada proveedor tiene clave en el servicio de LLM (nunca la clave). */
export interface AiStatus { service: 'disponible'; providers: Array<Option & { key_configured: boolean }> }
export interface AiTestResult { ok: boolean; provider: string; model: string; message: string }

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
  sources: SourcesConfig
  privacy: PrivacyConfig
  ai: AiConfig & { simulated: boolean }
  kpis: KpiConfig[]
  options: {
    languages: Option[]
    timezones: string[]
    providers: ProviderOption[]
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
  /** Sección de la configuración o `usuarios` (FE006). */
  section: SectionCode | 'usuarios'
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

export type TopicKind = 'main-topics' | 'secondary-topics'
export type TopicInput = Omit<Topic, 'id' | 'conversations'>
export type CheckInput = Omit<ComplianceCheck, 'id' | 'evaluation' | 'builtin'>

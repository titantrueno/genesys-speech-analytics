/** Flujos de descarga de Genesys Cloud (FE011): el contrato de `/api/download-flows` y del conector. */

export type DownloadChannel = 'voz' | 'chat'
export type RelativeUnit = 'hoy' | 'ayer' | 'horas' | 'dias'

export interface DownloadInterval {
  type: 'relativo' | 'especifico'
  unit?: RelativeUnit | null
  amount?: number | null
  from?: string | null
  to?: string | null
}

export interface DownloadSchedule {
  type: 'desactivada' | 'cada_horas' | 'diaria'
  hours?: number | null
  time?: string | null
}

export type DownloadRunStatus = 'pendiente' | 'en_curso' | 'completada' | 'completada_con_avisos' | 'error'

export interface DownloadFlowInput {
  name: string
  interval: DownloadInterval
  channels: DownloadChannel[]
  schedule: DownloadSchedule
  active: boolean
  /** Vuelve a descargar las conversaciones existentes y borra su summary y main topic del LLM (FE013). */
  overwrite: boolean
}

export interface DownloadFlow extends DownloadFlowInput {
  id: string
  timezone: string
  author: { id: string; name: string }
  created_at: string
  updated_at: string
  next_run_at: string | null
  last_run: { id: string; status: DownloadRunStatus; created_at: string } | null
}

export interface DownloadCounters {
  found: number
  downloaded: number
  inserted: number
  updated: number
  skipped: number
  errors: number
  skipped_in_progress: number
  /** Ya estaban en la base y no se descargaron (flujo sin «Sobrescribir»). */
  skipped_existing: number
  skipped_other_channel: number
  by_channel: Record<string, number>
  by_quality: Record<string, number>
  undelivered_messages: number
}

export interface DownloadRun {
  id: string
  flow_id: string
  origin: 'manual' | 'programada'
  status: DownloadRunStatus
  interval: { from: string; to: string }
  channels: DownloadChannel[]
  /** Nulo en las ejecuciones anteriores a FE013, cuyo modo no se conoce. */
  overwrite: boolean | null
  counters: DownloadCounters
  error: string | null
  started_by: { id: string; name: string } | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_s: number | null
}

export type LogLevel = 'info' | 'aviso' | 'error'

export interface LogEntry {
  id: number
  at: string
  level: LogLevel
  stage: string
  message: string
  genesys_id: string | null
}

export interface GenesysTest {
  ok: boolean
  at: string
  organization: string | null
  region: string | null
  message: string
}

export interface GenesysConnector {
  service: 'disponible' | 'no_disponible'
  region: string | null
  credentials_configured: boolean | null
  database: string | null
  last_test: GenesysTest | null
  last_download: { run_id: string; flow_id: string; status: DownloadRunStatus; finished_at: string | null } | null
  conversations: { total: number; by_channel: Record<string, number>; by_quality: Record<string, number> } | null
}

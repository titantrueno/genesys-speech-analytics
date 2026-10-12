import type { DownloadFlow, DownloadRun } from '../downloads/types'
import { fakeId } from './fixtures'

export const DOWNLOAD_AUTHOR = { id: fakeId('1US', 1), name: 'Admin Demo' }

export function downloadFlow(n: number, overrides: Partial<DownloadFlow> = {}): DownloadFlow {
  return {
    id: fakeId('1FL', 100 + n), name: `Descarga ${n}`, interval: { type: 'relativo', unit: 'hoy', amount: null },
    channels: ['voz', 'chat'], schedule: { type: 'desactivada' }, active: true, overwrite: false, timezone: 'Europe/Madrid',
    author: DOWNLOAD_AUTHOR, created_at: '2026-10-12T08:00:00+00:00', updated_at: '2026-10-12T12:00:00+00:00',
    next_run_at: null, last_run: null, ...overrides,
  }
}

export const COUNTERS = {
  found: 13, downloaded: 13, inserted: 13, updated: 0, skipped: 0, errors: 0, skipped_in_progress: 0, skipped_existing: 0,
  skipped_other_channel: 0, by_channel: { voz: 7, chat: 6 }, by_quality: { completa: 9, parcial: 2, sin_transcripcion: 2 },
  undelivered_messages: 2,
}

export function downloadRun(n: number, overrides: Partial<DownloadRun> = {}): DownloadRun {
  return {
    id: fakeId('1RN', 100 + n), flow_id: fakeId('1FL', 101), origin: 'manual', status: 'completada_con_avisos',
    interval: { from: '2026-10-11T22:00:00+00:00', to: '2026-10-12T11:32:00+00:00' }, channels: ['voz', 'chat'],
    overwrite: false, counters: COUNTERS, error: null, started_by: DOWNLOAD_AUTHOR, created_at: '2026-10-12T11:32:00+00:00',
    started_at: '2026-10-12T11:32:01+00:00', finished_at: '2026-10-12T11:32:14+00:00', duration_s: 13.2, ...overrides,
  }
}

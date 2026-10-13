import { afterEach, describe, expect, it } from 'vitest'
import { formatDateTime, formatDateTimeLong, formatDuration, formatKpi, setDisplayLocale, setDisplayTimeZone } from '../lib/format'

// 21:30 en Madrid (UTC+2) son las 04:30 del día siguiente en Tokio (UTC+9).
const LATE = '2026-09-26T21:30:00+02:00'

afterEach(() => {
  setDisplayLocale('es-ES')
  setDisplayTimeZone(undefined)
})

describe('formatos según el idioma activo (FE016, criterio 9)', () => {
  it('las fechas con hora siguen el idioma y respetan la zona horaria configurada', () => {
    setDisplayTimeZone('Asia/Tokyo')
    setDisplayLocale('es-ES')
    expect(formatDateTime(LATE)).toBe('27 sept, 04:30')
    setDisplayLocale('en-US')
    expect(formatDateTime(LATE)).toBe('Sep 27, 04:30 AM')
    expect(formatDateTimeLong(LATE)).toMatch(/September 27, 2026/)
    setDisplayTimeZone('Europe/Madrid')
    expect(formatDateTime(LATE)).toBe('Sep 26, 09:30 PM')
  })

  it('números, porcentajes y duraciones siguen el idioma', () => {
    setDisplayLocale('es-ES')
    expect(formatKpi(1234.5, '%')).toBe('1.234,5 %')
    expect(formatKpi(-0.04, 'índice')).toBe('-0,04')
    setDisplayLocale('en-US')
    expect(formatKpi(1234.5, '%')).toBe('1,234.5%')
    expect(formatKpi(-0.04, 'índice')).toBe('-0.04')
    expect(formatKpi(null, '%')).toBe('—')
    expect(formatDuration(232)).toBe('3:52 min')
  })
})

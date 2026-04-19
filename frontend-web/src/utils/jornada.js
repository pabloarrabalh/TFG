export const DEFAULT_JORNADA = 18

export function readStoredJornada(key = 'jornada_global', fallback = DEFAULT_JORNADA) {
  try {
    const raw = localStorage.getItem(key)
    const parsed = raw ? parseInt(raw, 10) : NaN
    return Number.isFinite(parsed) ? parsed : fallback
  } catch {
    return fallback
  }
}

export function writeStoredJornada(value, key = 'jornada_global') {
  try {
    localStorage.setItem(key, String(value))
  } catch {}
}

const rawBackendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

export const BACKEND_URL = rawBackendUrl.replace(/\/$/, '')

export const backendUrl = (path = '') => {
  if (!path) return BACKEND_URL
  return `${BACKEND_URL}${path.startsWith('/') ? path : `/${path}`}`
}

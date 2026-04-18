import axios from 'axios'
import { BACKEND_URL } from '../config/backend'

const AUTH_TOKEN_KEY = 'auth_token'

function isJwtExpired(token) {
  try {
    const payloadPart = token.split('.')[1]
    if (!payloadPart) return true
    const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
    const payload = JSON.parse(atob(padded))
    if (!payload?.exp) return false
    return Date.now() >= payload.exp * 1000
  } catch {
    return true
  }
}

export function getAuthToken() {
  try {
    const token = localStorage.getItem(AUTH_TOKEN_KEY) || ''
    if (!token) return ''
    if (isJwtExpired(token)) {
      clearAuthToken()
      return ''
    }
    return token
  } catch {
    return ''
  }
}

export function setAuthToken(token) {
  try {
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token)
    else localStorage.removeItem(AUTH_TOKEN_KEY)
  } catch {}
}

export function clearAuthToken() {
  setAuthToken('')
  try {
    window.dispatchEvent(new Event('auth-token-cleared'))
  } catch {}
}

const apiClient = axios.create({
  baseURL: BACKEND_URL,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  } else if (config.headers?.Authorization) {
    delete config.headers.Authorization
  }
  return config
})

apiClient.interceptors.response.use((response) => {
  return response
}, (error) => {
  if (error?.response?.status === 401) {
    clearAuthToken()
  }
  return Promise.reject(error)
})

// ── Auth ─────────────────────────────────────────────────────
export const fetchMe = () => apiClient.get('/api/me/')

export const login = (username, password) =>
  apiClient.post('/api/auth/login/', { username, password })

export const register = (data) =>
  apiClient.post('/api/auth/register/', data)

export const logout = () =>
  apiClient.post('/api/auth/logout/', {})

// ── Search ───────────────────────────────────────────────────
export const buscar = (q) => apiClient.get(`/api/buscar/?q=${encodeURIComponent(q)}`)

// ── Menu ─────────────────────────────────────────────────────
export const fetchMenu = () => apiClient.get('/api/menu/')

// ── Clasificacion ────────────────────────────────────────────
export const fetchClasificacion = (params = {}) =>
  apiClient.get('/api/clasificacion/', { params })

// ── Equipos ──────────────────────────────────────────────────
export const fetchEquipos = () => apiClient.get('/api/equipos/')
export const fetchEquipo = (nombre, temporada) =>
  apiClient.get(`/api/equipo/${encodeURIComponent(nombre)}/`, { params: temporada ? { temporada } : {} })

// ── Jugador ──────────────────────────────────────────────────
export const fetchJugador = (id, temporada) =>
  apiClient.get(`/api/jugador/${id}/`, { params: temporada ? { temporada } : {} })
export const fetchRadarJugador = (id, temporada) =>
  apiClient.get(`/api/radar/${id}/${temporada}/`)
export const predecirJugador = (jugadorId, jornadaNum) =>
  apiClient.post('/api/predecir-jugador/', { jugador_id: jugadorId, jornada: jornadaNum })
export const predecirPortero = (jugadorId, jornadaNum) =>
  apiClient.post('/api/predecir-portero/', { jugador_id: jugadorId, jornada: jornadaNum })

// ── Plantilla ────────────────────────────────────────────────
export const fetchPlantillas = () => apiClient.get('/api/plantillas/usuario/')
export const fetchPlantilla = (id) => apiClient.get(`/api/plantillas/usuario/${id}/`)
export const guardarPlantilla = (data) => apiClient.post('/api/plantillas/usuario/', data)
export const eliminarPlantilla = (id) => apiClient.delete(`/api/plantillas/usuario/${id}/`)
export const renombrarPlantilla = (id, nombre) =>
  apiClient.post(`/api/plantillas/usuario/${id}/renombrar/`, { nombre })

// ── Perfil ───────────────────────────────────────────────────
export const fetchPerfil = () => apiClient.get('/api/perfil/')
export const updatePerfil = (data) => apiClient.patch('/api/perfil/update/', data)
export const updateStatus = (status) => apiClient.patch('/api/perfil/status/', { estado: status })
export const uploadProfilePhoto = (formData) =>
  apiClient.post('/api/perfil/foto/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
export const deleteFavoriteTeam = (favId) =>
  apiClient.delete(`/api/favoritos/${favId}/`)

// ── Favoritos ────────────────────────────────────────────────
export const fetchFavoriteTeams = () => apiClient.get('/api/favoritos/')
export const toggleFavorito = (equipoId) =>
  apiClient.post('/api/favoritos/toggle/', { equipo_id: equipoId })

// ── Amigos ───────────────────────────────────────────────────
export const fetchAmigos = () => apiClient.get('/api/amigos/')
export const sendFriendRequest = (username) =>
  apiClient.post('/api/amigos/solicitud/', { username })
export const acceptFriendRequest = (requestId) =>
  apiClient.post(`/api/amigos/aceptar/${requestId}/`)
export const rejectFriendRequest = (requestId) =>
  apiClient.post(`/api/amigos/rechazar/${requestId}/`)
export const removeFriend = (userId) =>
  apiClient.post(`/api/amigos/eliminar/${userId}/`)

export default apiClient

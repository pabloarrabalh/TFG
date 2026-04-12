import axios from 'axios'

const BASE_URL = 'http://localhost:8000'

// Read CSRF token from Django's cookie
function getCsrfToken() {
  const name = 'csrftoken'
  const cookies = document.cookie.split(';')
  for (let c of cookies) {
    const [key, val] = c.trim().split('=')
    if (key === name) return decodeURIComponent(val)
  }
  return null
}

const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // send session cookie
  headers: { 'Content-Type': 'application/json' },
})

// Attach CSRF token to mutating requests
apiClient.interceptors.request.use((config) => {
  const method = (config.method || '').toLowerCase()
  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const token = getCsrfToken()
    if (token) config.headers['X-CSRFToken'] = token
  }
  return config
})

// ── Auth ─────────────────────────────────────────────────────
export const fetchCsrf = () => apiClient.get('/login/')

export const login = (username, password) =>
  apiClient.post('/login/submit/', new URLSearchParams({ username, password }), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })

export const register = (data) =>
  apiClient.post('/register/submit/', new URLSearchParams(data), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })

export const logout = () =>
  apiClient.post('/logout/', new URLSearchParams(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })

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

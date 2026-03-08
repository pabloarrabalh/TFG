import { useEffect, useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useAuth } from '../context/AuthContext'
import HelpButton from '../components/ui/HelpButton'
import { useTour } from '../context/TourContext'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'

const STATUS_CONFIG = {
  active: { color: 'bg-green-500', label: 'Activo' },
  away:   { color: 'bg-gray-500',  label: 'Ausente' },
  dnd:    { color: 'bg-yellow-500', label: 'No molestar' },
}

const FILTROS = [
  { key: 'todos',  label: 'Todos' },
  { key: 'active', label: 'Activos' },
  { key: 'away',   label: 'Ausentes' },
  { key: 'dnd',    label: 'No molestar' },
]

function Avatar({ name, photo, size = 10 }) {
  if (photo) {
    const src = photo.startsWith('http') ? photo : `http://localhost:8000${photo}`
    return (
      <img
        src={src}
        alt={name}
        className={`size-${size} rounded-xl object-cover`}
        onError={e => { e.target.style.display = 'none' }}
      />
    )
  }
  const initials = (name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
  const colors = [
    'from-yellow-500 to-orange-600',
    'from-blue-500 to-purple-600',
    'from-primary to-blue-500',
    'from-green-500 to-teal-600',
    'from-pink-500 to-rose-600',
  ]
  const color = colors[(name?.charCodeAt(0) || 0) % colors.length]
  return (
    <div className={`size-${size} bg-gradient-to-br ${color} rounded-xl flex items-center justify-center flex-shrink-0`}>
      <span className="text-sm font-bold text-white">{initials}</span>
    </div>
  )
}

export default function AmigosPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { tourActive, isPhaseCompleted, markPhaseCompleted } = useTour()
  const driverRef = useRef(null)

  const [data, setData] = useState({ amigos: [], solicitudes_pendientes: [], solicitudes_enviadas: [] })
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(null)
  const [filtro, setFiltro] = useState('todos')
  const [busquedaAmigos, setBusquedaAmigos] = useState('')

  // Send request form
  const [searchUser, setSearchUser] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    loadAmigos()
  }, [])

  async function loadAmigos() {
    setLoading(true)
    try {
      const res = await api.get('/api/amigos/')
      setData(res.data)
    } catch {
      setMessage({ type: 'error', text: 'Error al cargar amigos' })
    } finally {
      setLoading(false)
    }
  }

  function flash(type, text) {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 4000)
  }

  async function sendRequest() {
    const raw = searchUser || ''
    const username = raw.trim().replace(/^@/, '')
    if (!username) return
    setSending(true)
    try {
      await api.post('/api/amigos/solicitud/', { username })
      flash('success', `Solicitud enviada a @${username}`)
      setSearchUser('')
      await loadAmigos()
    } catch (e) {
      flash('error', e.response?.data?.error || 'Error al enviar solicitud')
    } finally {
      setSending(false)
    }
  }

  async function accept(id) {
    try {
      await api.post(`/api/amigos/aceptar/${id}/`)
      flash('success', 'Solicitud aceptada')
      await loadAmigos()
    } catch {
      flash('error', 'Error al aceptar')
    }
  }

  async function reject(id) {
    try {
      await api.post(`/api/amigos/rechazar/${id}/`)
      flash('success', 'Solicitud rechazada')
      await loadAmigos()
    } catch {
      flash('error', 'Error al rechazar')
    }
  }

  async function removeAmigo(id) {
    if (!window.confirm('¿Eliminar este amigo?')) return
    try {
      await api.post(`/api/amigos/eliminar/${id}/`)
      flash('success', 'Amigo eliminado')
      await loadAmigos()
    } catch {
      flash('error', 'Error al eliminar')
    }
  }

  // ── Tour guiado ──────────────────────────────────────────────────────────────
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!tourActive || isPhaseCompleted('amigos') || loading) return
    const timer = setTimeout(() => {
      driverRef.current = driver({
        showProgress: true,
        allowClose: false,
        nextBtnText: 'Siguiente →',
        prevBtnText: '← Anterior',
        doneBtnText: 'Ver Perfil →',
        steps: [
          {
            element: '#tour-amigos-buscar',
            popover: {
              title: 'Buscar amigos',
              description: 'Escribe el @usuario de un amigo y envíale una solicitud de amistad para poder ver vuestras plantillas.',
              side: 'bottom',
              align: 'start',
            },
          },
          {
            element: '#tour-amigos-lista',
            popover: {
              title: 'Tu lista de amigos',
              description: 'Aquí aparecen tus amigos. Haz clic en cualquiera para ver su plantilla fantasy con las predicciones y los puntos reales.',
              side: 'top',
              align: 'center',
            },
          },
        ],
        onDestroyStarted: () => {
          driverRef.current?.destroy()
          markPhaseCompleted('amigos')
          navigate('/perfil')
        },
      })
      driverRef.current.drive()
    }, 700)
    return () => {
      clearTimeout(timer)
      driverRef.current?.destroy()
    }
  }, [tourActive, loading])

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <LoadingSpinner size="lg" />
    </div>
  )

  const { amigos, solicitudes_pendientes, solicitudes_enviadas } = data

  // Filter + search friends list
  const amigosFiltrados = amigos.filter(a => {
    const matchFiltro = filtro === 'todos' || (a.estado || 'active') === filtro
    const matchBusqueda = !busquedaAmigos.trim() ||
      (a.first_name || '').toLowerCase().includes(busquedaAmigos.toLowerCase()) ||
      (a.username  || '').toLowerCase().includes(busquedaAmigos.toLowerCase())
    return matchFiltro && matchBusqueda
  })

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black text-white">Mis Amigos</h1>
        <p className="text-gray-400 mt-1">Busca amigos y compara plantillas con predicciones y XAI</p>
      </div>

      {message && (
        <div className={`px-4 py-3 rounded-xl text-sm font-semibold ${message.type === 'success' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* ── Left panel ── */}
        <div className="xl:col-span-5 space-y-4">
          {/* Send request */}
          <GlassPanel id="tour-amigos-buscar" className="p-5">
            <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-lg">person_add</span>
              Añadir amigo
            </h3>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Nombre de usuario (@username)..."
                value={searchUser}
                onChange={e => setSearchUser(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendRequest()}
                className="flex-1 px-3 py-2 bg-background-dark border border-border-dark text-white rounded-xl focus:outline-none focus:border-primary text-sm"
              />
              <button
                onClick={sendRequest}
                disabled={sending || !searchUser.trim()}
                className="px-4 py-2 bg-primary hover:bg-primary-dark text-black rounded-xl font-bold transition-colors disabled:opacity-60 text-sm flex-shrink-0"
              >
                {sending
                  ? <span className="material-symbols-outlined text-base animate-spin">progress_activity</span>
                  : <span className="material-symbols-outlined text-base">send</span>}
              </button>
            </div>
          </GlassPanel>

          {/* Solicitudes recibidas */}
          {solicitudes_pendientes.length > 0 && (
            <GlassPanel className="p-5">
              <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-yellow-400 text-lg">notifications_active</span>
                Solicitudes recibidas
                <span className="bg-yellow-400/20 text-yellow-400 text-xs px-2 py-0.5 rounded-full font-black">{solicitudes_pendientes.length}</span>
              </h3>
              <div className="space-y-2">
                {solicitudes_pendientes.map(sol => (
                  <div key={sol.id} className="flex items-center justify-between p-3 bg-surface-dark rounded-xl">
                    <div className="flex items-center gap-3">
                      <Avatar name={sol.first_name || sol.username} size={9} />
                      <div>
                        <p className="text-white font-semibold text-sm">{sol.first_name || sol.username}</p>
                        <p className="text-xs text-gray-400">@{sol.username}</p>
                      </div>
                    </div>
                    <div className="flex gap-1.5">
                      <button onClick={() => accept(sol.id)}
                        className="p-1.5 bg-green-500/20 hover:bg-green-500/40 text-green-400 rounded-lg transition-colors" title="Aceptar">
                        <span className="material-symbols-outlined text-base">check</span>
                      </button>
                      <button onClick={() => reject(sol.id)}
                        className="p-1.5 bg-red-500/20 hover:bg-red-500/40 text-red-400 rounded-lg transition-colors" title="Rechazar">
                        <span className="material-symbols-outlined text-base">close</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </GlassPanel>
          )}

          {/* Solicitudes enviadas */}
          {solicitudes_enviadas.length > 0 && (
            <GlassPanel className="p-5">
              <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-gray-400 text-lg">schedule_send</span>
                Solicitudes enviadas
              </h3>
              <div className="space-y-2">
                {solicitudes_enviadas.map(sol => (
                  <div key={sol.id} className="flex items-center gap-3 p-3 bg-surface-dark rounded-xl">
                    <Avatar name={sol.username} size={9} />
                    <div className="flex-1">
                      <p className="text-white font-semibold text-sm">@{sol.username}</p>
                      <p className="text-xs text-gray-500">Pendiente de respuesta</p>
                    </div>
                    <span className="text-xs text-gray-500 bg-gray-700/50 px-2 py-0.5 rounded-full">Pendiente</span>
                  </div>
                ))}
              </div>
            </GlassPanel>
          )}

          {/* Friends list with filter + search */}
          <GlassPanel id="tour-amigos-lista" className="overflow-hidden">
            <div className="p-4 border-b border-white/10 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-black text-white">
                  Amigos
                  <span className="ml-2 text-sm text-gray-400 font-normal">({amigos.length})</span>
                </h3>
              </div>
              <input
                type="text"
                placeholder="Buscar entre tus amigos..."
                value={busquedaAmigos}
                onChange={e => setBusquedaAmigos(e.target.value)}
                className="w-full px-3 py-1.5 bg-background-dark border border-border-dark text-white rounded-xl text-xs placeholder-gray-500 focus:outline-none focus:border-primary"
              />
              <div className="flex gap-1 flex-wrap">
                {FILTROS.map(f => (
                  <button key={f.key} onClick={() => setFiltro(f.key)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${filtro === f.key ? 'bg-primary text-black' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            {amigosFiltrados.length === 0
              ? (
                <div className="p-8 text-center">
                  <span className="material-symbols-outlined text-4xl text-gray-600 block mb-3">group</span>
                  <p className="text-gray-400 text-sm">
                    {amigos.length === 0 ? 'Aún no tienes amigos' : 'Sin resultados para ese filtro'}
                  </p>
                </div>
              )
              : (
                <div className="divide-y divide-white/10">
                  {amigosFiltrados.map(amigo => {
                    const st = STATUS_CONFIG[amigo.estado || 'active'] || STATUS_CONFIG.active
                    return (
                      <div key={amigo.id} className="p-4 hover:bg-white/5 transition-colors group">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="relative flex-shrink-0">
                              <Avatar name={amigo.first_name || amigo.username} photo={amigo.profile_photo} size={10} />
                              <span className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-surface-dark ${st.color}`} />
                            </div>
                            <div>
                              <p className="font-bold text-white text-sm">{amigo.first_name || amigo.username}</p>
                              <p className="text-xs text-gray-400">@{amigo.username} · {st.label}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            {/* Ver plantilla */}
                            <Link to={`/amigos/${amigo.id}/plantilla`}
                              className="p-1.5 bg-primary/20 hover:bg-primary/40 text-primary rounded-lg transition-colors" title="Ver plantilla">
                              <span className="material-symbols-outlined text-base">groups</span>
                            </Link>
                            {/* Eliminar (visible on hover) */}
                            <button onClick={() => removeAmigo(amigo.id)}
                              className="p-1.5 text-gray-600 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100" title="Eliminar">
                              <span className="material-symbols-outlined text-base">person_remove</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )
            }
          </GlassPanel>
        </div>

        {/* ── Right panel ── */}
        <div className="xl:col-span-7 space-y-4">
          {/* Info */}
          <GlassPanel className="p-6">
            <div className="flex items-center gap-3 mb-3">
              <span className="material-symbols-outlined text-primary text-2xl">groups</span>
              <h3 className="text-lg font-bold text-white">Ver plantillas de amigos</h3>
            </div>
            <p className="text-gray-400 text-sm mb-3">
              Haz clic en el icono{' '}
              <span className="inline-flex items-center gap-1 bg-primary/20 text-primary px-1.5 py-0.5 rounded text-xs">
                <span className="material-symbols-outlined text-xs">groups</span>
              </span>{' '}
              junto a un amigo para ver su plantilla con predicciones y análisis XAI.
            </p>
            <p className="text-xs text-gray-500">
              Solo puedes ver las plantillas que tu amigo haya marcado como públicas. Configura la privacidad desde{' '}
              <Link to="/perfil" className="text-primary hover:underline">Mi Perfil</Link>.
            </p>
          </GlassPanel>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            <GlassPanel className="p-4 text-center">
              <div className="text-2xl font-black text-primary mb-1">{amigos.length}</div>
              <p className="text-gray-400 text-xs">Amigos</p>
            </GlassPanel>
            <GlassPanel className="p-4 text-center">
              <div className="text-2xl font-black text-yellow-400 mb-1">{solicitudes_pendientes.length}</div>
              <p className="text-gray-400 text-xs">Solicitudes</p>
            </GlassPanel>
            <GlassPanel className="p-4 text-center">
              <div className="text-2xl font-black text-gray-400 mb-1">{solicitudes_enviadas.length}</div>
              <p className="text-gray-400 text-xs">Enviadas</p>
            </GlassPanel>
          </div>

          {/* Quick access to friends' plantillas */}
          {amigos.length > 0 && (
            <GlassPanel className="p-5">
              <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-lg text-primary">sports_soccer</span>
                Acceso rápido
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {amigos.slice(0, 6).map(amigo => (
                  <Link key={amigo.id} to={`/amigos/${amigo.id}/plantilla`}
                    className="flex items-center gap-3 p-3 bg-surface-dark hover:bg-white/10 border border-border-dark hover:border-primary/40 rounded-xl transition-all group">
                    <Avatar name={amigo.first_name || amigo.username} photo={amigo.profile_photo} size={8} />
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-semibold truncate">{amigo.first_name || amigo.username}</p>
                      <p className="text-xs text-gray-500 group-hover:text-primary transition-colors">Ver plantilla →</p>
                    </div>
                  </Link>
                ))}
              </div>
            </GlassPanel>
          )}
        </div>
      </div>
      <HelpButton title="Guía de Amigos" fields={[
        { label: 'Buscar usuario', description: 'Escribe el nombre de usuario (con o sin @) para encontrar a alguien y enviarle una solicitud de amistad.' },
        { label: 'Solicitud pendiente', description: 'Petición de amistad enviada que está esperando respuesta del otro usuario.' },
        { label: 'Amigos', description: 'Usuarios que aceptaron tu solicitud. Puedes ver sus plantillas públicas.' },
        { label: 'Ver plantilla', description: 'Accede a la plantilla fantasy de un amigo si la tiene configurada como pública.' },
      ]} />
    </div>
  )
}

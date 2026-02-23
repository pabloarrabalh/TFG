import { useEffect, useState } from 'react'
import api from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { useAuth } from '../context/AuthContext'

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

  const [data, setData] = useState({ amigos: [], solicitudes_pendientes: [], solicitudes_enviadas: [] })
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(null)

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
    if (!searchUser.trim()) return
    setSending(true)
    try {
      await api.post('/api/amigos/solicitud/', { username: searchUser.trim() })
      flash('success', `Solicitud enviada a @${searchUser.trim()}`)
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

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <LoadingSpinner size="lg" />
    </div>
  )

  const { amigos, solicitudes_pendientes, solicitudes_enviadas } = data

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black text-white">Mis Amigos</h1>
        <p className="text-gray-400 mt-1">Compara resultados y compite con tus amigos</p>
      </div>

      {message && (
        <div className={`px-4 py-3 rounded-xl text-sm font-semibold ${message.type === 'success' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left: friends list */}
        <div className="xl:col-span-5 space-y-4">
          {/* Send request */}
          <GlassPanel className="p-5">
            <h3 className="text-base font-bold text-white mb-3">Añadir amigo</h3>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Nombre de usuario..."
                value={searchUser}
                onChange={e => setSearchUser(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendRequest()}
                className="flex-1 px-3 py-2 bg-background-dark border border-border-dark text-white rounded-xl focus:outline-none focus:border-primary text-sm"
              />
              <button
                onClick={sendRequest}
                disabled={sending || !searchUser.trim()}
                className="px-4 py-2 bg-primary hover:bg-primary-dark text-black rounded-xl font-bold transition-colors disabled:opacity-60 text-sm"
              >
                {sending ? (
                  <span className="material-symbols-outlined text-base animate-spin">progress_activity</span>
                ) : (
                  <span className="material-symbols-outlined text-base">person_add</span>
                )}
              </button>
            </div>
          </GlassPanel>

          {/* Pending requests received */}
          {solicitudes_pendientes.length > 0 && (
            <GlassPanel className="p-5">
              <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-yellow-400 text-lg">notifications</span>
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
                      <button
                        onClick={() => accept(sol.id)}
                        className="p-1.5 bg-green-500/20 hover:bg-green-500/40 text-green-400 rounded-lg transition-colors"
                        title="Aceptar"
                      >
                        <span className="material-symbols-outlined text-base">check</span>
                      </button>
                      <button
                        onClick={() => reject(sol.id)}
                        className="p-1.5 bg-red-500/20 hover:bg-red-500/40 text-red-400 rounded-lg transition-colors"
                        title="Rechazar"
                      >
                        <span className="material-symbols-outlined text-base">close</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </GlassPanel>
          )}

          {/* Sent requests */}
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

          {/* Friends list */}
          <GlassPanel className="overflow-hidden">
            <div className="p-4 border-b border-white/10">
              <h3 className="text-lg font-black text-white">
                Amigos
                <span className="ml-2 text-sm text-gray-400 font-normal">({amigos.length})</span>
              </h3>
            </div>

            {amigos.length === 0 ? (
              <div className="p-8 text-center">
                <span className="material-symbols-outlined text-4xl text-gray-600 block mb-3">group</span>
                <p className="text-gray-400 text-sm">Aún no tienes amigos</p>
                <p className="text-gray-500 text-xs mt-1">Busca usuarios por nombre para añadirlos</p>
              </div>
            ) : (
              <div className="divide-y divide-white/10">
                {amigos.map((amigo, idx) => (
                  <div key={amigo.id} className="p-4 hover:bg-white/5 transition-colors flex items-center justify-between group">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        <span className="text-base font-black text-gray-400 w-5 text-center">{idx + 1}</span>
                        <Avatar name={amigo.first_name || amigo.username} photo={amigo.profile_photo} size={10} />
                      </div>
                      <div>
                        <p className="font-bold text-white text-sm">{amigo.first_name || amigo.username}</p>
                        <p className="text-xs text-gray-400">@{amigo.username}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeAmigo(amigo.id)}
                      className="text-gray-600 hover:text-red-400 transition-colors p-1 opacity-0 group-hover:opacity-100"
                      title="Eliminar amigo"
                    >
                      <span className="material-symbols-outlined text-base">person_remove</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </GlassPanel>
        </div>

        {/* Right: placeholder stats / coming soon */}
        <div className="xl:col-span-7 space-y-6">
          {/* Coming soon banner */}
          <GlassPanel className="p-8 text-center">
            <div className="bg-gradient-to-r from-purple-600/20 to-pink-600/20 rounded-2xl p-6 border border-purple-500/20">
              <span className="material-symbols-outlined text-5xl text-purple-400 block mb-3">compare_arrows</span>
              <h3 className="text-xl font-bold text-white mb-2">Comparación de ligas</h3>
              <p className="text-gray-400 text-sm">Próximamente podrás comparar tus puntos de fantasy con los de tus amigos jornada a jornada.</p>
            </div>
          </GlassPanel>

          <GlassPanel className="p-8 text-center">
            <div className="bg-gradient-to-r from-yellow-500/20 to-orange-600/20 rounded-2xl p-6 border border-yellow-500/20">
              <span className="material-symbols-outlined text-5xl text-yellow-400 block mb-3">emoji_events</span>
              <h3 className="text-xl font-bold text-white mb-2">Logros y Logros</h3>
              <p className="text-gray-400 text-sm">Desbloquea logros compitiendo con tus amigos. Funcionalidad en desarrollo.</p>
            </div>
          </GlassPanel>

          {/* Summary stats */}
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
        </div>
      </div>
    </div>
  )
}

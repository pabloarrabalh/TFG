import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'
import { useAuth } from '../context/AuthContext'
import HelpButton from '../components/ui/HelpButton'

const BACKEND = 'http://localhost:8000'
const ESTADOS = [
  { value: 'active', label: 'Activo', color: 'bg-green-500' },
  { value: 'away', label: 'Ausente', color: 'bg-gray-500' },
  { value: 'dnd', label: 'No molestar', color: 'bg-yellow-500' },
]

const AVATAR_COUNT = 5

export default function PerfilPage() {
  const { user, refetchUser } = useAuth()

  const [perfil, setPerfil] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  // Notification prefs & plantilla privacy
  const [pref, setPref] = useState('all')
  const [savingPref, setSavingPref] = useState(false)
  const [plantillasPriv, setPlantillasPriv] = useState([])
  const [privLoading, setPrivLoading] = useState(false)

  // Edit form
  const [editOpen, setEditOpen] = useState(false)
  const [editData, setEditData] = useState({ first_name: '', last_name: '', email: '', nickname: '' })

  // Photo modal
  const [photoModal, setPhotoModal] = useState(false)
  const [avatarIdx, setAvatarIdx] = useState(0)
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef()

  useEffect(() => {
    loadPerfil()
  }, [])

  async function loadPerfil() {
    setLoading(true)
    try {
      const res = await api.get('/api/perfil/')
      setPerfil(res.data)
      setPref(res.data.preferencias_notificaciones || 'all')
      setEditData({
        first_name: res.data.first_name || '',
        last_name: res.data.last_name || '',
        email: res.data.email || '',
        nickname: res.data.nickname || '',
      })
    } catch {
      setMessage({ type: 'error', text: 'Error al cargar el perfil' })
    } finally {
      setLoading(false)
    }
    // Load plantilla privacy separately (non-blocking)
    try {
      const res2 = await api.get('/api/plantillas/privacidad/')
      setPlantillasPriv(res2.data.plantillas || [])
    } catch { /* silent */ }
  }

  async function saveProfile() {
    setSaving(true)
    setMessage(null)
    try {
      await api.post('/api/perfil/update/', editData)
      setMessage({ type: 'success', text: 'Perfil actualizado correctamente' })
      setEditOpen(false)
      await loadPerfil()
      await refetchUser()
    } catch (e) {
      const err = e.response?.data
      setMessage({ type: 'error', text: err?.error || 'Error al guardar' })
    } finally {
      setSaving(false)
    }
  }

  async function updateStatus(estado) {
    try {
      await api.post('/api/perfil/status/', { estado })
      setPerfil(prev => ({ ...prev, estado }))
      await refetchUser()
    } catch {
      setMessage({ type: 'error', text: 'Error al actualizar estado' })
    }
  }


  async function deleteFavorite(id) {
    try {
      await api.delete(`/api/favoritos/${id}/`)
      setPerfil(prev => ({
        ...prev,
        favoritos: prev.favoritos.filter(f => f.id !== id)
      }))
    } catch {
      setMessage({ type: 'error', text: 'Error al eliminar favorito' })
    }
  }

  async function useAvatar(idx) {
    setUploading(true)
    try {
      await api.post('/api/perfil/foto/', { default_avatar: `default${idx + 1}` })
      setMessage({ type: 'success', text: 'Avatar actualizado' })
      setPhotoModal(false)
      await loadPerfil()
      await refetchUser()
    } catch {
      setMessage({ type: 'error', text: 'Error al actualizar avatar' })
    } finally {
      setUploading(false)
    }
  }

  async function uploadPhoto(file) {
    if (!file) return
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('foto', file)
      await api.post('/api/perfil/foto/', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setMessage({ type: 'success', text: 'Foto actualizada' })
      setPhotoModal(false)
      await loadPerfil()
      await refetchUser()
    } catch {
      setMessage({ type: 'error', text: 'Error al subir foto' })
    } finally {
      setUploading(false)
    }
  }

  async function updatePref(value) {
    setSavingPref(true)
    try {
      await api.post('/api/perfil/preferencias-notificaciones/', { preferencia: value })
      setPref(value)
      setMessage({ type: 'success', text: 'Preferencias actualizadas' })
    } catch {
      setMessage({ type: 'error', text: 'Error al guardar preferencias' })
    } finally {
      setSavingPref(false)
    }
  }

  async function togglePrivacidad(id) {
    setPrivLoading(true)
    try {
      const res = await api.post(`/api/plantilla/${id}/privacidad/`)
      setPlantillasPriv(prev => prev.map(p =>
        p.id === id ? { ...p, privacidad: res.data.privacidad } : p
      ))
    } catch {
      setMessage({ type: 'error', text: 'Error al cambiar privacidad' })
    } finally {
      setPrivLoading(false)
    }
  }

  async function setPredeterminada(id) {
    setPrivLoading(true)
    try {
      await api.post(`/api/plantilla/${id}/predeterminada/`)
      // Update local state: solo una puede ser predeterminada
      setPlantillasPriv(prev => prev.map(p => ({ ...p, predeterminada: p.id === id })))
      setMessage({ type: 'success', text: 'Plantilla predeterminada actualizada' })
    } catch {
      setMessage({ type: 'error', text: 'Error al establecer predeterminada' })
    } finally {
      setPrivLoading(false)
    }
  }

  const estadoActual = ESTADOS.find(e => e.value === perfil?.estado) || ESTADOS[0]
  const avatarSrc = (idx) => `${BACKEND}/static/logos/default${idx + 1}.png`

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <LoadingSpinner size="lg" />
    </div>
  )

  const initials = `${perfil?.first_name?.[0] || ''}${perfil?.last_name?.[0] || ''}`.toUpperCase() || '?'
  const rawPhoto = perfil?.profile_photo || perfil?.foto_url
  const profilePic = rawPhoto
    ? (rawPhoto.startsWith('http') ? rawPhoto : `${BACKEND}${rawPhoto}`)
    : `https://ui-avatars.com/api/?name=${encodeURIComponent((perfil?.first_name || '') + '+' + (perfil?.last_name || ''))}&background=39ff14&color=050505&bold=true&size=256`

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {message && (
        <div className={`px-4 py-3 rounded-xl text-sm font-semibold ${message.type === 'success' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
          {message.text}
        </div>
      )}

      {/* Profile header */}
      <GlassPanel className="p-8">
        <div className="flex flex-col sm:flex-row items-center gap-6">
          {/* Avatar */}
          <div className="relative flex-shrink-0">
            <div
              className="size-32 rounded-2xl bg-cover bg-center bg-no-repeat ring-2 ring-primary shadow-lg"
              style={{ backgroundImage: `url("${profilePic}")` }}
            />
            <button
              onClick={() => setPhotoModal(true)}
              className="absolute bottom-0 right-0 bg-primary text-black p-2.5 rounded-full hover:bg-primary-dark transition-colors shadow-lg"
            >
              <span className="material-symbols-outlined text-lg">photo_camera</span>
            </button>
          </div>

          {/* Info */}
          <div className="flex-1 text-center sm:text-left">
            <h1 className="text-3xl sm:text-4xl font-black text-white mb-2">
              {perfil?.first_name} {perfil?.last_name}
            </h1>
            {perfil?.nickname && (
              <p className="text-primary font-semibold mb-2">@{perfil.nickname}</p>
            )}
            <div className="space-y-1.5 mb-5">
              <div className="flex items-center gap-2 text-gray-400 justify-center sm:justify-start">
                <span className="material-symbols-outlined text-lg">mail</span>
                <span className="text-sm">{perfil?.email}</span>
              </div>
              {perfil?.date_joined && (
                <div className="flex items-center gap-2 text-gray-400 justify-center sm:justify-start">
                  <span className="material-symbols-outlined text-lg">calendar_today</span>
                  <span className="text-sm">Se unió el {new Date(perfil.date_joined).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}</span>
                </div>
              )}
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <button
                onClick={() => setEditOpen(true)}
                className="flex items-center justify-center gap-2 px-5 py-2 bg-primary/20 border border-primary/50 rounded-lg hover:bg-primary/30 transition-colors font-semibold text-primary text-sm"
              >
                <span className="material-symbols-outlined text-lg">edit</span>
                Editar perfil
              </button>
            </div>
          </div>
        </div>
      </GlassPanel>

      {/* Estado */}
      <GlassPanel className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white">Mi Estado</h2>
          <select
            value={perfil?.estado || 'active'}
            onChange={e => updateStatus(e.target.value)}
            className="select-custom text-sm"
          >
            {ESTADOS.map(e => (
              <option key={e.value} value={e.value}>{e.label}</option>
            ))}
          </select>
        </div>
      </GlassPanel>

      {/* Equipos favoritos */}
      <GlassPanel className="p-6">
        <div className="flex items-center gap-3 mb-5">
          <span className="material-symbols-outlined text-2xl text-primary">favorite</span>
          <h2 className="text-xl font-bold text-white">Equipos Favoritos</h2>
        </div>

        {perfil?.favoritos?.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {perfil.favoritos.map(fav => (
              <div key={fav.id} className="group relative">
                <button
                  onClick={() => deleteFavorite(fav.id)}
                  className="absolute top-2 right-2 size-7 bg-gray-600 hover:bg-red-600 rounded-full flex items-center justify-center transition-colors z-10"
                >
                  <span className="material-symbols-outlined text-base text-white">close</span>
                </button>
                <Link to={`/equipo/${encodeURIComponent(fav.equipo_nombre)}`}>
                  <div className="glass-panel rounded-xl p-5 hover:border-primary/50 hover:shadow-neon transition-all cursor-pointer">
                    <div className="flex items-center gap-4">
                      <TeamShield escudo={fav.equipo_escudo} nombre={fav.equipo_nombre} size={56} className="size-14" />
                      <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-white group-hover:text-primary transition-colors truncate">
                          {fav.equipo_nombre}
                        </h3>
                      </div>
                    </div>
                  </div>
                </Link>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-10">
            <span className="material-symbols-outlined text-5xl text-gray-600 block mb-3">favorite_border</span>
            <p className="text-gray-400 mb-4">Aún no tienes equipos favoritos</p>
            <Link to="/favoritos/select" className="inline-flex items-center gap-2 px-5 py-2 bg-primary text-black rounded-lg hover:bg-primary-dark transition-colors font-semibold text-sm">
              <span className="material-symbols-outlined text-lg">add</span>
              Agregar equipos
            </Link>
          </div>
        )}
      </GlassPanel>

      {/* ── Notification preferences ── */}
      <GlassPanel className="p-6">
        <div className="flex items-center gap-3 mb-5">
          <span className="material-symbols-outlined text-2xl text-yellow-400">notifications</span>
          <h2 className="text-xl font-bold text-white">Preferencias de notificaciones</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { value: 'all',     label: 'Todas',           icon: 'notifications_active', color: 'text-green-400' },
            { value: 'friends', label: 'Solo solicitudes', icon: 'person_add',           color: 'text-blue-400'  },
            { value: 'events',  label: 'Solo eventos',    icon: 'sports_soccer',        color: 'text-orange-400'},
            { value: 'none',    label: 'Ninguna',         icon: 'notifications_off',    color: 'text-gray-400'  },
          ].map(opt => (
            <button key={opt.value} onClick={() => updatePref(opt.value)} disabled={savingPref}
              className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${pref === opt.value ? 'border-primary bg-primary/10' : 'border-border-dark bg-white/[0.03] hover:bg-white/10'}`}>
              <span className={`material-symbols-outlined text-2xl ${pref === opt.value ? 'text-primary' : opt.color}`}>{opt.icon}</span>
              <span className={`text-xs font-bold text-center ${pref === opt.value ? 'text-primary' : 'text-gray-300'}`}>{opt.label}</span>
            </button>
          ))}
        </div>
      </GlassPanel>

      {/* ── Plantilla privacy ── */}
      {plantillasPriv.length > 0 && (
        <GlassPanel className="p-6">
          <div className="flex items-center gap-3 mb-5">
            <span className="material-symbols-outlined text-2xl text-primary">lock</span>
            <h2 className="text-xl font-bold text-white">Configuración de plantillas</h2>
          </div>
          <p className="text-gray-400 text-sm mb-4">
            Controla la privacidad de tus plantillas y elige cuál recibe notificaciones de eventos de jugadores (goles, asistencias, tarjetas).
          </p>
          <div className="space-y-3">
            {plantillasPriv.map(p => {
              const isPublic = p.privacidad === 'publica'
              const isDefault = p.predeterminada
              return (
                <div key={p.id} className={`flex items-center justify-between p-4 rounded-xl border transition-all ${isDefault ? 'bg-primary/10 border-primary/50' : 'bg-surface-dark border-border-dark'}`}>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setPredeterminada(p.id)}
                      disabled={privLoading || isDefault}
                      className={`p-1.5 rounded-lg transition-colors ${isDefault ? 'text-yellow-400' : 'text-gray-500 hover:text-yellow-400 hover:bg-yellow-400/10'}`}
                      title={isDefault ? 'Plantilla para notificaciones' : 'Establecer para notificaciones'}
                    >
                      <span className="material-symbols-outlined text-xl">{isDefault ? 'star' : 'star_outline'}</span>
                    </button>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-white font-semibold text-sm">{p.nombre}</p>
                        {isDefault && (
                          <span className="text-[10px] bg-yellow-400/20 text-yellow-400 px-2 py-0.5 rounded-full font-bold">
                            Notificaciones
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500">{isDefault ? 'Recibirás alertas de estos jugadores' : 'Clic en ★ para activar notificaciones'}</p>
                    </div>
                  </div>
                  <button onClick={() => togglePrivacidad(p.id)} disabled={privLoading}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${isPublic ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30' : 'bg-gray-700/50 text-gray-400 hover:bg-gray-600/50'}`}>
                    <span className="material-symbols-outlined text-base">{isPublic ? 'lock_open' : 'lock'}</span>
                    {isPublic ? 'Pública' : 'Privada'}
                  </button>
                </div>
              )
            })}
          </div>
        </GlassPanel>
      )}

      {/* Quick stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <GlassPanel className="p-5 text-center">
          <div className="text-3xl font-black text-primary mb-1">{perfil?.favoritos?.length || 0}</div>
          <p className="text-gray-400 text-sm">Equipos Favoritos</p>
        </GlassPanel>
        <GlassPanel className="p-5 text-center">
          <div className="text-lg font-black text-white mb-1">
            {perfil?.date_joined ? new Date(perfil.date_joined).toLocaleDateString('es-ES', { month: 'short', year: 'numeric' }) : '—'}
          </div>
          <p className="text-gray-400 text-sm">Miembro desde</p>
        </GlassPanel>
        <GlassPanel className="p-5 text-center">
          <div className="flex items-center justify-center gap-2 mb-1">
            <span className={`size-2.5 rounded-full ${estadoActual.color} animate-pulse`} />
            <span className={`text-lg font-black`} style={{ color: estadoActual.value === 'active' ? '#4ade80' : estadoActual.value === 'away' ? '#9ca3af' : '#facc15' }}>
              {estadoActual.label}
            </span>
          </div>
          <p className="text-gray-400 text-sm">Estado actual</p>
        </GlassPanel>
      </div>

      {/* Edit profile modal */}
      {editOpen && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-surface-dark rounded-2xl w-full max-w-md border border-border-dark p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-xl font-bold text-white">Editar perfil</h3>
              <button onClick={() => setEditOpen(false)} className="text-gray-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="space-y-4">
              {[
                { key: 'first_name', label: 'Nombre' },
                { key: 'last_name', label: 'Apellidos' },
                { key: 'email', label: 'Email', type: 'email' },
                { key: 'nickname', label: 'Nickname' },
              ].map(({ key, label, type = 'text' }) => (
                <div key={key}>
                  <label className="block text-sm font-semibold text-gray-300 mb-1.5">{label}</label>
                  <input
                    type={type}
                    value={editData[key]}
                    onChange={e => setEditData(prev => ({ ...prev, [key]: e.target.value }))}
                    className="w-full px-4 py-2.5 bg-background-dark border border-border-dark text-white rounded-xl focus:outline-none focus:border-primary text-sm"
                  />
                </div>
              ))}
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setEditOpen(false)}
                className="flex-1 px-4 py-2.5 bg-surface-dark border border-border-dark text-white rounded-xl font-semibold hover:bg-white/5 transition-colors text-sm"
              >
                Cancelar
              </button>
              <button
                onClick={saveProfile}
                disabled={saving}
                className="flex-1 px-4 py-2.5 bg-primary hover:bg-primary-dark text-black rounded-xl font-bold transition-colors disabled:opacity-60 text-sm"
              >
                {saving ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Photo modal */}
      {photoModal && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-surface-dark rounded-2xl w-full max-w-lg border border-border-dark p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-xl font-bold text-white">Cambiar foto de perfil</h3>
              <button onClick={() => setPhotoModal(false)} className="text-gray-400 hover:text-white">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            {/* Avatar gallery */}
            <div className="mb-6">
              <h4 className="text-base font-semibold text-white mb-4">Selecciona un avatar</h4>
              <div className="flex items-center justify-center gap-4">
                <button
                  onClick={() => setAvatarIdx(i => (i - 1 + AVATAR_COUNT) % AVATAR_COUNT)}
                  className="p-2 bg-gray-700 hover:bg-primary hover:text-black rounded-lg transition-colors"
                >
                  <span className="material-symbols-outlined">chevron_left</span>
                </button>
                <div className="size-28 rounded-2xl overflow-hidden border-2 border-primary flex-shrink-0 bg-gray-800">
                  <img
                    src={avatarSrc(avatarIdx)}
                    alt="Avatar"
                    className="w-full h-full object-contain"
                    onError={e => { e.target.src = `https://ui-avatars.com/api/?name=A${avatarIdx + 1}&background=39ff14&color=050505&bold=true&size=256` }}
                  />
                </div>
                <button
                  onClick={() => setAvatarIdx(i => (i + 1) % AVATAR_COUNT)}
                  className="p-2 bg-gray-700 hover:bg-primary hover:text-black rounded-lg transition-colors"
                >
                  <span className="material-symbols-outlined">chevron_right</span>
                </button>
              </div>
              <p className="text-center text-gray-400 text-sm mt-3">{avatarIdx + 1} / {AVATAR_COUNT}</p>
              <button
                onClick={() => useAvatar(avatarIdx)}
                disabled={uploading}
                className="w-full mt-4 px-4 py-2.5 bg-primary hover:bg-primary-dark text-black rounded-xl font-bold transition-colors disabled:opacity-60 text-sm"
              >
                {uploading ? 'Aplicando...' : 'Usar este avatar'}
              </button>
            </div>

            <div className="flex items-center gap-3 my-4">
              <div className="flex-1 h-px bg-border-dark" />
              <span className="text-gray-400 text-sm">O</span>
              <div className="flex-1 h-px bg-border-dark" />
            </div>

            {/* Custom upload */}
            <div>
              <h4 className="text-base font-semibold text-white mb-4">Sube tu propia foto</h4>
              <div
                className="border-2 border-dashed border-border-dark rounded-xl p-6 text-center hover:border-primary transition-colors cursor-pointer"
                onClick={() => fileRef.current?.click()}
              >
                <span className="material-symbols-outlined text-4xl text-gray-600 block mb-2">cloud_upload</span>
                <p className="text-gray-400 text-sm">Haz clic para seleccionar una foto</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={e => uploadPhoto(e.target.files[0])}
                />
              </div>
            </div>
          </div>
        </div>
      )}
      <HelpButton title="Guía del perfil" fields={[
        { label: 'Nickname', description: 'Alias visible para otros usuarios. Puede ser distinto al nombre de usuario (@usuario).' },
        { label: 'Estado', description: 'Indicador de disponibilidad: Activo (verde), Ausente (gris) o No molestar (amarillo).' },
        { label: 'Equipo favorito', description: 'Equipo preferido que aparece destacado en el menú y la clasificación.' },
        { label: 'Notificaciones', description: 'Activa o desactiva los avisos de solicitudes de amistad y eventos de jugadores de tu plantilla.' },
        { label: 'Privacidad plantilla', description: 'Controla si tus amigos pueden ver tu plantilla fantasy (Pública) o no (Privada).' },
        { label: 'Plantilla predeterminada', description: 'Plantilla usada para generar notificaciones de eventos de jugadores.' },
      ]} />
    </div>
  )
}

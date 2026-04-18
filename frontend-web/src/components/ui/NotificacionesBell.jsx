import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../../services/apiClient'
import { BACKEND_URL } from '../../config/backend'
import { useAuth } from '../../context/AuthContext'

const WS_URL = `${BACKEND_URL.startsWith('https:') ? 'wss:' : 'ws:'}//${new URL(BACKEND_URL).host}/ws/notificaciones/`
const RECONNECT_DELAY_MS = 5000

const TIPO_CFG = {
  solicitud_amistad: {
    icon: 'person_add',
    color: 'text-blue-400',
    bg: 'bg-blue-500/20',
  },
  evento_jugador: {
    icon: 'sports_soccer',
    color: 'text-green-400',
    bg: 'bg-green-500/20',
  },
}

function timeAgo(dateStr) {
  if (!dateStr) return 'ahora'
  const t = new Date(dateStr)
  if (isNaN(t.getTime())) return 'ahora'
  const diff = Date.now() - t.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'ahora'
  if (min < 60) return `hace ${min}m`
  const h = Math.floor(min / 60)
  if (h < 24) return `hace ${h}h`
  return `hace ${Math.floor(h / 24)}d`
}

export default function NotificacionesBell() {
  const [notifs, setNotifs] = useState([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const panelRef = useRef(null)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const { user } = useAuth()

  // ── WebSocket ──────────────────────────────────────────────────────
  const connectWS = useCallback(() => {
    if (!user) return
    if (wsRef.current && wsRef.current.readyState < 2) return // already open/connecting

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'init') {
          setNotifs(msg.notificaciones || [])
          setUnread(msg.no_leidas || 0)
        } else if (msg.type === 'nueva') {
          setNotifs(prev => {
            const exists = prev.some(n => n.id === msg.notificacion.id)
            return exists ? prev : [msg.notificacion, ...prev].slice(0, 50)
          })
          setUnread(msg.no_leidas || 0)
        }
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      if (!user) return
      reconnectTimer.current = setTimeout(connectWS, RECONNECT_DELAY_MS)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [user])

  useEffect(() => {
    connectWS()
    return () => {
      clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect on intentional close
        wsRef.current.close()
      }
    }
  }, [connectWS])

  // Request fresh data from server via WS when panel opens
  useEffect(() => {
    if (open && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'fetch' }))
    }
  }, [open])

  // Close on outside click
  useEffect(() => {
    function handle(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  // ── Helpers: refresh via WS after REST mutations ────────────────────
  function wsRefresh() {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'fetch' }))
    }
  }

  // ── Actions ────────────────────────────────────────────────────────
  async function markRead(id) {
    try {
      await api.post(`/api/notificaciones/${id}/leer/`)
      setNotifs(prev => prev.map(n => n.id === id ? { ...n, leida: true } : n))
      setUnread(c => Math.max(0, c - 1))
    } catch { /* silent */ }
  }

  async function markAllRead() {
    try {
      await api.post('/api/notificaciones/leer-todas/')
      setNotifs(prev => prev.map(n => ({ ...n, leida: true })))
      setUnread(0)
    } catch { /* silent */ }
  }

  async function deleteNotif(id) {
    try {
      await api.post(`/api/notificaciones/${id}/borrar/`)
      setNotifs(prev => prev.filter(n => n.id !== id))
      setUnread(prev => Math.max(0, prev - 1))
    } catch { /* silent */ }
  }

  async function clearAll() {
    try {
      await api.post('/api/notificaciones/borrar-todas/')
      setNotifs([])
      setUnread(0)
    } catch { /* silent */ }
  }

  async function acceptFriendRequest(notif) {
    const solicitudId = notif.datos?.solicitud_id
    if (!solicitudId) return
    setLoading(true)
    try {
      await api.post(`/api/amigos/aceptar/${solicitudId}/`)
      await markRead(notif.id)
      wsRefresh()
    } catch { /* silent */ }
    setLoading(false)
  }

  async function rejectFriendRequest(notif) {
    const solicitudId = notif.datos?.solicitud_id
    if (!solicitudId) return
    setLoading(true)
    try {
      await api.post(`/api/amigos/rechazar/${solicitudId}/`)
      await markRead(notif.id)
      wsRefresh()
    } catch { /* silent */ }
    setLoading(false)
  }


  return (
    <div ref={panelRef} className="relative">
      {/* Bell button */}
      <button
        onClick={() => setOpen(o => !o)}
        className={`relative p-2 rounded-xl transition-colors ${open ? 'bg-white/15 text-white' : 'text-gray-400 hover:text-white hover:bg-white/10'}`}
        title="Notificaciones"
      >
        <span className="material-symbols-outlined text-xl">
          {unread > 0 ? 'notifications_active' : 'notifications'}
        </span>
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-black rounded-full flex items-center justify-center px-1 leading-none">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute right-0 top-12 w-[480px] z-50 bg-[#1a1d23] border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
          {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-white/5">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-primary text-2xl">notifications</span>
              <span className="text-white font-bold text-lg">Notificaciones</span>
              {unread > 0 && (
                <span className="bg-red-500/20 text-red-400 text-sm font-black px-2.5 py-1 rounded-full">{unread} nuevas</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {unread > 0 && (
                <button onClick={markAllRead}
                  className="text-sm text-gray-400 hover:text-primary transition-colors font-medium">
                  Marcar todas
                </button>
              )}
              <button onClick={clearAll}
                className="text-sm text-gray-400 hover:text-primary transition-colors font-medium">
                Limpiar
              </button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-[600px] overflow-y-auto">
            {notifs.length === 0
              ? (
                <div className="py-16 text-center">
                  <span className="material-symbols-outlined text-6xl text-gray-600 block mb-4">notifications_off</span>
                  <p className="text-gray-500 text-base">Sin notificaciones</p>
                </div>
              )
              : notifs.map(notif => {
                  const cfg = TIPO_CFG[notif.tipo] || TIPO_CFG.evento_jugador
                  const isFriendReq = notif.tipo === 'solicitud_amistad'
                  const pendiente = notif.datos?.estado === 'pendiente'
                  return (
                    <div key={notif.id}
                      className={`flex gap-4 px-5 py-4 border-b border-white/5 transition-colors ${notif.leida ? 'opacity-60' : 'bg-white/[0.03]'}`}>
                      {/* Icon */}
                      <div className={`flex-shrink-0 size-12 ${cfg.bg} rounded-xl flex items-center justify-center mt-0.5`}>
                        <span className={`material-symbols-outlined text-2xl ${cfg.color}`}>{cfg.icon}</span>
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-semibold leading-tight">{notif.titulo}</p>
                        <p className="text-gray-400 text-sm mt-1 leading-snug">{notif.mensaje}</p>
                        <p className="text-gray-600 text-xs mt-1.5">{timeAgo(notif.creada_en)}</p>

                        {/* Friend request actions */}
                        {isFriendReq && pendiente && !notif.leida && (
                          <div className="flex gap-2 mt-3">
                            <button onClick={() => acceptFriendRequest(notif)} disabled={loading}
                              className="flex items-center gap-1 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/40 text-green-400 rounded-lg text-sm font-bold transition-colors disabled:opacity-60">
                              <span className="material-symbols-outlined text-sm">check</span>
                              Aceptar
                            </button>
                            <button onClick={() => rejectFriendRequest(notif)} disabled={loading}
                              className="flex items-center gap-1 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/40 text-red-400 rounded-lg text-sm font-bold transition-colors disabled:opacity-60">
                              <span className="material-symbols-outlined text-sm">close</span>
                              Rechazar
                            </button>
                          </div>
                        )}
                        {isFriendReq && !pendiente && (
                          <span className="mt-2 inline-block text-xs text-gray-500">
                            {notif.datos?.estado === 'aceptada' ? '✓ Aceptada' : '✗ Rechazada'}
                          </span>
                        )}
                      </div>

                      {/* Actions: mark read / delete */}
                      <div className="flex flex-col gap-2 items-end">
                        {!notif.leida && (
                          <button onClick={() => markRead(notif.id)}
                            className="flex-shrink-0 text-gray-600 hover:text-gray-300 transition-colors mt-0.5" title="Marcar como leída">
                            <span className="material-symbols-outlined text-xl">close</span>
                          </button>
                        )}
                        <button onClick={() => deleteNotif(notif.id)} title="Borrar" className="text-gray-600 hover:text-red-400">
                          <span className="material-symbols-outlined text-xl">delete</span>
                        </button>
                      </div>
                    </div>
                  )
                })
            }
          </div>
        </div>
      )}
    </div>
  )
}

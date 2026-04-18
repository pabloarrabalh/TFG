import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useState, useEffect, useRef } from 'react'
import { backendUrl } from '../../config/backend'

async function cargarEventosJornada(jornada) {
  try {
    const res = await fetch(backendUrl(`/api/plantilla-notificaciones/${jornada}/`), { credentials: 'include' })
    if (!res.ok) return
    // Los eventos se crean como notificaciones bell en el backend automáticamente
  } catch {}
}

const NAV_ITEMS = [
  { path: '/menu', label: 'Inicio', icon: 'home', key: 'menu' },
  { path: '/mi-plantilla', label: 'Mi Plantilla', icon: 'groups', key: 'mi-plantilla' },
  { path: '/clasificacion', label: 'Liga', icon: 'sports_soccer', key: 'liga' },
  { path: '/equipos', label: 'Equipos', icon: 'shield', key: 'equipos' },
  { path: '/estadisticas', label: 'Estadísticas', icon: 'bar_chart', key: 'estadisticas' },
  { path: '/amigos', label: 'Amigos', icon: 'people', key: 'amigos' },
]

export default function Sidebar({ open, onClose }) {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()
  const [jornada, setJornada] = useState(6)
  const [inputJornada, setInputJornada] = useState('6')
  const [showJornadaInput, setShowJornadaInput] = useState(false)

  // Cargar jornada del localStorage
  useEffect(() => {
    const saved = localStorage.getItem('jornada_global')
    if (saved) {
      const num = parseInt(saved)
      setJornada(num)
      setInputJornada(String(num))
    }
  }, [])

  // Guardar jornada en localStorage
  const updateJornada = (newJornada) => {
    if (newJornada >= 1 && newJornada <= 38) {
      const prev = jornada
      setJornada(newJornada)
      setInputJornada(String(newJornada))
      localStorage.setItem('jornada_global', String(newJornada))
      window.dispatchEvent(new CustomEvent('jornadaChanged', { detail: { jornada: newJornada } }))
      fetch(backendUrl(`/api/menu/top-jugadores/?jornada=${newJornada + 1}`)).catch(() => {})
      if (newJornada > prev) cargarEventosJornada(newJornada)
    }
  }

  const handleManualInput = () => {
    const num = parseInt(inputJornada)
    if (!isNaN(num)) {
      updateJornada(num)
      setShowJornadaInput(false)
    }
  }

  const isActive = (path) => pathname === path || pathname.startsWith(path + '/')

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        id="tour-sidebar"
        className={`sidebar ${open ? '' : 'sidebar-hidden'} fixed flex flex-col w-72 h-full bg-surface-dark border-r border-border-dark z-50`}
      >
        <nav className="flex-1 px-4 py-8 space-y-2 overflow-y-auto scrollbar-hide">
          {/* Selector de Jornada Global */}
          <div id="tour-sidebar-jornada" className="mb-6 p-4 bg-primary/10 border border-primary/30 rounded-xl">
            <div className="flex items-center gap-2 mb-3">
              <span className="material-symbols-outlined text-primary text-lg">schedule</span>
              <h3 className="text-xs font-bold text-primary uppercase tracking-wide">Jornada</h3>
            </div>
            
            {!showJornadaInput ? (
              <>
                <div className="flex items-center gap-2 mb-3">
                  <button
                    onClick={() => updateJornada(Math.max(1, jornada - 1))}
                    className="p-1.5 hover:bg-primary/20 rounded-lg transition-all"
                    title="Jornada anterior"
                  >
                    <span className="material-symbols-outlined text-sm">chevron_left</span>
                  </button>
                  <div className="flex-1 text-center">
                    <div className="text-2xl font-black text-primary">{jornada}</div>
                    <div className="text-xs text-gray-400">/ 38</div>
                  </div>
                  <button
                    onClick={() => updateJornada(Math.min(38, jornada + 1))}
                    className="p-1.5 hover:bg-primary/20 rounded-lg transition-all"
                    title="Próxima jornada"
                  >
                    <span className="material-symbols-outlined text-sm">chevron_right</span>
                  </button>
                </div>
                <button
                  onClick={() => setShowJornadaInput(true)}
                  className="w-full text-xs text-primary hover:text-primary/80 font-semibold py-1 transition-colors"
                >
                  Introducir jornada
                </button>
              </>
            ) : (
              <div className="flex gap-2">
                <input
                  type="number"
                  min="1"
                  max="38"
                  value={inputJornada}
                  onChange={(e) => setInputJornada(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleManualInput()}
                  className="flex-1 px-2 py-1.5 bg-background-dark border border-primary/30 text-white rounded text-sm focus:outline-none focus:border-primary"
                  autoFocus
                />
                <button
                  onClick={handleManualInput}
                  className="px-2 py-1.5 bg-primary hover:bg-primary/80 text-black rounded font-bold text-xs transition-all"
                >
                  OK
                </button>
              </div>
            )}
          </div>

          {NAV_ITEMS.map(({ path, label, icon, key }) => (
            <Link
              key={key}
              id={`tour-sidebar-${key}`}
              to={path}
              onClick={() => { if (window.innerWidth < 1024) onClose() }}
              className={`flex items-center gap-4 px-4 py-3.5 rounded-xl transition-all group ${
                isActive(path) ? 'nav-link-active' : 'nav-link'
              }`}
            >
              <span className={`material-symbols-outlined transition-colors ${
                isActive(path) ? '' : 'group-hover:text-primary'
              }`}>
                {icon}
              </span>
              <span className="text-sm tracking-wide">{label}</span>
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-border-dark">
          {user ? (
            <button
              onClick={() => logout().then(onClose)}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 rounded-xl transition-all font-medium shadow-lg text-sm"
            >
              <span className="material-symbols-outlined">logout</span>
              Salir
            </button>
          ) : (
            <Link
              to="/login"
              onClick={onClose}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-gradient-to-r from-primary to-green-500 hover:from-green-500 hover:to-primary rounded-xl font-medium text-sm text-black shadow-lg transition-all"
            >
              <span className="material-symbols-outlined">login</span>
              Iniciar Sesión
            </Link>
          )}
        </div>
      </aside>
    </>
  )
}

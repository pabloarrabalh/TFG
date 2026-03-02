import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import apiClient from '../../services/apiClient'
import NotificacionesBell from '../ui/NotificacionesBell'

const BACKEND = 'http://localhost:8000'

export default function Header({ onToggleSidebar }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [showResults, setShowResults] = useState(false)
  const dropdownRef = useRef(null)
  const searchRef = useRef(null)
  const searchTimer = useRef(null)

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setDropdownOpen(false)
      if (searchRef.current && !searchRef.current.contains(e.target)) setShowResults(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleSearch = (e) => {
    const q = e.target.value
    setSearchQuery(q)
    clearTimeout(searchTimer.current)
    if (q.trim().length < 3) { setShowResults(false); setSearchResults([]); return }
    searchTimer.current = setTimeout(async () => {
      try {
        const { data } = await apiClient.get(`/api/buscar/?q=${encodeURIComponent(q)}`)
        setSearchResults(data.results || [])
        setShowResults(true)
      } catch { setShowResults(false) }
    }, 300)
  }

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const profilePhotoUrl = user?.profile_photo
    ? (user.profile_photo.startsWith('http') ? user.profile_photo : `${BACKEND}${user.profile_photo}`)
    : null

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between h-16 px-6 bg-surface-dark/80 backdrop-blur-md border-b border-border-dark shrink-0">
      {/* Left: hamburger + brand */}
      <div className="flex items-center gap-4">
        <button
          onClick={onToggleSidebar}
          className="flex items-center justify-center w-9 h-9 rounded-lg hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
          aria-label="Toggle sidebar"
        >
          <span className="material-symbols-outlined">menu</span>
        </button>
        <Link to="/menu" className="flex items-center gap-2 font-display font-black text-white hover:text-primary transition-colors">
          <span className="material-symbols-outlined text-primary text-2xl">sports_soccer</span>
          <span className="text-lg tracking-tight">LigaMaster</span>
        </Link>
      </div>

      {/* Center: search */}
      <div className="hidden md:block relative w-96" ref={searchRef}>
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-lg select-none">search</span>
          <input
            type="text"
            placeholder="Buscar jugador o equipo..."
            value={searchQuery}
            onChange={handleSearch}
            className="w-full bg-surface-dark-lighter border border-border-dark rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary/50 transition-colors"
          />
        </div>
        {showResults && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-surface-dark border border-border-dark rounded-xl shadow-2xl overflow-hidden z-50 max-h-96 overflow-y-auto scrollbar-hide">
            {searchResults.length > 0 ? searchResults.map((r, i) => (
              <Link
                key={i}
                to={r.url}
                onClick={() => setShowResults(false)}
                className="flex items-center gap-3 px-4 py-3 hover:bg-surface-dark-lighter transition-colors border-b border-border-dark last:border-b-0"
              >
                <span className="material-symbols-outlined text-primary">{r.type === 'jugador' ? 'person' : 'shield'}</span>
                <div>
                  <p className="text-sm font-semibold text-white">{r.nombre}</p>
                  <p className="text-xs text-gray-400">{r.type === 'jugador' ? `Jugador${r.posicion ? ' • ' + r.posicion : ''}` : 'Equipo'}</p>
                </div>
              </Link>
            )) : (
              <p className="px-4 py-6 text-center text-gray-400 text-sm">No hay resultados</p>
            )}
          </div>
        )}
      </div>

      {/* Right: bell + user */}
      <div className="flex items-center gap-2">
        {user && <NotificacionesBell />}
        {user ? (
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen((o) => !o)}
            className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors"
          >
            {profilePhotoUrl ? (
              <img src={profilePhotoUrl} alt="avatar" className="w-8 h-8 rounded-full object-cover border border-border-dark" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-primary/20 border border-primary/40 flex items-center justify-center">
                <span className="text-primary text-xs font-bold">{(user.first_name || user.username || '?')[0].toUpperCase()}</span>
              </div>
            )}
            <div className="hidden md:block text-left">
              <p className="text-sm font-bold text-white leading-none">{user.nickname || user.first_name || user.username}</p>
              <p className="text-xs mt-0.5" style={{ color: user.estado === 'active' ? '#4ade80' : user.estado === 'away' ? '#9ca3af' : '#facc15' }}>
              {user.estado === 'active' ? 'Activo' : user.estado === 'away' ? 'Ausente' : user.estado === 'dnd' ? 'No molestar' : 'Activo'}
            </p>
            </div>
            <span className="material-symbols-outlined text-gray-400 text-sm">expand_more</span>
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 top-full mt-2 w-56 bg-surface-dark border border-border-dark rounded-xl shadow-2xl overflow-hidden z-50 py-1">
              <Link to="/perfil" onClick={() => setDropdownOpen(false)} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-dark-lighter text-gray-300 hover:text-white transition-colors">
                <span className="material-symbols-outlined text-lg">person</span>
                <span className="text-sm font-medium">Mi perfil</span>
              </Link>
              <Link to="/mi-plantilla" onClick={() => setDropdownOpen(false)} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-dark-lighter text-gray-300 hover:text-white transition-colors">
                <span className="material-symbols-outlined text-lg">groups</span>
                <span className="text-sm font-medium">Mi Plantilla</span>
              </Link>
              <div className="border-t border-border-dark my-1" />
              <button onClick={handleLogout} className="w-full flex items-center gap-3 px-4 py-3 hover:bg-red-600/10 text-gray-300 hover:text-red-500 transition-colors">
                <span className="material-symbols-outlined text-lg">logout</span>
                <span className="text-sm font-medium">Cerrar sesión</span>
              </button>
            </div>
          )}
        </div>
      ) : (
          <Link to="/login" className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-primary to-green-500 hover:from-green-500 hover:to-primary rounded-lg transition-all font-bold text-sm text-black shadow-neon">
            <span className="material-symbols-outlined text-sm">login</span>
            <span>Iniciar Sesión</span>
          </Link>
        )}
      </div>
    </header>
  )
}

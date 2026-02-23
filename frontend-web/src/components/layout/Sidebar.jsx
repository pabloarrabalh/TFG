import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const NAV_ITEMS = [
  { path: '/menu', label: 'Inicio', icon: 'home', key: 'menu' },
  { path: '/mi-plantilla', label: 'Mi Plantilla', icon: 'groups', key: 'mi-plantilla' },
  { path: '/clasificacion', label: 'Liga', icon: 'sports_soccer', key: 'liga' },
  { path: '/equipos', label: 'Equipos', icon: 'shield', key: 'equipos' },
  { path: '/jugador', label: 'Estadísticas', icon: 'bar_chart', key: 'estadisticas' },
  { path: '/amigos', label: 'Amigos', icon: 'people', key: 'amigos' },
]

export default function Sidebar({ open, onClose }) {
  const { pathname } = useLocation()
  const { user, logout } = useAuth()

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
        className={`sidebar ${open ? '' : 'sidebar-hidden'} fixed flex flex-col w-72 h-full bg-surface-dark border-r border-border-dark z-40`}
      >
        <nav className="flex-1 px-4 py-8 space-y-2 overflow-y-auto scrollbar-hide">
          {NAV_ITEMS.map(({ path, label, icon, key }) => (
            <Link
              key={key}
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

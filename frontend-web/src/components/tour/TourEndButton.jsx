import { useTour } from '../../context/TourContext'
import { useLocation, useNavigate } from 'react-router-dom'

/**
 * Floating "Acabar Tutorial" button always visible when tour is active.
 * Placed fixed at bottom-right so the user can exit at any time.
 */
export default function TourEndButton() {
  const { tourActive, endTourManually, tourJugadorId, openSidebarRef } = useTour()
  const location = useLocation()
  const navigate = useNavigate()

  const resolveNextTourPath = () => {
    const path = location.pathname

    if (path === '/favoritos/select') return '/menu'
    if (path === '/menu') return '/mi-plantilla'
    if (path === '/mi-plantilla') return '/clasificacion'
    if (path === '/clasificacion') return `/jugador/${tourJugadorId || 1}`
    if (path.startsWith('/jugador')) return '/amigos'
    if (path === '/amigos') return '/perfil'
    return null
  }

  const handleEndTutorial = () => {
    const nextPath = resolveNextTourPath()
    endTourManually()

    if (nextPath === '/mi-plantilla') {
      openSidebarRef.current?.()
    }

    if (nextPath) {
      navigate(nextPath)
    }
  }

  if (!tourActive) return null

  return (
    <button
      onClick={handleEndTutorial}
      className="fixed bottom-6 right-6 z-[9999999] flex items-center gap-2 px-4 py-2.5 bg-red-600/90 hover:bg-red-600 text-white rounded-xl shadow-2xl font-bold text-sm transition-all border border-red-500 backdrop-blur-sm"
      title="Salir del tour guiado"
    >
      <span className="material-symbols-outlined text-base">close</span>
      Acabar Tutorial
    </button>
  )
}

import { useState, useEffect } from 'react'
import Header from './Header'
import Sidebar from './Sidebar'
import { useTour } from '../../context/TourContext'
import TourEndButton from '../tour/TourEndButton'

function GlobalToasts() {
  const [toasts, setToasts] = useState([])
  useEffect(() => {
    const handler = (e) => {
      const { msg, tipo = 'info' } = e.detail
      const id = Date.now() + Math.random()
      setToasts(prev => [...prev, { id, msg, tipo }])
      setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4500)
    }
    window.addEventListener('globalNotif', handler)
    return () => window.removeEventListener('globalNotif', handler)
  }, [])
  if (!toasts.length) return null
  const cls = (tipo) => tipo === 'success' ? 'bg-green-600' : tipo === 'error' ? 'bg-red-600' : tipo === 'warning' ? 'bg-yellow-600' : 'bg-blue-600'
  return (
    <div className="fixed top-20 left-6 z-[999999] pointer-events-none flex flex-col gap-3 max-w-sm">
      {toasts.map(t => (
        <div key={t.id} className={`px-4 py-3 rounded-xl text-white shadow-2xl font-semibold text-sm pointer-events-auto break-words ${cls(t.tipo)}`}>
          {t.msg}
        </div>
      ))}
    </div>
  )
}

const LS_KEY = 'sidebarHidden'

export default function Layout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try {
      return localStorage.getItem(LS_KEY) !== 'true'
    } catch {
      return false
    }
  })

  const { openSidebarRef } = useTour()

  // Register the openSidebar callback for the tour system
  useEffect(() => {
    openSidebarRef.current = () => setSidebarOpen(true)
    return () => { openSidebarRef.current = null }
  }, [openSidebarRef])

  const toggleSidebar = () => {
    setSidebarOpen((prev) => {
      const next = !prev
      try { localStorage.setItem(LS_KEY, String(!next)) } catch {}
      return next
    })
  }

  const closeSidebar = () => {
    setSidebarOpen(false)
    try { localStorage.setItem(LS_KEY, 'true') } catch {}
  }

  // On small screens always close sidebar
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth < 1024) setSidebarOpen(false)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return (
    <div className="flex flex-col h-screen bg-background-dark">
      <GlobalToasts />
      <TourEndButton />
      <Header onToggleSidebar={toggleSidebar} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar open={sidebarOpen} onClose={closeSidebar} />
        <main
          className="flex-1 h-full overflow-y-auto scrollbar-hide"
          // push content right when sidebar is open on large screens
          style={{ marginLeft: sidebarOpen && window.innerWidth >= 1024 ? '18rem' : '0', transition: 'margin 0.3s cubic-bezier(0.4,0,0.2,1)' }}
        >
          {children}
        </main>
      </div>
    </div>
  )
}

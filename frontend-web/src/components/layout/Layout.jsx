import { useState, useEffect } from 'react'
import Header from './Header'
import Sidebar from './Sidebar'

const LS_KEY = 'sidebarHidden'

export default function Layout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try {
      return localStorage.getItem(LS_KEY) !== 'true'
    } catch {
      return false
    }
  })

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

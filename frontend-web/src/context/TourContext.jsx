import { createContext, useContext, useRef, useState, useEffect } from 'react'

const TourContext = createContext(null)

export function TourProvider({ children }) {
  const [tourActive, setTourActive] = useState(false)
  const [completedPhases, setCompletedPhases] = useState(new Set())
  // Layout registers its openSidebar callback here so tour phases can open the sidebar
  const openSidebarRef = useRef(null)
  // Stores a jugador-page ID found during the menu phase, for later navigation
  const [tourJugadorId, setTourJugadorId] = useState(null)

  // Restore active state across page reloads
  useEffect(() => {
    if (localStorage.getItem('_tour_active') === '1') {
      setTourActive(true)
    }
  }, [])

  function startTour() {
    setTourActive(true)
    setCompletedPhases(new Set())
    localStorage.setItem('_tour_active', '1')
  }

  function endTour() {
    setTourActive(false)
    setCompletedPhases(new Set())
    localStorage.removeItem('_tour_active')
    localStorage.setItem('_tour_done', '1')
  }

  function markPhaseCompleted(phaseId) {
    setCompletedPhases(prev => new Set([...prev, phaseId]))
  }

  function isPhaseCompleted(phaseId) {
    return completedPhases.has(phaseId)
  }

  // tourModalShown: whether the post-registration "start tour?" modal has been shown
  function hasTourBeenOffered() {
    return !!localStorage.getItem('_tour_offered')
  }

  function markTourOffered() {
    localStorage.setItem('_tour_offered', '1')
  }

  return (
    <TourContext.Provider value={{
      tourActive,
      startTour,
      endTour,
      markPhaseCompleted,
      isPhaseCompleted,
      openSidebarRef,
      tourJugadorId,
      setTourJugadorId,
      hasTourBeenOffered,
      markTourOffered,
    }}>
      {children}
    </TourContext.Provider>
  )
}

export function useTour() {
  const ctx = useContext(TourContext)
  if (!ctx) throw new Error('useTour must be used inside TourProvider')
  return ctx
}

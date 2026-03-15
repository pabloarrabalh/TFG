import { useTour } from '../../context/TourContext'

/**
 * Floating "Acabar Tutorial" button always visible when tour is active.
 * Placed fixed at bottom-right so the user can exit at any time.
 */
export default function TourEndButton() {
  const { tourActive, endTourManually } = useTour()

  if (!tourActive) return null

  return (
    <button
      onClick={endTourManually}
      className="fixed bottom-6 right-6 z-[9999999] flex items-center gap-2 px-4 py-2.5 bg-red-600/90 hover:bg-red-600 text-white rounded-xl shadow-2xl font-bold text-sm transition-all border border-red-500 backdrop-blur-sm"
      title="Salir del tour guiado"
    >
      <span className="material-symbols-outlined text-base">close</span>
      Acabar Tutorial
    </button>
  )
}

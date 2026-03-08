import { useTour } from '../../context/TourContext'

/**
 * Modal shown on SelectFavoritesPage after a new user registers.
 * Asks whether they want a guided tour of the app.
 */
export default function TourModal({ onClose }) {
  const { startTour, markTourOffered } = useTour()

  function handleYes() {
    markTourOffered()
    startTour()
    onClose()
  }

  function handleNo() {
    markTourOffered()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-[9999998] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-surface-dark border border-border-dark rounded-2xl shadow-2xl max-w-md w-full p-8 space-y-6">
        {/* Icon */}
        <div className="flex justify-center">
          <div className="bg-primary/20 rounded-full p-4">
            <span className="material-symbols-outlined text-primary text-5xl">explore</span>
          </div>
        </div>

        {/* Text */}
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-black text-white">¡Bienvenido/a! 👋</h2>
          <p className="text-gray-400 text-base leading-relaxed">
            ¿Quieres un <span className="text-primary font-bold">tour guiado</span> por las principales funciones de la app?
            Te llevaremos por el panel principal, tu plantilla fantasy, la clasificación y más.
          </p>
          <p className="text-gray-500 text-sm">Puedes salir del tour en cualquier momento.</p>
        </div>

        {/* Buttons */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleYes}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-primary hover:bg-primary-dark text-black font-bold rounded-xl transition-all"
          >
            <span className="material-symbols-outlined text-base">play_arrow</span>
            Sí, mostrarme la app
          </button>
          <button
            onClick={handleNo}
            className="flex-1 px-6 py-3 bg-surface-dark hover:bg-white/10 text-gray-400 hover:text-white border border-border-dark rounded-xl font-semibold transition-all "
          >
            Ahora no
          </button>
        </div>
      </div>
    </div>
  )
}

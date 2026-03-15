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
    <div className="fixed inset-0 z-[9999998] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animation-fadeIn">
      <div className="bg-surface-dark border border-primary/40 rounded-2xl shadow-2xl max-w-md w-full p-8 space-y-6 animate-in zoom-in duration-300">
        {/* Icon */}
        <div className="flex justify-center">
          <div className="bg-primary/20 rounded-full p-4 animate-pulse">
            <span className="material-symbols-outlined text-primary text-5xl">explore</span>
          </div>
        </div>

        {/* Text */}
        <div className="text-center space-y-3">
          <h2 className="text-2xl font-black text-white">¡Bienvenido/a a LigaMaster! 👋</h2>
          <p className="text-gray-300 text-base leading-relaxed">
            Hemos preparado un <span className="text-primary font-bold">tour interactivo</span> para que conozcas todas las funciones de la app en apenas 5 minutos.
          </p>
          <p className="text-gray-400 text-sm">Te mostraremos cómo crear tu plantilla, ver predicciones de IA, chatear con el Consejero y mucho más.</p>
          <p className="text-gray-500 text-xs">Puedes salir del tour en cualquier momento o hacerlo después.</p>
        </div>

        {/* Buttons */}
        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            onClick={handleYes}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-primary hover:bg-primary-dark text-black font-bold rounded-xl transition-all hover:shadow-[0_0_16px_rgba(57,255,20,0.5)]"
          >
            <span className="material-symbols-outlined text-base">play_arrow</span>
            Sí, mostrarme la app
          </button>
          <button
            onClick={handleNo}
            className="flex-1 px-6 py-3 bg-surface-dark hover:bg-white/10 text-gray-400 hover:text-white border border-border-dark rounded-xl font-semibold transition-all hover:border-primary/50"
          >
            Ahora no
          </button>
        </div>
      </div>
    </div>
  )
}

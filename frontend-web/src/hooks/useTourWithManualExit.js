import { useEffect, useRef } from 'react'
import { useTour } from '../context/TourContext'
import { driver } from 'driver.js'

/**
 * Hook que simplifica la gestión del tour permitiendo salida manual sin navegación.
 * 
 * Uso:
 * const { startDoneBtnListener } = useTourWithManualExit()
 * 
 * En el setup del driver:
 * driverRef.current = driver({ ... })
 * startDoneBtnListener(doneButtonText) // ej: 'Ver Liga →'
 * driverRef.current.drive()
 */
export function useTourWithManualExit() {
  const { triggerManualExit, resetManualExit, manualTourExit } = useTour()

  /**
   * Intercepta el botón "done" del driver para marcar salida manual
   * Debe llamarse después de crear el driver pero antes de drive()
   * @param {string} doneBtnText - El texto del botón done (ej: 'Ver Liga →')
   */
  function startDoneBtnListener(doneBtnText) {
    // Esperar a que driver.js renderice los botones en el DOM
    setTimeout(() => {
      const buttons = document.querySelectorAll('button')
      const doneButton = Array.from(buttons).find(
        btn => btn.textContent.trim() === doneBtnText.trim()
      )

      if (doneButton) {
        // Agregar listener para marcar salida manual cuando se presiona "done"
        doneButton.addEventListener(
          'click',
          () => {
            triggerManualExit()
          },
          { once: true }
        )
      }
    }, 100)
  }

  /**
   * Devuelve true si el usuario presionó el botón done (salida manual)
   */
  function isManualExit() {
    return manualTourExit
  }

  /**
   * Limpia la bandera de salida manual
   */
  function cleanup() {
    resetManualExit()
  }

  return {
    startDoneBtnListener,
    isManualExit,
    cleanup,
    manualTourExit,
  }
}

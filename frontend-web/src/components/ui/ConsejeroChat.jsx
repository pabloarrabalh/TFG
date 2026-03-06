import { useState, useEffect } from 'react'
import apiClient from '../../services/apiClient'

const BACKEND = 'http://localhost:8000'

export default function ConsejeroChat({ jugadores11, plantillaId, onClose }) {
  const [step, setStep] = useState('select') // 'select', 'action', 'loading', 'result'
  const [selectedJugador, setSelectedJugador] = useState(null)
  const [selectedAction, setSelectedAction] = useState(null)
  const [resultado, setResultado] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSelectJugador = (jugador) => {
    setSelectedJugador(jugador)
    setStep('action')
    setError(null)
  }

  const handleSelectAction = async (action) => {
    if (!selectedJugador) return
    setSelectedAction(action)
    setStep('loading')
    setError(null)
    setLoading(true)

    try {
      const response = await fetch(`${BACKEND}/api/consejero/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        credentials: 'include',
        body: JSON.stringify({
          jugador_id: selectedJugador.id,
          accion: action,
          plantilla_id: plantillaId,
        }),
      })

      if (!response.ok) {
        throw new Error('Error en la respuesta del servidor')
      }

      const data = await response.json()
      setResultado(data)
      setStep('result')
    } catch (err) {
      setError(err?.message || 'Error al analizar al jugador')
      setStep('action')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setSelectedJugador(null)
    setSelectedAction(null)
    setResultado(null)
    setError(null)
    setStep('select')
  }

  function getCookie(name) {
    const value = `; ${document.cookie}`
    const parts = value.split(`; ${name}=`)
    if (parts.length === 2) return parts.pop().split(';').shift()
    return ''
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 bg-surface-dark border border-primary/40 rounded-2xl shadow-2xl overflow-hidden flex flex-col z-[9999]">
      {/* Header */}
      <div className="bg-gradient-to-r from-primary/20 to-primary/10 border-b border-primary/20 px-5 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-2xl text-primary">lightbulb</span>
          <div>
            <h3 className="text-white font-black text-sm">Consejero de Plantilla</h3>
            <p className="text-xs text-gray-400 mt-0.5">Análisis inteligente de tus jugadores</p>
          </div>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors flex-shrink-0">
          <span className="material-symbols-outlined">close</span>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 p-5 space-y-4 max-h-[500px] overflow-y-auto">
        {/* STEP 1: Select jugador */}
        {step === 'select' && (
          <div className="space-y-3">
            <p className="text-sm text-gray-300 font-semibold">¿De qué jugador deseas recibir consejo?</p>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {jugadores11.length === 0 ? (
                <p className="text-xs text-gray-500 italic">No hay jugadores en el once</p>
              ) : (
                jugadores11.map((j) => (
                  <button
                    key={j.id}
                    onClick={() => handleSelectJugador(j)}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-background-dark hover:bg-primary/10 border border-border-dark hover:border-primary/50 transition-all text-left"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-white truncate">{j.nombre} {j.apellido}</p>
                      <p className="text-xs text-gray-400">{j.posicion}</p>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        {/* STEP 2: Select action */}
        {step === 'action' && selectedJugador && (
          <div className="space-y-3">
            <p className="text-sm text-gray-300 font-semibold">
              Vale, ¿qué deseas hacer con <span className="text-primary">{selectedJugador.nombre}</span>?
            </p>
            <div className="space-y-2">
              {[
                { id: 'fichar', label: 'Fichar', icon: 'arrow_downward', color: 'border-blue-500/40 hover:bg-blue-500/10' },
                { id: 'vender', label: 'Vender', icon: 'arrow_upward', color: 'border-red-500/40 hover:bg-red-500/10' },
                { id: 'mantener', label: 'Mantener', icon: 'lock', color: 'border-green-500/40 hover:bg-green-500/10' },
              ].map((action) => (
                <button
                  key={action.id}
                  onClick={() => handleSelectAction(action.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border transition-all text-left font-bold text-white ${action.color}`}
                >
                  <span className="material-symbols-outlined text-lg">{action.icon}</span>
                  {action.label}
                </button>
              ))}
            </div>
            <button
              onClick={handleReset}
              className="w-full px-4 py-2 text-xs text-gray-400 hover:text-white transition-colors border border-border-dark rounded-lg"
            >
              Volver atrás
            </button>
          </div>
        )}

        {/* STEP 3: Loading */}
        {step === 'loading' && (
          <div className="flex flex-col items-center justify-center py-8 gap-3">
            <div className="animate-spin inline-block w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full" />
            <p className="text-sm text-gray-300 text-center">Analizando estadísticas del jugador...</p>
          </div>
        )}

        {/* STEP 4: Result */}
        {step === 'result' && resultado && (
          <div className="space-y-4">
            {/* Header: accion + modelo recommendation */}
            <div className="bg-primary/20 border border-primary/40 rounded-xl p-4">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-bold text-primary uppercase tracking-wider">
                  {resultado.accion === 'fichar' ? 'Fichar' : resultado.accion === 'vender' ? 'Vender' : 'Mantener'} — Análisis Inteligente
                </p>
                {resultado.confianza > 0 && (
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
                    resultado.recomendacion === 'fichar'   ? 'bg-green-500/20 border-green-500/50 text-green-300' :
                    resultado.recomendacion === 'vender'   ? 'bg-red-500/20 border-red-500/50 text-red-300' :
                                                             'bg-yellow-500/20 border-yellow-500/50 text-yellow-300'
                  }`}>
                    Modelo: {resultado.recomendacion} {resultado.confianza}%
                  </span>
                )}
              </div>
              <p className="text-sm text-white leading-relaxed font-semibold">{resultado.veredicto}</p>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-background-dark border border-border-dark rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 mb-1">Rendimiento</p>
                <p className="text-lg font-black text-yellow-400">{resultado.rendimiento}</p>
                <p className="text-xs text-gray-500">media temp.</p>
              </div>
              <div className="bg-background-dark border border-border-dark rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 mb-1">vs Promedio</p>
                <p className={`text-lg font-black ${resultado.vs_promedio > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {resultado.vs_promedio > 0 ? '+' : ''}{resultado.vs_promedio.toFixed(1)}
                </p>
                <p className="text-xs text-gray-500">posición</p>
              </div>
              <div className="bg-background-dark border border-border-dark rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 mb-1">Titulares últ. 3</p>
                <p className={`text-lg font-black ${resultado.titulares_3 === 3 ? 'text-green-400' : resultado.titulares_3 >= 2 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {resultado.titulares_3}/3
                </p>
                <p className="text-xs text-gray-500">{resultado.minutos_3} min</p>
              </div>
            </div>

            {resultado.razon && (
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
                <p className="text-xs font-bold text-blue-300 mb-2">Motivos</p>
                <p className="text-xs text-blue-200 leading-relaxed">{resultado.razon}</p>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={handleReset}
                className="flex-1 px-4 py-2 bg-background-dark border border-border-dark rounded-lg text-sm font-bold text-white hover:bg-white/5 transition-colors"
              >
                Otro jugador
              </button>
              <button
                onClick={onClose}
                className="flex-1 px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary-dark transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-500/20 border border-red-500/40 rounded-lg p-3">
            <p className="text-sm text-red-300">{error}</p>
            <button
              onClick={handleReset}
              className="mt-3 w-full px-3 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 rounded-lg text-xs font-bold text-red-300 transition-colors"
            >
              Volver a intentar
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

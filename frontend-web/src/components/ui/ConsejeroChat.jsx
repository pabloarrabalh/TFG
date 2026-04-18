import { useState } from 'react'
import { backendUrl } from '../../config/backend'

export default function ConsejeroChat({ jugadores11, plantillaId, onClose }) {
  const [step, setStep] = useState('select') // 'select', 'loading', 'result'
  const [selectedJugador, setSelectedJugador] = useState(null)
  const [resultado, setResultado] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSelectJugador = (jugador) => {
    setSelectedJugador(jugador)
    setError(null)
    analizarJugador(jugador)
  }

  const analizarJugador = async (jugador) => {
    if (!jugador) return
    setStep('loading')
    setError(null)
    setLoading(true)

    try {
      const response = await fetch(backendUrl('/api/consejero/'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        credentials: 'include',
        body: JSON.stringify({
          jugador_id: jugador.id,
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
      setStep('select')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setSelectedJugador(null)
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

  const toNumber = (value, fallback = 0) => {
    const n = Number(value)
    return Number.isFinite(n) ? n : fallback
  }

  const formatActionLabel = (value) => {
    if (value === 'fichar') return 'Fichar'
    if (value === 'vender') return 'Vender'
    return 'Vender'
  }

  const confidence = resultado ? Math.max(0, Math.min(100, toNumber(resultado.confianza, 0))) : 0
  const vsPromedio = resultado ? toNumber(resultado.vs_promedio, 0) : 0
  const rendimiento = resultado ? toNumber(resultado.rendimiento, 0) : 0
  const factores = Array.isArray(resultado?.factores) ? resultado.factores : []
  const driversStack = factores
    .filter((factor) => {
      // Excluir estos factores de la visualización con barras
      const excluded = ['sot_last5', 'shots_last5', 'pf_last8', 'form_trend_3_8', 'tackles_last5', 'clears_last5', 'min_last5', 'pf_std5']
      return !excluded.includes(factor.nombre)
    })
    .map((factor, idx) => {
      const impactoRel = Math.max(0, toNumber(factor.impacto_rel_pct ?? factor.impacto, 0))
      return {
        ...factor,
        idx,
        impactoRel,
        esPositivo: factor.direccion === 'positivo',
      }
    })
  const driversTotal = Math.max(
    1,
    driversStack.reduce((acc, factor) => acc + factor.impactoRel, 0)
  )
  const driversConPct = driversStack.map((factor) => ({
    ...factor,
    pctLinea: (factor.impactoRel / driversTotal) * 100,
  }))

  const confidenceColor =
    resultado?.recomendacion === 'fichar'
      ? 'bg-green-500/20 border-green-500/50 text-green-300'
      : 'bg-red-500/20 border-red-500/50 text-red-300'

  return (
    <div className="fixed bottom-4 left-3 right-3 sm:left-auto sm:right-6 sm:w-96 bg-surface-dark border border-primary/40 rounded-2xl shadow-2xl overflow-hidden flex flex-col z-[9999]">
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

        {/* STEP 2: Loading */}
        {step === 'loading' && (
          <div className="flex flex-col items-center justify-center py-8 gap-3">
            <div className="animate-spin inline-block w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full" />
            <p className="text-sm text-gray-300 text-center">Analizando estadísticas del jugador...</p>
          </div>
        )}

        {/* STEP 3: Result */}
        {step === 'result' && resultado && (
          <div className="space-y-4">
            {/* Header: accion + modelo recommendation */}
            <div className="bg-primary/20 border border-primary/40 rounded-xl p-4">
              <div className="flex items-start justify-between gap-3 mb-2">
                <p className="text-xs font-bold text-primary uppercase tracking-wider leading-relaxed">
                  Recomendación automática - Análisis Inteligente
                </p>
                {resultado.confianza > 0 && (
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full border whitespace-nowrap ${confidenceColor}`}>
                    Recomendación: {formatActionLabel(resultado.recomendacion)} ({resultado.confianza}%)
                  </span>
                )}
              </div>
              {resultado.confianza > 0 && (
                <div className="mb-3">
                  <div className="w-full h-2 rounded-full bg-black/30 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        resultado.recomendacion === 'fichar'
                          ? 'bg-green-400'
                          : 'bg-red-400'
                      }`}
                      style={{ width: `${confidence}%` }}
                    />
                  </div>
                </div>
              )}
              <p className="text-sm text-white leading-relaxed font-semibold">{resultado.veredicto}</p>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-background-dark border border-border-dark rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 mb-1">Rendimiento</p>
                <p className="text-lg font-black text-yellow-400">{rendimiento.toFixed(2)}</p>
                <p className="text-xs text-gray-500">media temp.</p>
              </div>
              <div className="bg-background-dark border border-border-dark rounded-lg p-3 text-center">
                <p className="text-xs text-gray-400 mb-1">vs Promedio</p>
                <p className={`text-lg font-black ${vsPromedio > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {vsPromedio > 0 ? '+' : ''}{vsPromedio.toFixed(1)}
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
                <p className="text-xs font-bold text-blue-300 mb-2">Resumen contextual</p>
                <p className="text-xs text-blue-200 whitespace-pre-wrap leading-relaxed">{resultado.razon}</p>
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

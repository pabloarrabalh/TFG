import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import HelpButton from '../components/ui/HelpButton'

const BACKEND = 'http://localhost:8000'

const POS_COLOR = {
  Portero: 'from-yellow-500 to-orange-500',
  Defensa: 'from-blue-500 to-violet-500',
  Centrocampista: 'from-gray-500 to-gray-600',
  Delantero: 'from-red-500 to-pink-500',
}
const POS_BADGE = {
  Portero: { bg: 'bg-yellow-500', text: 'PT' },
  Defensa: { bg: 'bg-blue-600', text: 'DF' },
  Centrocampista: { bg: 'bg-gray-500', text: 'MC' },
  Delantero: { bg: 'bg-red-500', text: 'DT' },
}
const ESCUDO_MAP = {
  'Real Madrid': 'madrid', 'Barcelona': 'barcelona', 'Atlético Madrid': 'atletico_madrid',
  'Real Sociedad': 'sociedad', 'Villarreal': 'villarreal', 'Athletic Club': 'athletic_club',
  'Real Betis': 'betis', 'Girona': 'girona', 'Rayo Vallecano': 'rayo_vallecano',
  'Osasuna': 'osasuna', 'Valencia': 'valencia', 'Celta Vigo': 'celta_vigo',
  'Real Mallorca': 'mallorca', 'Getafe': 'getafe', 'Sevilla': 'sevilla',
  'Alavés': 'alaves', 'RCD Espanyol': 'espanyol', 'Las Palmas': 'las_palmas',
  'Almería': 'almeria', 'Valladolid': 'valladolid', 'Leganés': 'leganes',
}
const obtenerEscudo = n => ESCUDO_MAP[n] || (n?.toLowerCase().replace(/\s+/g, '_')) || null

function getCsrfToken() {
  const m = document.cookie?.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='))
  return m ? m.split('=')[1] : ''
}

function EscudoImg({ nombre, size = 24 }) {
  const s = obtenerEscudo(nombre)
  if (!s) return <span className="text-gray-400 text-xs font-bold">{(nombre || '?')[0]}</span>
  return (
    <img src={`${BACKEND}/static/escudos/${s}.png`} alt={nombre}
      style={{ width: size, height: size }} className="object-contain rounded"
      onError={e => { e.target.style.display = 'none' }} />
  )
}

function PlayerCardRO({ jugador, prediccion, onClick }) {
  const badge = POS_BADGE[jugador.posicion] || POS_BADGE.Delantero
  const gradient = POS_COLOR[jugador.posicion] || POS_COLOR.Delantero
  return (
    <div
      onClick={() => onClick(jugador)}
      className={`bg-gradient-to-br ${gradient} rounded-xl p-3 text-center shadow-lg cursor-pointer min-w-[120px] max-w-[145px] hover:scale-105 transition-all select-none`}
    >
      {jugador.proximo_rival_nombre && (
        <div className="absolute top-2 right-2 opacity-80">
          <EscudoImg nombre={jugador.proximo_rival_nombre} size={16} />
        </div>
      )}
      <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center mx-auto mb-1 text-white font-black text-sm">
        {`${jugador.nombre?.[0] || ''}${jugador.apellido?.[0] || ''}`.toUpperCase()}
      </div>
      <p className="font-bold text-white text-xs leading-tight truncate px-2">
        {jugador.nombre} {jugador.apellido || ''}
      </p>
      <span className={`inline-block px-1.5 py-0.5 rounded text-white text-xs font-bold mt-1 ${badge.bg}`}>
        {badge.text}
      </span>
      {prediccion != null && (
        <div className="mt-1 text-yellow-300 font-black text-sm">{Number(prediccion).toFixed(1)} pts</div>
      )}
    </div>
  )
}

export default function AmigoPlantillaPage() {
  const { userId } = useParams()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [amigoInfo, setAmigoInfo] = useState(null)
  const [plantillas, setPlantillas] = useState([])
  const [plantillaIdx, setPlantillaIdx] = useState(0)
  const [jornadaActual, setJornadaActual] = useState(18)
  const [jornadas, setJornadas] = useState([])
  const [predicciones, setPredicciones] = useState({})
  const [error, setError] = useState(null)

  // Modal detalles
  const [modalDet, setModalDet] = useState(null)
  const [detLoadingPred, setDetLoadingPred] = useState(false)
  const [detPrediccion, setDetPrediccion] = useState(null)
  const [detFeaturesImpacto, setDetFeaturesImpacto] = useState([])

  const fetchingRef = useRef(new Set())

  useEffect(() => {
    loadData()
  }, [userId])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      // Load jornadas
      const jRes = await fetch(`${BACKEND}/api/mi-plantilla/?temporada=25/26&jornada=1`, { credentials: 'include' })
      const jData = await jRes.json()
      const jornList = jData.jornadas || []
      setJornadas(jornList)
      const jornActual = jornList[jornList.length - 1] || 18
      setJornadaActual(jornActual)

      // Load friend's plantillas
      const res = await fetch(`${BACKEND}/api/amigos/${userId}/plantillas/`, { credentials: 'include' })
      if (!res.ok) {
        const d = await res.json()
        setError(d.error || 'No se pudo cargar la plantilla')
        return
      }
      const data = await res.json()
      setAmigoInfo(data.amigo)
      setPlantillas(data.plantillas || [])
    } catch (e) {
      setError('Error de conexión')
    } finally {
      setLoading(false)
    }
  }

  const plantilla = plantillas[plantillaIdx]
  const alineacion = plantilla?.alineacion || {}

  const todosLosJugadores = [
    ...(alineacion.Portero || []),
    ...(alineacion.Defensa || []),
    ...(alineacion.Centrocampista || []),
    ...(alineacion.Delantero || []),
  ]

  useEffect(() => {
    if (todosLosJugadores.length > 0) {
      cargarPredicciones(todosLosJugadores)
    }
  }, [plantillaIdx, jornadaActual])

  async function cargarPredicciones(jugadores) {
    const nuevas = {}
    await Promise.all(jugadores.map(async jug => {
      if (fetchingRef.current.has(jug.id)) return
      fetchingRef.current.add(jug.id)
      try {
        const resp = await fetch(`${BACKEND}/api/predecir-jugador/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          credentials: 'include',
          body: JSON.stringify({ jugador_id: jug.id, jornada: jornadaActual, posicion: jug.posicion }),
        })
        const data = await resp.json()
        if (data.prediccion != null) nuevas[jug.id] = data.prediccion
      } catch {}
      finally { fetchingRef.current.delete(jug.id) }
    }))
    setPredicciones(prev => ({ ...prev, ...nuevas }))
  }

  async function abrirDetalles(jugador) {
    setModalDet(jugador)
    setDetPrediccion(null)
    setDetFeaturesImpacto([])
    setDetLoadingPred(true)
    try {
      const isPortero = (jugador.posicion || '').toLowerCase().includes('portero')
      let endpoint, body
      if (isPortero) {
        endpoint = `${BACKEND}/api/explicar-prediccion/`
        body = { jugador_id: jugador.id, jornada: jornadaActual }
      } else {
        endpoint = `${BACKEND}/api/predecir-jugador/`
        body = { jugador_id: jugador.id, jornada: jornadaActual, posicion: jugador.posicion }
      }
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        credentials: 'include',
        body: JSON.stringify(body),
      })
      const data = await resp.json()
      setDetPrediccion(data.prediccion ?? null)
      setDetFeaturesImpacto(data.features_impacto || [])
    } catch {}
    finally { setDetLoadingPred(false) }
  }

  if (loading) return <div className="flex items-center justify-center min-h-screen"><LoadingSpinner size="lg" /></div>
  if (error) return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <span className="material-symbols-outlined text-5xl text-red-400">error</span>
      <p className="text-white text-lg">{error}</p>
      <button onClick={() => navigate('/amigos')} className="px-4 py-2 bg-primary text-black rounded-xl font-bold">Volver a amigos</button>
    </div>
  )

  if (!plantilla) return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <span className="material-symbols-outlined text-5xl text-gray-500">sports_soccer</span>
      <p className="text-white text-lg">{amigoInfo?.nombre || 'Tu amigo'} no tiene plantillas públicas</p>
      <button onClick={() => navigate('/amigos')} className="px-4 py-2 bg-primary text-black rounded-xl font-bold">Volver a amigos</button>
    </div>
  )

  const POSICIONES_CAMPO = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']

  return (
    <div className="p-4 pb-20 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/amigos')} className="p-2 rounded-xl hover:bg-white/10 text-gray-400 hover:text-white transition-colors">
          <span className="material-symbols-outlined">arrow_back</span>
        </button>
        <div className="flex items-center gap-3">
          {amigoInfo?.profile_photo ? (
            <img src={amigoInfo.profile_photo.startsWith('http') ? amigoInfo.profile_photo : `${BACKEND}${amigoInfo.profile_photo}`}
              alt="" className="w-10 h-10 rounded-xl object-cover border border-border-dark" />
          ) : (
            <div className="w-10 h-10 rounded-xl bg-primary/20 border border-primary/40 flex items-center justify-center">
              <span className="text-primary font-bold">{(amigoInfo?.nombre || amigoInfo?.username || '?')[0].toUpperCase()}</span>
            </div>
          )}
          <div>
            <h1 className="text-xl font-black text-white">Plantilla de {amigoInfo?.nombre || amigoInfo?.username}</h1>
            <p className="text-xs text-gray-400">@{amigoInfo?.username}</p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {/* Plantilla selector */}
        {plantillas.length > 1 && (
          <div className="flex gap-1">
            {plantillas.map((p, i) => (
              <button key={p.id} onClick={() => { setPlantillaIdx(i); setPredicciones({}) }}
                className={`px-3 py-1.5 rounded-xl text-sm font-semibold transition-colors ${i === plantillaIdx ? 'bg-primary text-black' : 'bg-surface-dark border border-border-dark text-white hover:bg-white/10'}`}>
                {p.nombre}
              </button>
            ))}
          </div>
        )}
        {/* Jornada selector */}
        <div className="flex items-center gap-2 ml-auto bg-surface-dark rounded-xl px-3 py-1.5 border border-border-dark">
          <span className="material-symbols-outlined text-gray-400 text-base">sports_soccer</span>
          <span className="text-sm text-gray-300">Jornada</span>
          <select value={jornadaActual}
            onChange={e => { setJornadaActual(parseInt(e.target.value)); setPredicciones({}) }}
            className="bg-transparent text-white text-sm font-bold outline-none cursor-pointer">
            {jornadas.map(j => <option key={j} value={j}>{j}</option>)}
          </select>
        </div>
      </div>

      {/* Plantilla nombre */}
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-primary">groups</span>
        <h2 className="text-lg font-black text-white">{plantilla.nombre}</h2>
        <span className="text-xs text-gray-500 bg-surface-dark border border-border-dark px-2 py-0.5 rounded-full ml-1">{plantilla.formacion}</span>
        <span className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full ml-1">
          <span className="material-symbols-outlined text-xs align-middle">public</span> Pública
        </span>
      </div>

      {/* Campo */}
      <div className="relative w-full rounded-2xl overflow-hidden" style={{
        background: 'linear-gradient(180deg,#14532d 0%,#166534 12%,#15803d 24%,#16a34a 36%,#15803d 48%,#166534 60%,#16a34a 72%,#15803d 84%,#14532d 100%)',
        minHeight: '520px',
        border: '2px solid rgba(255,255,255,0.08)',
      }}>
        {/* Field lines */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-white/15" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 rounded-full border border-white/15" />
          <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-white/15" />
        </div>
        {/* Rows */}
        <div className="relative z-10 flex flex-col justify-around h-full py-4 min-h-[520px]">
          {[...POSICIONES_CAMPO].reverse().map(pos => {
            const jug = alineacion[pos] || []
            if (!jug.length) return null
            return (
              <div key={pos} className="flex justify-center gap-3 flex-wrap px-2">
                {jug.map((j, idx) => (
                  <div key={`${j.id}-${idx}`} className="relative">
                    <PlayerCardRO
                      jugador={j}
                      prediccion={predicciones[j.id]}
                      onClick={abrirDetalles}
                    />
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      </div>

      {/* Suplentes */}
      {(alineacion.Suplentes || []).length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-bold text-gray-400 mb-2 uppercase tracking-wider">Suplentes</h3>
          <div className="flex gap-3 flex-wrap">
            {(alineacion.Suplentes).map((j, idx) => (
              <PlayerCardRO key={`sup-${j.id}-${idx}`} jugador={j} prediccion={predicciones[j.id]} onClick={abrirDetalles} />
            ))}
          </div>
        </div>
      )}

      {/* Modal detalles */}
      {modalDet && (
        <div className="fixed inset-0 bg-black/70 z-[9998] flex items-center justify-center p-4" onClick={() => setModalDet(null)}>
          <div className="bg-surface-dark border border-border-dark rounded-2xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-black text-white truncate">{modalDet.nombre} {modalDet.apellido}</h2>
              <button onClick={() => setModalDet(null)} className="text-gray-400 hover:text-white flex-shrink-0">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Equipo</span>
                <div className="flex items-center gap-2">
                  <EscudoImg nombre={modalDet.equipo_nombre} size={24} />
                  <span className="text-white text-sm font-bold">{modalDet.equipo_nombre || '-'}</span>
                </div>
              </div>
              {modalDet.proximo_rival_nombre && (
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 text-sm">Próximo rival</span>
                  <div className="flex items-center gap-2">
                    <EscudoImg nombre={modalDet.proximo_rival_nombre} size={24} />
                    <span className="text-white text-sm font-bold">{modalDet.proximo_rival_nombre}</span>
                  </div>
                </div>
              )}
              <div className="border-t border-border-dark pt-3">
                <p className="text-sm font-bold text-white mb-2">Predicción jornada {jornadaActual}</p>
                {detLoadingPred ? (
                  <div className="flex items-center gap-2 text-xs text-gray-400 italic">
                    <span className="animate-spin inline-block w-3 h-3 border-2 border-yellow-400 border-t-transparent rounded-full" />
                    Analizando al jugador...
                  </div>
                ) : detPrediccion != null ? (
                  <div>
                    <div className="text-2xl font-black text-yellow-400 mb-3">{Number(detPrediccion).toFixed(2)} pts</div>
                    {detFeaturesImpacto.length > 0 && (() => {
                      const positivos = detFeaturesImpacto
                        .filter(f => (f.impacto ?? f.impacto_pts ?? 0) > 0)
                        .sort((a, b) => Math.abs(b.impacto ?? b.impacto_pts ?? 0) - Math.abs(a.impacto ?? a.impacto_pts ?? 0))
                        .slice(0, 3)
                      const negativos = detFeaturesImpacto
                        .filter(f => (f.impacto ?? f.impacto_pts ?? 0) < 0)
                        .sort((a, b) => Math.abs(b.impacto ?? b.impacto_pts ?? 0) - Math.abs(a.impacto ?? a.impacto_pts ?? 0))
                        .slice(0, 3)
                      return (
                        <div className="space-y-2">
                          {positivos.length > 0 && (
                            <div>
                              <p className="text-xs font-bold text-green-400 mb-1 uppercase tracking-wider">↑ A favor</p>
                              <div className="space-y-1">
                                {positivos.map((f, i) => (
                                  <div key={i} className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 bg-green-500/10 border border-green-500/20">
                                    <span className="text-white/85 text-xs leading-tight flex-1">{f.explicacion || f.feature}</span>
                                    <span className="text-xs font-black whitespace-nowrap text-green-400">+{Math.abs(f.impacto).toFixed(2)} pts</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {negativos.length > 0 && (
                            <div>
                              <p className="text-xs font-bold text-red-400 mb-1 uppercase tracking-wider">↓ En contra</p>
                              <div className="space-y-1">
                                {negativos.map((f, i) => (
                                  <div key={i} className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 bg-red-500/10 border border-red-500/20">
                                    <span className="text-white/85 text-xs leading-tight flex-1">{f.explicacion || f.feature}</span>
                                    <span className="text-xs font-black whitespace-nowrap text-red-400">−{Math.abs(f.impacto).toFixed(2)} pts</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })()}
                  </div>
                ) : (
                  <span className="text-xs text-gray-500">Sin predicción disponible para esta jornada</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      <HelpButton title="Plantilla de tu amigo" sections={[
        { title: 'Plantilla', fields: [
          { label: 'Posición', description: 'Línea táctica del jugador: Portero, Defensa, Centrocampista o Delantero.' },
          { label: 'PTS', description: 'Puntos fantasy acumulados por el jugador en la temporada.' },
        ]},
        { title: 'Predicción XAI', fields: [
          { label: 'Predicción', description: 'Puntuación estimada para el próximo partido por el modelo de IA.' },
          { label: 'Factores positivos', description: 'Variables que aumentan la predicción de puntos del jugador.' },
          { label: 'Factores negativos', description: 'Variables que reducen la predicción de puntos del jugador.' },
        ]},
      ]} />
    </div>
  )
}

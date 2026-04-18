import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import HelpButton from '../components/ui/HelpButton'
import CampoPlantilla from '../components/campo/CampoPlantilla'
import { getAuthToken } from '../services/apiClient'
import { backendUrl } from '../config/backend'

const normalizePhotoUrl = (photo) => {
  if (!photo) return null
  const value = `${photo}`.trim()
  if (!value) return null
  if (value.startsWith('http://') || value.startsWith('https://')) return value
  const normalizedPath = value.startsWith('/') ? value : `/${value}`
  try {
    return new URL(normalizedPath, backendUrl()).toString()
  } catch {
    return normalizedPath
  }
}

const FORMACIONES = {
  '4-3-3': { Portero: 1, Defensa: 4, Centrocampista: 3, Delantero: 3 },
  '4-4-2': { Portero: 1, Defensa: 4, Centrocampista: 4, Delantero: 2 },
  '3-5-2': { Portero: 1, Defensa: 3, Centrocampista: 5, Delantero: 2 },
  '3-4-3': { Portero: 1, Defensa: 3, Centrocampista: 4, Delantero: 3 },
  '4-2-4': { Portero: 1, Defensa: 4, Centrocampista: 2, Delantero: 4 },
  '5-4-1': { Portero: 1, Defensa: 5, Centrocampista: 4, Delantero: 1 },
  '5-3-2': { Portero: 1, Defensa: 5, Centrocampista: 3, Delantero: 2 },
  '4-5-1': { Portero: 1, Defensa: 4, Centrocampista: 5, Delantero: 1 },
}

const POS_BADGE = {
  Portero: { bg: 'bg-yellow-500', text: 'PT' },
  Defensa: { bg: 'bg-blue-600', text: 'DF' },
  Centrocampista: { bg: 'bg-gray-500', text: 'MC' },
  Delantero: { bg: 'bg-red-500', text: 'DT' },
}

const POSICIONES_CAMPO = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']

const POS_COLOR = {
  Portero: 'from-yellow-500 to-orange-500',
  Defensa: 'from-blue-500 to-violet-500',
  Centrocampista: 'from-gray-500 to-gray-600',
  Delantero: 'from-red-500 to-pink-500',
}

const ESCUDO_MAP = {
  'Real Madrid': 'madrid', 'Barcelona': 'barcelona', 'Atlético Madrid': 'atletico_madrid',
  'Real Sociedad': 'sociedad', 'Villarreal': 'villarreal', 'Athletic Club': 'athletic_club',
  'Real Betis': 'betis', 'Girona': 'girona', 'Rayo Vallecano': 'rayo_vallecano',
  'Osasuna': 'osasuna', 'Valencia': 'valencia', 'Celta Vigo': 'celta_vigo',
  'Real Mallorca': 'mallorca', 'Getafe': 'getafe', 'Sevilla': 'sevilla',
  'Alavés': 'alaves', 'RCD Espanyol': 'espanyol', 'Las Palmas': 'las_palmas',
  'Almería': 'almeria', 'Granada': 'granada', 'Valladolid': 'valladolid',
  'Cádiz': 'cadiz', 'Leganés': 'leganes', 'Levante': 'levante',
}

const obtenerEscudo = (nombre) => ESCUDO_MAP[nombre] || (nombre?.toLowerCase().replace(/\s+/g, '_')) || null

function EscudoImg({ nombre, size = 28 }) {
  const s = obtenerEscudo(nombre)
  if (!s) return <span className="text-gray-400 text-xs font-bold">{(nombre || '?')[0]}</span>
  return (
    <img
      src={backendUrl(`/static/escudos/${s}.png`)}
      alt={nombre}
      style={{ width: size, height: size }}
      className="object-contain rounded"
      onError={e => { e.target.style.display = 'none' }}
    />
  )
}

export default function AmigoPlantillaPage() {
  const { userId } = useParams()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [amigoInfo, setAmigoInfo] = useState(null)
  const [plantillas, setPlantillas] = useState([])
  const [plantillaIdx, setPlantillaIdx] = useState(0)
  const [jornadaActual, setJornadaActual] = useState(() => {
    const saved = localStorage.getItem('jornadaActual')
    return saved ? parseInt(saved) : 18
  })
  const [predicciones, setPredicciones] = useState({})
  const [error, setError] = useState(null)
  const [modalDet, setModalDet] = useState(null)
  const [detLoadingPred, setDetLoadingPred] = useState(false)
  const [detPrediccion, setDetPrediccion] = useState(null)
  const [detFeaturesImpacto, setDetFeaturesImpacto] = useState([])
  const [friendAvatarError, setFriendAvatarError] = useState(false)
  const fetchingRef = useRef(new Set())

  useEffect(() => {
    loadData()
  }, [userId])

  useEffect(() => {
    setFriendAvatarError(false)
  }, [amigoInfo?.profile_photo])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(backendUrl(`/api/amigos/${userId}/plantillas/`), {
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      })
      if (!res.ok) {
        const d = await res.json()
        setError(d.error || 'No se pudo cargar la plantilla')
        return
      }
      const data = await res.json()
      setAmigoInfo(data.amigo)
      setPlantillas(data.plantillas || [])
    } catch (e) {
      setError('Error de conexion')
    } finally {
      setLoading(false)
    }
  }

  const plantilla = plantillas[plantillaIdx]
  const alineacion = plantilla?.alineacion || {}
  const formacion = plantilla?.formacion || '4-3-3'
  const cfg = FORMACIONES[formacion]

  const todosLosJugadores = [
    ...(alineacion.Portero || []),
    ...(alineacion.Defensa || []),
    ...(alineacion.Centrocampista || []),
    ...(alineacion.Delantero || []),
  ].filter(Boolean)

  useEffect(() => {
    if (todosLosJugadores.length > 0) {
      cargarPredicciones()
    }
  }, [plantillaIdx, jornadaActual])

  async function cargarPredicciones() {
    const nuevas = {}
    await Promise.all(
      todosLosJugadores.map(async (jug) => {
        if (fetchingRef.current.has(jug.id)) return
        fetchingRef.current.add(jug.id)
        try {
          const resp = await fetch(backendUrl('/api/explicar-prediccion/'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
            body: JSON.stringify({ jugador_id: jug.id, jornada: jornadaActual, posicion: jug.posicion }),
          })
          const data = await resp.json()
          if (data.prediccion != null) nuevas[jug.id] = data.prediccion
        } catch (e) {
          console.error('Error cargando prediccion', e)
        } finally {
          fetchingRef.current.delete(jug.id)
        }
      })
    )
    setPredicciones((prev) => ({ ...prev, ...nuevas }))
  }

  async function abrirDetalles(jugador) {
    setModalDet(jugador)
    setDetPrediccion(null)
    setDetFeaturesImpacto([])
    setDetLoadingPred(true)
    try {
      const resp = await fetch(backendUrl('/api/explicar-prediccion/'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
        body: JSON.stringify({ jugador_id: jugador.id, jornada: jornadaActual, posicion: jugador.posicion }),
      })
      const data = await resp.json()
      setDetPrediccion(data.prediccion ?? null)
      setDetFeaturesImpacto(data.features_impacto || [])
    } catch (e) {
      console.error('Error cargando detalles', e)
    } finally {
      setDetLoadingPred(false)
    }
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
      <p className="text-white text-lg">{amigoInfo?.nombre || 'Tu amigo'} no tiene plantillas publicas</p>
      <button onClick={() => navigate('/amigos')} className="px-4 py-2 bg-primary text-black rounded-xl font-bold">Volver a amigos</button>
    </div>
  )

  function renderLinea(pos) {
    const slots = cfg[pos] || 1
    return (
      <div className="flex items-center justify-center gap-3 py-1">
        {Array.from({ length: slots }, (_, i) => {
          const j = alineacion[pos]?.[i] || null
          return j ? (
            <div
              key={i}
              className={`bg-gradient-to-br ${POS_COLOR[j.posicion] || POS_COLOR.Delantero} rounded-xl p-4 text-center shadow-lg cursor-pointer w-[130px] h-[180px] hover:scale-105 transition-all relative select-none flex flex-col justify-between`}
              onClick={() => abrirDetalles(j)}
            >
              {j.proximo_rival_nombre && (
                <div className="absolute top-2 right-2 opacity-90">
                  <EscudoImg nombre={j.proximo_rival_nombre} size={20} />
                </div>
              )}
              <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center mx-auto text-white font-black text-sm">
                {`${j.nombre?.[0] || ''}${j.apellido?.[0] || ''}`.toUpperCase()}
              </div>
              <div className="flex-1 flex flex-col justify-center">
                <p className="font-bold text-white text-xs leading-tight truncate px-2">
                  {j.nombre} {j.apellido || ''}
                </p>
                <span className={`inline-block px-1.5 py-0.5 rounded text-white text-xs font-bold mt-1 ${(POS_BADGE[j.posicion] || POS_BADGE.Delantero).bg}`}>
                  {(POS_BADGE[j.posicion] || POS_BADGE.Delantero).text}
                </span>
              </div>
              <div className="mt-1">
                {predicciones[j.id] != null ? (
                  <div className="text-yellow-300 font-black text-sm">{Number(predicciones[j.id]).toFixed(1)} pts</div>
                ) : (
                  <div className="text-gray-300 font-black text-xs">—</div>
                )}
              </div>
            </div>
          ) : (
            <div
              key={i}
              className="w-[130px] h-[180px] rounded-xl border-2 border-dashed border-white/20 flex items-center justify-center text-gray-500 hover:border-primary/50 transition-colors"
            />
          )
        })}
      </div>
    )
  }

  return (
    <div className="p-4 pb-20 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/amigos')} className="p-2 rounded-xl hover:bg-white/10 text-gray-400 hover:text-white transition-colors">
          <span className="material-symbols-outlined">arrow_back</span>
        </button>
        <div className="flex items-center gap-3">
          {normalizePhotoUrl(amigoInfo?.profile_photo) && !friendAvatarError ? (
            <img 
              src={normalizePhotoUrl(amigoInfo.profile_photo)}
              alt=""
              className="w-10 h-10 rounded-full object-cover border border-border-dark"
              onError={() => setFriendAvatarError(true)}
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-primary/20 border border-primary/40 flex items-center justify-center">
              <span className="text-primary font-bold">{(amigoInfo?.nombre || amigoInfo?.username || '?')[0].toUpperCase()}</span>
            </div>
          )}
          <div>
            <h1 className="text-xl font-black text-white">Plantilla de {amigoInfo?.nombre || amigoInfo?.username}</h1>
            <p className="text-xs text-gray-400">@{amigoInfo?.username}</p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        {plantillas.length > 1 && (
          <div className="flex gap-1">
            {plantillas.map((p, i) => (
              <button 
                key={p.id} 
                onClick={() => { setPlantillaIdx(i); setPredicciones({}) }}
                className={`px-3 py-1.5 rounded-xl text-sm font-semibold transition-colors ${i === plantillaIdx ? 'bg-primary text-black' : 'bg-surface-dark border border-border-dark text-white hover:bg-white/10'}`}
              >
                {p.nombre}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-primary">groups</span>
        <h2 className="text-lg font-black text-white">{plantilla.nombre}</h2>
        <span className="text-xs text-gray-500 bg-surface-dark border border-border-dark px-2 py-0.5 rounded-full ml-1">{formacion}</span>
        <span className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full ml-1">
          <span className="material-symbols-outlined text-xs align-middle mr-0.5">public</span>
          Publica
        </span>
      </div>

      <CampoPlantilla 
        alineacion={alineacion}
        formaciones={FORMACIONES}
        predicciones={predicciones}
        onCardClick={abrirDetalles}
      />

      {modalDet && (
        <div className="fixed inset-0 bg-black/70 z-[9998] flex items-center justify-center p-4" onClick={() => setModalDet(null)}>
          <div className="bg-surface-dark border border-border-dark rounded-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
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
                  <span className="text-gray-400 text-sm">Proximo rival</span>
                  <div className="flex items-center gap-2">
                    <EscudoImg nombre={modalDet.proximo_rival_nombre} size={24} />
                    <span className="text-white text-sm font-bold">{modalDet.proximo_rival_nombre}</span>
                  </div>
                </div>
              )}
              <div className="border-t border-border-dark pt-3">
                <p className="text-sm font-bold text-white mb-2">Prediccion jornada {jornadaActual}</p>
                {detLoadingPred ? (
                  <div className="flex items-center gap-2 text-xs text-gray-400 italic">
                    <span className="animate-spin inline-block w-3 h-3 border-2 border-yellow-400 border-t-transparent rounded-full" />
                    Analizando al jugador...
                  </div>
                ) : detPrediccion != null ? (
                  <div>
                    <div className="bg-yellow-500/20 border border-yellow-500/40 rounded-lg p-3 mb-3">
                      <p className="text-xs font-bold text-yellow-300 mb-1">🤖 PREDICCIÓN CON IA</p>
                      <div className="text-2xl font-black text-yellow-400">{Number(detPrediccion).toFixed(2)} pts</div>
                    </div>
                    {detFeaturesImpacto.length > 0 && (() => {
                      const getImpacto = f => f.impacto_pts ?? f.impacto ?? 0
                      const positivos = detFeaturesImpacto
                        .filter(f => getImpacto(f) > 0)
                        .sort((a, b) => Math.abs(getImpacto(b)) - Math.abs(getImpacto(a)))
                        .slice(0, 3)
                      const negativos = detFeaturesImpacto
                        .filter(f => getImpacto(f) < 0)
                        .sort((a, b) => Math.abs(getImpacto(b)) - Math.abs(getImpacto(a)))
                        .slice(0, 3)
                      return (
                        <div className="space-y-2">
                          {positivos.length > 0 && (
                            <div>
                              <p className="text-xs font-bold text-green-400 mb-1 uppercase tracking-wider">↑ A favor</p>
                              <div className="space-y-1">
                                {positivos.map((f, i) => (
                                  <div key={i} className="rounded-lg px-2.5 py-2 bg-green-500/10 border border-green-500/20">
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="text-white/85 text-xs leading-tight font-semibold flex-1">{f.explicacion_positiva || f.explicacion || f.feature}</span>
                                      <span className="text-xs font-black whitespace-nowrap text-green-400">+{Math.abs(getImpacto(f)).toFixed(2)} pts</span>
                                    </div>
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
                                  <div key={i} className="rounded-lg px-2.5 py-2 bg-red-500/10 border border-red-500/20">
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="text-white/85 text-xs leading-tight font-semibold flex-1">{f.explicacion_negativa || f.explicacion || f.feature}</span>
                                      <span className="text-xs font-black whitespace-nowrap text-red-400">−{Math.abs(getImpacto(f)).toFixed(2)} pts</span>
                                    </div>
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
                  <span className="text-xs text-gray-500">Sin prediccion disponible para esta jornada</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

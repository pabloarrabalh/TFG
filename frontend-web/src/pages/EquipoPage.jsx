import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import api from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'

const BACKEND = 'http://localhost:8000'

// Caché de banderas
const flagCache = JSON.parse(localStorage.getItem('flag_cache') || '{}')

// Nationality codes that restcountries.com doesn't support → emoji fallback
const NATIONALITY_EMOJI_MAP = {
  'ENG': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
}

// Hook para cargar banderas
const useFlag = (nationality) => {
  const [flagUrl, setFlagUrl] = useState(null)
  
  useEffect(() => {
    if (!nationality || nationality === '0' || nationality === '—') {
      setFlagUrl(null)
      return
    }
    // Skip API call for sub-national codes handled by emoji map
    if (NATIONALITY_EMOJI_MAP[nationality]) {
      setFlagUrl(null)
      return
    }
    
    // Revisar caché
    if (flagCache[nationality]) {
      setFlagUrl(flagCache[nationality])
      return
    }
    
    // Consultar API
    fetch(`https://restcountries.com/v3.1/alpha/${nationality}?fields=flags`)
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data && data.flags) {
          const url = data.flags.svg || data.flags.png
          flagCache[nationality] = url
          localStorage.setItem('flag_cache', JSON.stringify(flagCache))
          setFlagUrl(url)
        }
      })
      .catch(() => setFlagUrl(null))
  }, [nationality])
  
  return flagUrl
}

export default function EquipoPage() {
  const { nombre } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [mostrarUltimas3, setMostrarUltimas3] = useState(false)
  const [historicoOpen, setHistoricoOpen] = useState(true)
  const [mostrarPartidosPasados, setMostrarPartidosPasados] = useState(false)
  const POS_ORDER = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']
  const [posicionesAbiertas, setPosicionesAbiertas] = useState({ Portero: true, Defensa: true, Centrocampista: true, Delantero: true, Otros: true })
  const togglePosicion = (pos) => setPosicionesAbiertas(prev => ({ ...prev, [pos]: !prev[pos] }))
  const [analysisModalOpen, setAnalysisModalOpen] = useState(false)
  const [pastSeasonModalOpen, setPastSeasonModalOpen] = useState(false)

  const temporada = searchParams.get('temporada') || '25/26'
  const jornada = searchParams.get('jornada') || localStorage.getItem('jornada_global') || null

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ temporada })
      if (jornada) params.set('jornada', jornada)
      
      const { data: d } = await api.get(`/api/equipo/${encodeURIComponent(nombre)}/?${params}`)
      setData(d)
    } catch (e) {
      // Error loading equipo
    } finally {
      setLoading(false)
    }
  }, [nombre, temporada, jornada])

  useEffect(() => { fetchData() }, [fetchData])

  // Sync jornada from sidebar (localStorage + event)
  useEffect(() => {
    if (!searchParams.get('jornada')) {
      const saved = localStorage.getItem('jornada_global')
      if (saved) {
        const newParams = new URLSearchParams(searchParams)
        newParams.set('jornada', saved)
        setSearchParams(newParams, { replace: true })
      }
    }
  }, []) // Only on mount

  useEffect(() => {
    const handleJornadaChange = (e) => {
      const newJornada = e.detail.jornada
      const newParams = new URLSearchParams(searchParams)
      newParams.set('jornada', newJornada)
      setSearchParams(newParams)
    }
    window.addEventListener('jornadaChanged', handleJornadaChange)
    return () => window.removeEventListener('jornadaChanged', handleJornadaChange)
  }, [searchParams, setSearchParams])

  // Auto-redirect to the most recent season with players when the current season has none
  // Only on initial mount (no temporada param set by the user yet)
  useEffect(() => {
    if (!data || data.jugadores?.length > 0 || !data.suggested_temporada) return
    // Only auto-redirect if the user didn't explicitly choose a temporada
    if (searchParams.get('temporada')) return
    const tempDisplay = data.suggested_temporada.replace('_', '/')
    const newParams = new URLSearchParams(searchParams)
    newParams.set('temporada', tempDisplay)
    setSearchParams(newParams, { replace: true })
  }, [data]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading && !data) return <LoadingSpinner />

  const {
    equipo = {},
    jugadores = [],
    clasificacion = {},
    racha_actual_detalles = [],
    temporadas_display = [],
    temporada_actual = '',
    temporada_actual_db = '',
    jornadas_disponibles = [],
    jornada_actual = 1,
    jornada_min = 1,
    jornada_max = 38,
    proximo_partido = null,
    rival_info = null,
    top_3_puntos = [],
    top_3_minutos = [],
    ultimas_3_jugadores = [],
    ultimas_3_stats = null,
    historico_temporadas = [],
    goles_equipo_favor = 0,
    goles_equipo_contra = 0,
    suggested_temporada = null
  } = data || {}

  const cambiarJornada = (delta) => {
    let nueva_jornada = jornada_actual + delta
    if (nueva_jornada < jornada_min) nueva_jornada = jornada_min
    if (nueva_jornada > jornada_max) nueva_jornada = jornada_max
    
    const newParams = new URLSearchParams(searchParams)
    newParams.set('jornada', nueva_jornada)
    setSearchParams(newParams)
  }

  const handleTemporadaChange = (tempNombre) => {
    // Convertir 25_26 a 25/26 para la URL
    const tempDisplay = tempNombre.replace('_', '/')
    // Preserve the current jornada so próximo partido works in past seasons too
    const currentJornada = searchParams.get('jornada') || localStorage.getItem('jornada_global')
    const url = currentJornada
      ? `/equipo/${encodeURIComponent(nombre)}?temporada=${tempDisplay}&jornada=${currentJornada}`
      : `/equipo/${encodeURIComponent(nombre)}?temporada=${tempDisplay}`
    navigate(url)
  }

  const groupByPosicion = (jugs) => {
    return {
      'Portero': jugs.filter(j => j.posicion === 'Portero'),
      'Defensa': jugs.filter(j => j.posicion === 'Defensa'),
      'Centrocampista': jugs.filter(j => j.posicion === 'Centrocampista'),
      'Delantero': jugs.filter(j => j.posicion === 'Delantero'),
    }
  }

  const jugadoresPorPos = groupByPosicion(jugadores)

  const FlagIcon = ({ nationality }) => {
    const flagUrl = useFlag(nationality)
    const emoji = NATIONALITY_EMOJI_MAP[nationality]

    if (emoji) {
      return <span className="text-base">{emoji}</span>
    }
    
    if (!flagUrl) {
      return <span className="text-base">🌍</span>
    }
    
    return (
      <img 
        src={flagUrl} 
        alt={nationality} 
        className="h-4 w-6 object-cover rounded-sm shadow-sm inline-block"
      />
    )
  }

  // Top-3 para el sidebar: usa ultimas_3_jugadores cuando está ese modo activo
  const _mapUltimas = (j) => ({
    id: j.jugador,
    jugador_id: j.jugador,
    nombre: j.jugador__nombre,
    apellido: j.jugador__apellido,
    puntos_fantasy: j.total_puntos_fantasy || 0,
    total_puntos_fantasy: j.total_puntos_fantasy || 0,
    minutos: j.total_minutos || 0,
    total_minutos: j.total_minutos || 0,
  })
  const sideTop3pts = (mostrarUltimas3 && ultimas_3_jugadores.length > 0)
    ? [...ultimas_3_jugadores].map(_mapUltimas).sort((a, b) => b.puntos_fantasy - a.puntos_fantasy).slice(0, 3)
    : top_3_puntos
  const sideTop3min = (mostrarUltimas3 && ultimas_3_jugadores.length > 0)
    ? [...ultimas_3_jugadores].map(_mapUltimas).sort((a, b) => b.minutos - a.minutos).slice(0, 3)
    : top_3_minutos

  const renderJugadorCard = (jugador) => (
    <div key={jugador.id} className="bg-surface-dark border border-border-dark rounded-xl p-4 hover:bg-white/5 transition-all">
      <div className="flex items-start gap-2 mb-3">
        <div className={`px-2 py-1 rounded text-xs font-bold flex-shrink-0 text-white ${
          jugador.posicion === 'Portero' ? 'bg-yellow-500' :
          jugador.posicion === 'Defensa' ? 'bg-blue-500' :
          jugador.posicion === 'Centrocampista' ? 'bg-gray-500' :
          'bg-red-500'
        }`}>
          {jugador.posicion === 'Portero' ? 'PT' :
           jugador.posicion === 'Defensa' ? 'DF' :
           jugador.posicion === 'Centrocampista' ? 'MC' : 'DT'}
        </div>
        <div className="flex-1 min-w-0">
          <a
            href={`/jugador/${jugador.jugador_id || jugador.id}`}
            className="font-bold text-white text-xs hover:text-primary transition-colors cursor-pointer line-clamp-2"
          >
            {jugador.nombre} {jugador.apellido}
          </a>
          <p className="text-xs text-gray-400 uppercase font-bold tracking-widest mt-1 flex items-center gap-2">
            <FlagIcon nationality={jugador.nacionalidad} />
            <span>{jugador.nacionalidad || '—'} · #{jugador.dorsal}</span>
          </p>
        </div>
      </div>
      
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="text-center">
          <div className="text-lg font-black text-primary">{jugador.puntos_fantasy || 0}</div>
          <div className="text-xs text-gray-400">PTS</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-black text-blue-400">{jugador.minutos || 0}'</div>
          <div className="text-xs text-gray-400">MIN</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-black text-yellow-400">{jugador.partidos || 0}</div>
          <div className="text-xs text-gray-400">PJ</div>
        </div>
      </div>
      
      <div className="border-t border-border-dark pt-3 space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-400">Partidos</span>
          <span className="text-xs font-bold text-white">{jugador.partidos || 0}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-400">Minutos</span>
          <span className="text-xs font-bold text-white">{jugador.minutos || 0}'</span>
        </div>
      </div>
    </div>
  )

  return (
    <div className="p-6 space-y-6 bg-background-dark min-h-full">
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Main Content */}
        <div className="xl:col-span-9">
          {/* Back Button & Badge */}
          <div className="flex items-center justify-between gap-4 mb-6">
            <a
              href={`/clasificacion?temporada=${temporada}`}
              className="px-4 py-2 bg-primary hover:bg-primary/80 text-black font-bold rounded-lg transition-all whitespace-nowrap text-sm"
            >
              ← Volver a Clasificación
            </a>
            <div className="bg-primary/10 px-4 py-2 rounded-lg border border-primary/30">
              <span className="text-xs font-bold text-primary uppercase tracking-widest">1ª DIVISIÓN - LALIGA EA SPORTS</span>
            </div>
          </div>

          {/* Team Header */}
          <div className="bg-pitch-pattern rounded-3xl p-8 mb-6 relative overflow-hidden">
            <div className="flex items-start gap-8 mb-6">
              <TeamShield
                escudo={equipo.escudo}
                nombre={equipo.nombre}
                className="w-32 h-32 object-contain flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <h1 className="text-3xl font-black text-white mb-2 truncate max-w-lg">
                  {equipo.nombre?.toUpperCase() || 'EQUIPO'}
                </h1>
                <div className="flex items-center gap-6 text-white/80">
                  {equipo.estadio ? (
                    <span className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-primary">stadium</span>
                      {equipo.estadio}
                    </span>
                  ) : (
                    <span className="flex items-center gap-2 text-gray-400 italic">
                      <span className="material-symbols-outlined">stadium</span>
                      Estadio no disponible
                    </span>
                  )}
                </div>
                
                {/* Racha Actual */}
                {racha_actual_detalles && racha_actual_detalles.length > 0 && (
                  <div className="flex items-center gap-2 mt-4">
                    {racha_actual_detalles.map((detalle, idx) => (
                      <div key={idx} className="relative inline-block group">
                        <div className={`w-6 h-6 rounded-full text-xs font-bold text-white flex items-center justify-center cursor-pointer ${
                          detalle.resultado === 'V' ? 'bg-green-500' :
                          detalle.resultado === 'E' ? 'bg-yellow-500' :
                          detalle.resultado === 'D' ? 'bg-red-500' :
                          'bg-gray-500'
                        }`}>
                          {detalle.resultado}
                        </div>
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none z-20 transition-opacity duration-200 border border-gray-700">
                          {detalle.titulo}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>


          </div>

          {/* Selector de Temporada y Jornada */}
          <GlassPanel className="rounded-2xl p-6 mb-6">
            <div className="flex gap-3 flex-wrap items-center justify-center">
              {temporadas_display.map(temp => (
                <button
                  key={temp.nombre}
                  onClick={() => handleTemporadaChange(temp.nombre)}
                  className={`px-6 py-3 rounded-lg font-bold transition-all ${
                    temp.display === temporada_actual
                      ? 'bg-green-500 text-black hover:bg-green-600'
                      : 'bg-surface-dark border border-border-dark text-white hover:border-primary'
                  }`}
                >
                  {temp.display}
                </button>
              ))}
              
              <button
                onClick={() => setMostrarUltimas3(!mostrarUltimas3)}
                className="px-6 py-3 rounded-lg font-bold transition-all bg-primary hover:bg-primary/80 text-black flex items-center gap-2 whitespace-nowrap"
              >
                <span className="material-symbols-outlined text-base">trending_up</span>
                Últimas 3
              </button>
            </div>
          </GlassPanel>

          {/* Últimas 3 — panel de stats resumen */}
          {mostrarUltimas3 && ultimas_3_stats && (
            <GlassPanel className="rounded-2xl p-6 mb-6">
              <div className="flex items-center gap-3 mb-5">
                <span className="material-symbols-outlined text-primary">bar_chart</span>
                <h2 className="text-xl font-black text-white uppercase tracking-wider">
                  ESTADÍSTICAS — ÚLTIMAS {ultimas_3_stats.temporadas?.length || 3} TEMPORADAS
                </h2>
              </div>
              <div className="flex flex-wrap gap-2 mb-5">
                {(ultimas_3_stats.temporadas || []).map(t => (
                  <span key={t} className="bg-primary/10 border border-primary/30 text-primary text-xs font-bold px-3 py-1 rounded-full">{t.replace('_','/')}</span>
                ))}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-surface-dark rounded-xl p-4 text-center">
                  <div className="text-3xl font-black text-primary">{ultimas_3_stats.total_goles || 0}</div>
                  <div className="text-xs text-gray-400 mt-1 uppercase font-bold">Goles</div>
                </div>
                <div className="bg-surface-dark rounded-xl p-4 text-center">
                  <div className="text-3xl font-black text-blue-400">{ultimas_3_stats.total_asistencias || 0}</div>
                  <div className="text-xs text-gray-400 mt-1 uppercase font-bold">Asistencias</div>
                </div>
                <div className="bg-surface-dark rounded-xl p-4 text-center">
                  <div className="text-3xl font-black text-yellow-400">{ultimas_3_stats.partidos_jugados || 0}</div>
                  <div className="text-xs text-gray-400 mt-1 uppercase font-bold">Partidos</div>
                </div>
                <div className="bg-surface-dark rounded-xl p-4 text-center">
                  <div className="text-3xl font-black text-green-400">{ultimas_3_stats.temporadas?.length || 0}</div>
                  <div className="text-xs text-gray-400 mt-1 uppercase font-bold">Temporadas</div>
                </div>
              </div>
            </GlassPanel>
          )}

          {/* Histórico Temporadas */}
          {historico_temporadas && historico_temporadas.length > 0 && (
            <GlassPanel className="rounded-2xl p-6 mb-6">
              <div
                className="flex items-center gap-3 mb-6 cursor-pointer"
                onClick={() => setHistoricoOpen(!historicoOpen)}
              >
                <span
                  className="material-symbols-outlined text-primary transition-transform"
                  style={{ transform: historicoOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}
                >
                  expand_more
                </span>
                <h2 className="text-2xl font-black text-white uppercase tracking-wider">HISTÓRICO</h2>
              </div>
              
              {historicoOpen && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border-dark">
                        <th className="text-left py-3 px-4 text-xs font-bold text-gray-400 uppercase">Temporada</th>
                        <th className="text-center py-3 px-4 text-xs font-bold text-gray-400 uppercase">Pos</th>
                        <th className="text-center py-3 px-4 text-xs font-bold text-gray-400 uppercase">V</th>
                        <th className="text-center py-3 px-4 text-xs font-bold text-gray-400 uppercase">E</th>
                        <th className="text-center py-3 px-4 text-xs font-bold text-gray-400 uppercase">P</th>
                        <th className="text-center py-3 px-4 text-xs font-bold text-gray-400 uppercase">GF</th>
                        <th className="text-center py-3 px-4 text-xs font-bold text-gray-400 uppercase">GC</th>
                        <th className="text-center py-3 px-4 text-xs font-bold text-gray-400 uppercase">DF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historico_temporadas.map((temp, idx) => (
                        <tr key={idx} className="border-b border-border-dark/30 hover:bg-surface-dark/50 transition-colors">
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-white">{temp.temporada}</span>
                              {idx > 0 && (
                                <span className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded">Finalizada</span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg text-xs font-black ${
                              temp.posicion <= 4 ? 'bg-blue-500/20 text-blue-400' :
                              temp.posicion <= 7 ? 'bg-orange-500/20 text-orange-400' :
                              temp.posicion <= 17 ? 'bg-gray-500/20 text-gray-300' :
                              'bg-red-500/20 text-red-400'
                            }`}>
                              {temp.posicion}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center text-green-400 font-bold">{temp.victorias}</td>
                          <td className="py-3 px-4 text-center text-yellow-400 font-bold">{temp.empates}</td>
                          <td className="py-3 px-4 text-center text-red-400 font-bold">{temp.derrotas}</td>
                          <td className="py-3 px-4 text-center text-gray-300">{temp.goles_favor}</td>
                          <td className="py-3 px-4 text-center text-gray-300">{temp.goles_contra}</td>
                          <td className={`py-3 px-4 text-center ${
                            temp.diferencia_goles > 0 ? 'text-primary font-bold' :
                            temp.diferencia_goles < 0 ? 'text-red-400 font-bold' :
                            'text-gray-300'
                          }`}>
                            {temp.diferencia_goles > 0 ? '+' : ''}{temp.diferencia_goles}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </GlassPanel>
          )}

          {/* Plantilla Oficial */}
          <GlassPanel className="rounded-2xl p-6">
            {(() => {
              // If mostrarUltimas3, map ultimas_3_jugadores to player-card format
              let plantillaJugadores = jugadores
              if (mostrarUltimas3 && ultimas_3_jugadores && ultimas_3_jugadores.length > 0) {
                plantillaJugadores = ultimas_3_jugadores.map(j => ({
                  id: j.jugador,
                  jugador_id: j.jugador,
                  nombre: j.jugador__nombre,
                  apellido: j.jugador__apellido,
                  posicion: j.posicion || '',
                  nacionalidad: j['jugador__nacionalidad'] || '',
                  dorsal: j.dorsal != null ? j.dorsal : '-',
                  goles: j.total_goles || 0,
                  asistencias: j.total_asistencias || 0,
                  puntos_fantasy: j.total_puntos_fantasy || 0,
                  partidos: j.partidos_count || 0,
                  minutos: j.total_minutos || 0,
                }))
              }

              const VALID_POS = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']
              const byPos = {
                Portero: plantillaJugadores.filter(j => j.posicion === 'Portero'),
                Defensa: plantillaJugadores.filter(j => j.posicion === 'Defensa'),
                Centrocampista: plantillaJugadores.filter(j => j.posicion === 'Centrocampista'),
                Delantero: plantillaJugadores.filter(j => j.posicion === 'Delantero'),
                Otros: plantillaJugadores.filter(j => !VALID_POS.includes(j.posicion)),
              }

              const POS_META = {
                Portero:       { color: 'bg-yellow-500', label: 'PORTEROS',       badge: 'PT' },
                Defensa:       { color: 'bg-blue-500',   label: 'DEFENSAS',       badge: 'DF' },
                Centrocampista:{ color: 'bg-gray-500',   label: 'CENTROCAMPISTAS',badge: 'MC' },
                Delantero:     { color: 'bg-red-500',    label: 'DELANTEROS',     badge: 'DT' },
                Otros:         { color: 'bg-purple-500', label: 'OTROS',          badge: '?' },
              }
              const ALL_POS = [...POS_ORDER, 'Otros']

              return (
                <>
                  <h2 className="text-3xl font-black text-white mb-8">
                    PLANTILLA <span className="text-primary">{mostrarUltimas3 ? 'ÚLTIMAS 3 TEMPORADAS' : 'OFICIAL'}</span>
                    {plantillaJugadores.length > 0 && ` (${plantillaJugadores.length} jugadores)`}
                  </h2>

                  {plantillaJugadores.length > 0 ? (
                    <div className="space-y-4">
                      {ALL_POS.map(pos => {
                        if (!byPos[pos] || byPos[pos].length === 0) return null
                        const meta = POS_META[pos]
                        const isOpen = posicionesAbiertas[pos]
                        return (
                          <div key={pos}>
                            {/* Collapsible header — clicking toggles */}
                            <button
                              onClick={() => togglePosicion(pos)}
                              className="w-full flex items-center gap-3 mb-3 group text-left"
                            >
                              <div className={`w-4 h-4 ${meta.color} rounded-full flex-shrink-0`} />
                              <h3 className="text-lg font-black text-white uppercase tracking-wider group-hover:text-primary transition-colors">
                                {meta.label}
                              </h3>
                              <span className="text-xs text-gray-500 font-bold ml-1">({byPos[pos].length})</span>
                              <span
                                className="material-symbols-outlined text-gray-400 group-hover:text-primary transition-all ml-auto"
                                style={{ transform: isOpen ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s' }}
                              >expand_more</span>
                            </button>

                            {isOpen && (
                              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                                {byPos[pos].map(jugador => renderJugadorCard(jugador))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <div className="p-12 text-center">
                      <p className="text-gray-400 text-lg">No hay datos de plantilla disponibles para este equipo en esta temporada.</p>
                    </div>
                  )}
                </>
              )
            })()}
          </GlassPanel>
        </div>

        {/* Sidebar */}
        <div className="xl:col-span-3">
          {/* Mensaje si no hay jugadores */}
          {jugadores.length === 0 && equipo.nombre && (
            <GlassPanel className="rounded-2xl p-6 mb-6 bg-yellow-500/10 border-yellow-500/30">
              <div className="text-center space-y-2">
                <span className="material-symbols-outlined text-yellow-500 text-5xl mb-3">info</span>
                <h3 className="text-lg font-bold text-yellow-400 mb-2">Sin datos esta temporada</h3>
                <p className="text-gray-300 text-sm mb-3">
                  {equipo.nombre} no disputa LaLiga EA Sports en la temporada {temporada}.
                </p>
                {suggested_temporada && (
                  <button
                    onClick={() => handleTemporadaChange(suggested_temporada)}
                    className="w-full bg-yellow-600 hover:bg-yellow-500 text-white px-4 py-2 rounded-lg font-bold text-sm transition-all"
                  >
                    Ver temporada {suggested_temporada.replace('_', '/')}
                  </button>
                )}
              </div>
            </GlassPanel>
          )}

          {/* Próximo Encuentro */}
          {jugadores.length > 0 && !mostrarUltimas3 && (
            <GlassPanel className="rounded-2xl p-6 mb-6">
              <div className="flex items-center gap-3 mb-4">
                <span className="material-symbols-outlined text-primary">calendar_today</span>
                <h3 className="text-lg font-bold text-white uppercase tracking-wider">PRÓXIMO ENCUENTRO</h3>
              </div>
              
              {proximo_partido && rival_info && (temporada === '25/26' || mostrarPartidosPasados) ? (
                <div className="space-y-3">
                  {temporada !== '25/26' && mostrarPartidosPasados && (
                    <div className="flex items-start gap-2 p-3 bg-yellow-950/30 border border-yellow-600/50 rounded-lg">
                      <span className="material-symbols-outlined text-yellow-400 text-sm flex-shrink-0 mt-0.5">info</span>
                      <p className="text-yellow-300 text-xs">
                        Este partido ya se ha jugado en una temporada pasada
                      </p>
                    </div>
                  )}
                  
                  <div className="text-center p-6 bg-surface-dark rounded-2xl space-y-4">
                    <div className="flex flex-col items-center gap-2 mb-2">
                      <TeamShield
                        escudo={rival_info.escudo}
                        nombre={rival_info.nombre}
                        className="w-24 h-24 object-contain"
                      />
                      <h4 className="text-lg font-bold text-white text-center">{rival_info.nombre}</h4>
                    </div>
                    
                    {proximo_partido.fecha_partido ? (
                      <div className="text-primary font-bold">
                        {new Date(proximo_partido.fecha_partido).toLocaleDateString('es-ES', {
                          weekday: 'long',
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric'
                        })}
                      </div>
                    ) : (
                      <div className="text-gray-400">Horario por confirmar</div>
                    )}
                    
                    <div className="border-t border-border-dark pt-4 mt-4">
                      <button
                        onClick={() => setAnalysisModalOpen(true)}
                        className="w-full bg-primary hover:bg-primary-dark text-black px-4 py-2 rounded-lg font-bold uppercase tracking-wider transition-all text-sm flex items-center justify-center gap-2"
                      >
                        VER ANÁLISIS
                        <span className="material-symbols-outlined text-base">arrow_forward</span>
                      </button>
                    </div>
                  </div>
                  
                  {temporada !== '25/26' && mostrarPartidosPasados && (
                    <button
                      onClick={() => setMostrarPartidosPasados(false)}
                      className="w-full bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded-lg font-bold uppercase tracking-wider transition-all text-xs"
                    >
                      Ocultar Historial
                    </button>
                  )}
                </div>
              ) : temporada !== '25/26' && !mostrarPartidosPasados && proximo_partido ? (
                // Temporada pasada con próximo partido pero oculto - mostrar botón
                <div className="text-center p-6 bg-surface-dark rounded-2xl space-y-4">
                  <span className="material-symbols-outlined text-yellow-500 text-4xl block mb-3">info</span>
                  <h4 className="text-lg font-bold text-white mb-2">Consultar Temporada Pasada</h4>
                  <p className="text-gray-400 text-sm mb-4">
                    Los próximos partidos disponibles corresponden a una temporada anterior. ¿Deseas consultarlos?
                  </p>
                  <button
                    onClick={() => setPastSeasonModalOpen(true)}
                    className="w-full bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-2 rounded-lg font-bold uppercase tracking-wider transition-all text-sm"
                  >
                    Ver Próximos Partidos
                  </button>
                </div>
              ) : (
                <div className="text-center p-6 bg-surface-dark rounded-2xl">
                  <p className="text-gray-400 text-sm">No hay próximo partido disponible</p>
                </div>
              )}
            </GlassPanel>
          )}

          {/* Top 3 Fantasy */}
          {sideTop3pts && sideTop3pts.length > 0 && (jugadores.length > 0 || mostrarUltimas3) && (
            <GlassPanel className="rounded-2xl p-6 mb-6">
              <div className="flex items-center gap-3 mb-4">
                <span className="material-symbols-outlined text-primary">star</span>
                <h3 className="text-lg font-bold text-white uppercase tracking-wider">
                  TOP 3 FANTASY{mostrarUltimas3 ? ' · 3 TEMP.' : ''}
                </h3>
              </div>
              
              <div className="space-y-2">
                {sideTop3pts.map((jugador, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-surface-dark rounded-lg p-3 hover:bg-opacity-80 transition">
                    <div className="flex items-center gap-3 flex-1">
                      <div className="text-xs font-bold text-primary bg-primary/20 w-6 h-6 rounded flex items-center justify-center">
                        {idx + 1}
                      </div>
                      <a
                        href={`/jugador/${jugador.jugador_id || jugador.id}`}
                        className="font-bold text-white text-xs hover:text-primary transition-colors cursor-pointer flex-1 line-clamp-2"
                      >
                        {jugador.nombre} {jugador.apellido}
                      </a>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-black text-primary">{jugador.total_puntos_fantasy || jugador.puntos_fantasy}</div>
                      <div className="text-xs text-gray-400">pts</div>
                    </div>
                  </div>
                ))}
              </div>
            </GlassPanel>
          )}

          {/* Top 3 Minutos */}
          {sideTop3min && sideTop3min.length > 0 && (jugadores.length > 0 || mostrarUltimas3) && (
            <GlassPanel className="rounded-2xl p-6 mb-6">
              <div className="flex items-center gap-3 mb-4">
                <span className="material-symbols-outlined text-primary">schedule</span>
                <h3 className="text-lg font-bold text-white uppercase tracking-wider">
                  TOP 3 MINUTOS{mostrarUltimas3 ? ' · 3 TEMP.' : ''}
                </h3>
              </div>
              
              <div className="space-y-2">
                {sideTop3min.map((jugador, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-surface-dark rounded-lg p-3 hover:bg-opacity-80 transition">
                    <div className="flex items-center gap-3 flex-1">
                      <div className="text-xs font-bold text-primary bg-primary/20 w-6 h-6 rounded flex items-center justify-center">
                        {idx + 1}
                      </div>
                      <a
                        href={`/jugador/${jugador.jugador_id || jugador.id}`}
                        className="font-bold text-white text-xs hover:text-primary transition-colors cursor-pointer flex-1 line-clamp-2"
                      >
                        {jugador.nombre} {jugador.apellido}
                      </a>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-black text-primary">{jugador.total_minutos || jugador.minutos}</div>
                      <div className="text-xs text-gray-400">min</div>
                    </div>
                  </div>
                ))}
              </div>
            </GlassPanel>
          )}
        </div>
      </div>

      {/* Modal de Análisis */}
      {analysisModalOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setAnalysisModalOpen(false)}
        >
          <div
            className="bg-surface-dark border border-border-dark rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-border-dark sticky top-0 bg-surface-dark">
              <h2 className="text-2xl font-black text-white">ANÁLISIS DEL PRÓXIMO ENCUENTRO</h2>
              <button
                onClick={() => setAnalysisModalOpen(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <span className="material-symbols-outlined text-2xl">close</span>
              </button>
            </div>
            
            {/* Content */}
            <div className="p-6 space-y-6">
              {/* Escudo del Rival */}
              {rival_info && (
                <div className="flex justify-center mb-6">
                  <TeamShield
                    escudo={rival_info.escudo}
                    nombre={rival_info.nombre}
                    className="w-24 h-24 object-contain"
                  />
                </div>
              )}

              {/* Últimos 5 partidos del rival */}
              {rival_info?.racha && rival_info.racha.length > 0 && (
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">Últimos 5 Partidos</h3>
                  <div className="bg-surface-dark/50 rounded-lg p-4 border border-border-dark/50">
                    <div className="flex justify-center gap-2">
                      {rival_info.racha.map((detalle, idx) => (
                        <div key={idx} className="relative inline-block group">
                          <div className={`w-8 h-8 rounded-full text-xs font-bold text-white flex items-center justify-center cursor-help ${
                            detalle.resultado === 'V' ? 'bg-green-500' :
                            detalle.resultado === 'E' ? 'bg-yellow-500' :
                            detalle.resultado === 'D' ? 'bg-red-500' :
                            'bg-gray-500 border border-gray-600'
                          }`}>
                            {detalle.resultado}
                          </div>
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none z-20 transition-opacity duration-200 border border-gray-700">
                            {detalle.titulo}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              
              {/* Máximos Goleadores */}
              {(rival_info?.max_goleador_equipo || rival_info?.max_goleador_rival) && (
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">Máximos Goleadores</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-surface-dark/50 rounded-lg p-4 border border-border-dark/50">
                      <div className="text-xs text-gray-400 uppercase font-bold mb-3 text-center">
                        {equipo.nombre}
                      </div>
                      {rival_info.max_goleador_equipo ? (
                        <div className="text-center">
                          <div className="text-2xl font-black text-primary">{rival_info.max_goleador_equipo.goles}</div>
                          <div className="text-sm font-bold text-white mt-1">
                            {rival_info.max_goleador_equipo.nombre} {rival_info.max_goleador_equipo.apellido}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">goles en la temporada</div>
                        </div>
                      ) : (
                        <div className="text-center text-gray-400 text-sm">Sin datos</div>
                      )}
                    </div>
                    
                    <div className="bg-surface-dark/50 rounded-lg p-4 border border-border-dark/50">
                      <div className="text-xs text-gray-400 uppercase font-bold mb-3 text-center">
                        {rival_info.nombre}
                      </div>
                      {rival_info.max_goleador_rival ? (
                        <div className="text-center">
                          <div className="text-2xl font-black text-primary">{rival_info.max_goleador_rival.goles}</div>
                          <div className="text-sm font-bold text-white mt-1">
                            {rival_info.max_goleador_rival.nombre} {rival_info.max_goleador_rival.apellido}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">goles en la temporada</div>
                        </div>
                      ) : (
                        <div className="text-center text-gray-400 text-sm">Sin datos</div>
                      )}
                    </div>
                  </div>
                </div>
              )}
              
              {/* Partido Anterior */}
              {rival_info?.partido_anterior && (
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">
                    Enfrentamiento Anterior (Jornada {rival_info.partido_anterior.jornada})
                  </h3>
                  <div className="bg-surface-dark/50 rounded-lg p-6 border border-border-dark/50">
                    <div className="flex items-center justify-between">
                      <div className="text-center flex-1">
                        <div className="text-xs text-gray-400 uppercase font-bold mb-2">
                          {rival_info.partido_anterior.es_local ? equipo.nombre : rival_info.nombre}
                        </div>
                        <div className="text-3xl font-black text-primary">{rival_info.partido_anterior.goles_equipo1}</div>
                      </div>
                      
                      <div className="mx-4 text-center">
                        <div className="text-xs text-gray-400 uppercase font-bold mb-2">
                          <span className={`px-3 py-1 rounded ${
                            rival_info.partido_anterior.resultado === 'V' ? 'bg-green-500/20 text-green-400' :
                            rival_info.partido_anterior.resultado === 'E' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-red-500/20 text-red-400'
                          }`}>
                            {rival_info.partido_anterior.resultado === 'V' ? 'Victoria' :
                             rival_info.partido_anterior.resultado === 'E' ? 'Empate' : 'Derrota'}
                          </span>
                        </div>
                        <div className="text-lg">vs</div>
                      </div>
                      
                      <div className="text-center flex-1">
                        <div className="text-xs text-gray-400 uppercase font-bold mb-2">
                          {rival_info.partido_anterior.es_local ? rival_info.nombre : equipo.nombre}
                        </div>
                        <div className="text-3xl font-black text-primary">{rival_info.partido_anterior.goles_equipo2}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              {/* H2H Histórico */}
              {rival_info?.h2h && (
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">Historial H2H (Todas las Temporadas)</h3>
                  <div className="bg-surface-dark/50 rounded-lg p-4 border border-border-dark/50">
                    <div className="text-xs text-gray-400 mb-4 uppercase font-bold">
                      Récord historial: {rival_info.h2h.victorias} V - {rival_info.h2h.empates} E - {rival_info.h2h.derrotas} P (Total: {rival_info.h2h.total})
                    </div>
                    
                    <div className="relative h-8 bg-gray-700 rounded-lg overflow-hidden flex">
                      <div
                        className="relative bg-green-500 flex items-center justify-center"
                        style={{ width: `${(rival_info.h2h.victorias / rival_info.h2h.total) * 100}%` }}
                      >
                        {(rival_info.h2h.victorias / rival_info.h2h.total) * 100 >= 10 && (
                          <span className="text-xs font-black text-white">{rival_info.h2h.victorias}</span>
                        )}
                      </div>
                      <div
                        className="relative bg-yellow-500 flex items-center justify-center"
                        style={{ width: `${(rival_info.h2h.empates / rival_info.h2h.total) * 100}%` }}
                      >
                        {(rival_info.h2h.empates / rival_info.h2h.total) * 100 >= 10 && (
                          <span className="text-xs font-black text-white">{rival_info.h2h.empates}</span>
                        )}
                      </div>
                      <div
                        className="relative bg-red-500 flex items-center justify-center"
                        style={{ width: `${(rival_info.h2h.derrotas / rival_info.h2h.total) * 100}%` }}
                      >
                        {(rival_info.h2h.derrotas / rival_info.h2h.total) * 100 >= 10 && (
                          <span className="text-xs font-black text-white">{rival_info.h2h.derrotas}</span>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex flex-wrap gap-4 mt-3 text-xs">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-green-500 rounded"></div>
                        <span className="text-gray-400">Victorias: {rival_info.h2h.victorias}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-yellow-500 rounded"></div>
                        <span className="text-gray-400">Empates: {rival_info.h2h.empates}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-red-500 rounded"></div>
                        <span className="text-gray-400">Derrotas: {rival_info.h2h.derrotas}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Comparativa de goles */}
              {proximo_partido && rival_info && (
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">Comparativa de Goles</h3>
                  <div className="space-y-4">
                    {/* Goles a favor */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-gray-400 font-bold">Goles a Favor</span>
                        <div className="flex gap-2">
                          <span className="text-primary font-black">{goles_equipo_favor}</span>
                          <span className="text-gray-400">-</span>
                          <span className="text-white font-black">{rival_info.goles_favor}</span>
                        </div>
                      </div>
                      <div className="relative h-8 bg-gray-700 rounded-lg overflow-hidden flex">
                        <div
                          className="relative bg-green-500 flex items-center justify-center"
                          style={{ width: `${(goles_equipo_favor / (goles_equipo_favor + rival_info.goles_favor)) * 100}%` }}
                        >
                          {(goles_equipo_favor / (goles_equipo_favor + rival_info.goles_favor)) * 100 >= 10 && (
                            <span className="text-xs font-black text-white">{goles_equipo_favor}</span>
                          )}
                        </div>
                        <div
                          className="relative bg-red-500 flex items-center justify-center"
                          style={{ width: `${(rival_info.goles_favor / (goles_equipo_favor + rival_info.goles_favor)) * 100}%` }}
                        >
                          {(rival_info.goles_favor / (goles_equipo_favor + rival_info.goles_favor)) * 100 >= 10 && (
                            <span className="text-xs font-black text-white">{rival_info.goles_favor}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* Goles en contra */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-gray-400 font-bold">Goles en Contra</span>
                        <div className="flex gap-2">
                          <span className="text-primary font-black">{goles_equipo_contra}</span>
                          <span className="text-gray-400">-</span>
                          <span className="text-white font-black">{rival_info.goles_contra}</span>
                        </div>
                      </div>
                      <div className="relative h-8 bg-gray-700 rounded-lg overflow-hidden flex">
                        <div
                          className="relative bg-green-500 flex items-center justify-center"
                          style={{ width: `${(goles_equipo_contra / (goles_equipo_contra + rival_info.goles_contra)) * 100}%` }}
                        >
                          {(goles_equipo_contra / (goles_equipo_contra + rival_info.goles_contra)) * 100 >= 10 && (
                            <span className="text-xs font-black text-white">{goles_equipo_contra}</span>
                          )}
                        </div>
                        <div
                          className="relative bg-red-500 flex items-center justify-center"
                          style={{ width: `${(rival_info.goles_contra / (goles_equipo_contra + rival_info.goles_contra)) * 100}%` }}
                        >
                          {(rival_info.goles_contra / (goles_equipo_contra + rival_info.goles_contra)) * 100 >= 10 && (
                            <span className="text-xs font-black text-white">{rival_info.goles_contra}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            {/* Footer */}
            <div className="p-6 border-t border-border-dark bg-surface-dark sticky bottom-0 flex justify-end gap-3">
              <button
                onClick={() => setAnalysisModalOpen(false)}
                className="px-6 py-2 rounded-lg border border-border-dark text-white hover:bg-white/5 transition-all font-bold"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Confirmar consulta de temporada pasada */}
      {pastSeasonModalOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-dark rounded-2xl border border-border-dark max-w-md w-full p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <span className="material-symbols-outlined text-yellow-500 text-3xl">info</span>
              <h3 className="text-xl font-black text-white">Temporada Anterior</h3>
            </div>
            
            <p className="text-gray-300 mb-6 text-sm">
              Estás consultando datos de una temporada anterior ({temporada}). 
              Los partidos que se muestren ya se han jugado y los resultados son históricos.
            </p>
            
            <div className="bg-yellow-950/30 border border-yellow-600/50 rounded-lg p-4 mb-6">
              <p className="text-yellow-300 text-xs">
                <span className="font-bold">⚠️ Nota:</span> Esta información es histórica y no afecta a la temporada actual.
              </p>
            </div>
            
            <div className="flex gap-3">
              <button
                onClick={() => setPastSeasonModalOpen(false)}
                className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-bold transition-all text-sm"
              >
                Cancelar
              </button>
              <button
                onClick={() => {
                  setMostrarPartidosPasados(true)
                  setPastSeasonModalOpen(false)
                }}
                className="flex-1 px-4 py-2 bg-primary hover:bg-primary/80 text-black rounded-lg font-bold transition-all text-sm"
              >
                Entendido, Ver Partido
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

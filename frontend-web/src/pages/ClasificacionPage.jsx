import React, { useEffect, useState, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import api from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'

export default function ClasificacionPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filtrosOpen, setFiltrosOpen] = useState(true)
  const [partidosOpen, setPartidosOpen] = useState(true)
  const [clasificacionOpen, setClasificacionOpen] = useState(true)
  const [expandedPartido, setExpandedPartido] = useState(null)

  const temporada = searchParams.get('temporada') || '25/26'
  const jornada = searchParams.get('jornada')
  const equipo = searchParams.get('equipo') || ''

  const fetchData = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams()
    params.set('temporada', temporada)
    if (jornada) params.set('jornada', jornada)
    if (equipo && equipo !== '__favoritos__') params.set('equipo', equipo)
    if (equipo === '__favoritos__') params.set('favoritos', 'true')
    try {
      const { data: d } = await api.get(`/api/clasificacion/?${params}`)
      setData(d)
    } catch (e) {
      // Error loading clasificacion
    } finally {
      setLoading(false)
    }
  }, [temporada, jornada, equipo])

  useEffect(() => { fetchData() }, [fetchData])

  // Inicializar jornada desde localStorage si no está en searchParams (solo al montar)
  useEffect(() => {
    if (!jornada) {
      const saved = localStorage.getItem('jornada_global')
      if (saved) {
        const newParams = new URLSearchParams(searchParams)
        newParams.set('jornada', saved)
        setSearchParams(newParams, { replace: true })
      }
    }
  }, []) // Empty dependencies - solo al montar

  // Escuchar cambios de jornada desde el sidebar
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

  const handleTemporadaChange = (e) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('temporada', e.target.value)
    newParams.delete('jornada')
    setSearchParams(newParams)
  }

  const handleJornadaChange = (e) => {
    const newParams = new URLSearchParams(searchParams)
    newParams.set('jornada', e.target.value)
    newParams.delete('equipo')
    setSearchParams(newParams)
  }

  const handleEquipoChange = (e) => {
    const newParams = new URLSearchParams(searchParams)
    if (e.target.value) newParams.set('equipo', e.target.value)
    else newParams.delete('equipo')
    setSearchParams(newParams)
  }

  const cambiarJornada = (delta) => {
    const jornadas = data?.jornadas || []
    const current = parseInt(jornada) || data?.jornada_actual || 1
    const nums = jornadas.map(j => j.numero)
    const idx = nums.indexOf(current)
    const newIdx = idx + delta
    if (newIdx >= 0 && newIdx < nums.length) {
      const newParams = new URLSearchParams(searchParams)
      newParams.set('jornada', nums[newIdx])
      setSearchParams(newParams)
    }
  }

  const irAJornadaActual = () => {
    const newParams = new URLSearchParams(searchParams)
    newParams.delete('jornada')
    newParams.delete('equipo')
    setSearchParams(newParams)
  }

  if (loading && !data) return <LoadingSpinner />

  const {
    clasificacion = [],
    partidos_jornada = [],
    temporadas = [],
    jornadas = [],
    equipos_disponibles = [],
    jornada_actual = 1
  } = data || {}

  const favoritosEquipos = data?.favoritos_equipos || data?.favoritos || data?.equipos_favoritos || []

  const currentJornada = parseInt(jornada) || jornada_actual

  const formatDate = (fecha) => {
    if (!fecha) return ''
    const [y, m, d] = fecha.split('-')
    return `${d}/${m}`
  }

  const formatTime = (hora) => {
    if (!hora) return 'Por definir'
    return hora.slice(0, 5)
  }

  return (
    <div className="p-6 space-y-6 bg-background-dark min-h-full">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-black text-white mb-2">Clasificación</h2>
        <p className="text-gray-400 text-lg">LaLiga EA Sports</p>
        <p className="text-sm text-gray-400 mt-2">Temporada {temporada}</p>
      </div>

      {/* Filters Panel */}
      <GlassPanel className="rounded-2xl p-6 mb-6">
        <div
          className="flex items-center gap-2 cursor-pointer mb-4"
          onClick={() => setFiltrosOpen(!filtrosOpen)}
        >
          <span className={`material-symbols-outlined text-white transition-transform ${filtrosOpen ? '' : '-rotate-90'}`}>
            expand_more
          </span>
          <h3 className="text-lg font-bold text-white">Filtros</h3>
        </div>

        {filtrosOpen && (
          <form className="flex flex-col md:flex-row gap-4 items-end">
            {/* Temporada */}
            <div className="flex-1">
              <label className="block text-sm font-bold text-white mb-2">Temporada</label>
              <select
                value={temporada}
                onChange={handleTemporadaChange}
                className="select-custom w-full bg-surface-dark border border-border-dark text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all cursor-pointer"
              >
                {temporadas.map(t => (
                  <option key={t.nombre} value={t.display}>{t.display}</option>
                ))}
              </select>
            </div>

            {/* Jornada */}
            <div className="flex-1">
              <label className="block text-sm font-bold text-white mb-2">Jornada</label>
              <select
                value={jornada || ''}
                onChange={handleJornadaChange}
                className="select-custom w-full bg-surface-dark border border-border-dark text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all cursor-pointer"
              >
                {!jornada && <option value="">Jornada Actual</option>}
                {jornadas.map(j => (
                  <option key={j.numero} value={j.numero}>Jornada {j.numero}</option>
                ))}
              </select>
            </div>

            {/* Equipo */}
            <div className="flex-1">
              <label className="block text-sm font-bold text-white mb-2">Equipo</label>
              <select
                value={equipo}
                onChange={handleEquipoChange}
                className="select-custom w-full bg-surface-dark border border-border-dark text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all cursor-pointer"
              >
                <option value="">Todos los equipos</option>
                {favoritosEquipos && favoritosEquipos.length > 0 && (
                  <option value="__favoritos__" style={{ fontWeight: 700 }}>★ Equipos favoritos</option>
                )}
                {equipos_disponibles.map(e => (
                  <option key={e.nombre} value={e.nombre}>{e.nombre}</option>
                ))}
              </select>
            </div>

            {/* Button */}
            <button
              type="button"
              onClick={irAJornadaActual}
              className="bg-primary text-black font-bold px-6 py-2.5 rounded-lg hover:bg-primary-dark transition-all"
            >
              Jornada Actual
            </button>
          </form>
        )}
      </GlassPanel>

      {/* Jornada Header + Matches */}
      <GlassPanel className="rounded-2xl p-6 mb-6">
        <div
          className="flex items-center justify-center gap-3 mb-4 cursor-pointer select-none"
          onClick={() => setPartidosOpen(!partidosOpen)}
        >
          <h3 className="text-2xl font-black text-white">Jornada {currentJornada}</h3>
          <span className={`material-symbols-outlined text-white transition-transform ${partidosOpen ? '' : '-rotate-90'}`}>
            expand_more
          </span>
        </div>

        {/* Matches Table */}
        {partidosOpen && partidos_jornada.length > 0 && (
          <div className="border-t border-border-dark pt-4" id="partidos-section">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <tbody>
                    {partidos_jornada.map((p, i) => (
                      <React.Fragment key={i}>
                        {/* Match Row */}
                        <tr
                          className="border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer"
                          onClick={() => setExpandedPartido(expandedPartido === i ? null : i)}
                          id={`partido-${i}`}
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center justify-end gap-3">
                              <span className={`font-bold text-sm ${equipo === p.equipo_local ? 'text-yellow-400' : 'text-white'}`}>
                                {p.equipo_local}
                              </span>
                              <TeamShield
                                escudo={p.equipo_local_escudo}
                                nombre={p.equipo_local}
                                className="size-8 rounded-lg object-contain"
                              />
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center font-black w-20">
                            {p.jugado ? (
                              <span className="text-primary text-xl">{p.goles_local}-{p.goles_visitante}</span>
                            ) : (
                              <span className="text-gray-500">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <TeamShield
                                escudo={p.equipo_visitante_escudo}
                                nombre={p.equipo_visitante}
                                className="size-8 rounded-lg object-contain"
                              />
                              <span className={`font-bold text-sm ${equipo === p.equipo_visitante ? 'text-yellow-400' : 'text-white'}`}>
                                {p.equipo_visitante}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-gray-400 text-xs w-40 text-center">
                            {p.fecha && (
                              <div className="flex flex-col items-center gap-0.5">
                                <span>{formatDate(p.fecha)}</span>
                                <span>{formatTime(p.hora)}</span>
                              </div>
                            )}
                          </td>
                        </tr>

                        {/* Expandable Sucesos Row */}
                        {expandedPartido === i && p.jugado && (
                          <tr className="border-b border-white/5 bg-white/5">
                            <td colSpan="4" className="px-4 py-4">
                              <div className="bg-surface-dark rounded-lg p-6 border border-border-dark">
                                <div className="grid grid-cols-2 gap-6">
                                  {/* Local */}
                                  <div>
                                    <h5 className="text-base font-black text-white mb-4 pb-2 border-b border-primary">
                                      {p.equipo_local}
                                    </h5>
                                    {p.sucesos?.goles_local?.length > 0 || p.sucesos?.amarillas_local?.length > 0 || p.sucesos?.rojas_local?.length > 0 ? (
                                      <>
                                        {p.sucesos?.goles_local?.length > 0 && (
                                          <div className="mb-3 pb-3 border-b border-border-dark">
                                            <p className="text-xs font-bold text-green-400 mb-2 uppercase tracking-wider">Goles</p>
                                            <ul className="text-sm text-white space-y-1">
                                              {p.sucesos.goles_local.map((s, j) => (
                                                <li key={`gol-local-${i}-${j}`} className="text-green-300 font-semibold">
                                                  <span className="text-gray-500 mr-2">Minuto {s.minuto}'</span>
                                                  {s.nombre}
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                        {p.sucesos?.amarillas_local?.length > 0 && (
                                          <div className="mb-3 pb-3 border-b border-border-dark">
                                            <p className="text-xs font-bold text-yellow-400 mb-2 uppercase tracking-wider">Amarillas</p>
                                            <ul className="text-sm text-white space-y-1">
                                              {p.sucesos.amarillas_local.map((s, j) => (
                                                <li key={`amarilla-local-${i}-${j}`} className="text-yellow-300 font-semibold">
                                                  <span className="text-gray-500 mr-2">Minuto {s.minuto}'</span>
                                                  {s.nombre}
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                        {p.sucesos?.rojas_local?.length > 0 && (
                                          <div>
                                            <p className="text-xs font-bold text-red-400 mb-2 uppercase tracking-wider">Rojas</p>
                                            <ul className="text-sm text-white space-y-1">
                                              {p.sucesos.rojas_local.map((s, j) => (
                                                <li key={`roja-local-${i}-${j}`} className="text-red-300 font-semibold">
                                                  <span className="text-gray-500 mr-2">Minuto {s.minuto}'</span>
                                                  {s.nombre}
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                      </>
                                    ) : (
                                      <p className="text-sm text-gray-500 italic">Sin sucesos registrados</p>
                                    )}
                                  </div>

                                  {/* Visitante */}
                                  <div>
                                    <h5 className="text-base font-black text-white mb-4 pb-2 border-b border-primary">
                                      {p.equipo_visitante}
                                    </h5>
                                    {p.sucesos?.goles_visitante?.length > 0 || p.sucesos?.amarillas_visitante?.length > 0 || p.sucesos?.rojas_visitante?.length > 0 ? (
                                      <>
                                        {p.sucesos?.goles_visitante?.length > 0 && (
                                          <div className="mb-3 pb-3 border-b border-border-dark">
                                            <p className="text-xs font-bold text-green-400 mb-2 uppercase tracking-wider">Goles</p>
                                            <ul className="text-sm text-white space-y-1">
                                              {p.sucesos.goles_visitante.map((s, j) => (
                                                <li key={`gol-visitante-${i}-${j}`} className="text-green-300 font-semibold">
                                                  <span className="text-gray-500 mr-2">Minuto {s.minuto}'</span>
                                                  {s.nombre}
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                        {p.sucesos?.amarillas_visitante?.length > 0 && (
                                          <div className="mb-3 pb-3 border-b border-border-dark">
                                            <p className="text-xs font-bold text-yellow-400 mb-2 uppercase tracking-wider">Amarillas</p>
                                            <ul className="text-sm text-white space-y-1">
                                              {p.sucesos.amarillas_visitante.map((s, j) => (
                                                <li key={`amarilla-visitante-${i}-${j}`} className="text-yellow-300 font-semibold">
                                                  <span className="text-gray-500 mr-2">Minuto {s.minuto}'</span>
                                                  {s.nombre}
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                        {p.sucesos?.rojas_visitante?.length > 0 && (
                                          <div>
                                            <p className="text-xs font-bold text-red-400 mb-2 uppercase tracking-wider">Rojas</p>
                                            <ul className="text-sm text-white space-y-1">
                                              {p.sucesos.rojas_visitante.map((s, j) => (
                                                <li key={`roja-visitante-${i}-${j}`} className="text-red-300 font-semibold">
                                                  <span className="text-gray-500 mr-2">Minuto {s.minuto}'</span>
                                                  {s.nombre}
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                      </>
                                    ) : (
                                      <p className="text-sm text-gray-500 italic">Sin sucesos registrados</p>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
          </div>
        )}

        {/* Standings Table */}
        {(clasificacion.length > 0 || equipo) && (
          <div className="border-t border-border-dark pt-6" id="clasificacion-section">
            <div
              className="flex items-center gap-2 cursor-pointer mb-4 justify-center"
              onClick={() => setClasificacionOpen(!clasificacionOpen)}
            >
              <span className={`material-symbols-outlined text-white transition-transform ${clasificacionOpen ? '' : '-rotate-90'}`}>
                expand_more
              </span>
              <h4 className="text-lg font-bold text-white">Clasificación</h4>
            </div>

            {clasificacionOpen && (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-left border-b border-white/10">#</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-left border-b border-white/10">Equipo</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center border-b border-white/10 w-24">Racha</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center border-b border-white/10 w-16">PJ</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center border-b border-white/10 w-16">PG</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center border-b border-white/10 w-16">PE</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center border-b border-white/10 w-16">PP</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center border-b border-white/10 w-16">GF</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center border-b border-white/10 w-16">GC</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center border-b border-white/10 w-16">DG</th>
                        <th className="px-4 py-4 text-xs font-bold uppercase tracking-widest text-primary text-center border-b border-white/10 w-16">Pts</th>
                      </tr>
                    </thead>
                    <tbody>
                      {clasificacion.map(reg => (
                        <tr
                          key={reg.posicion}
                          className={`border-b border-white/5 hover:bg-white/5 transition-colors border-l-4 ${equipo === reg.equipo
                              ? 'bg-yellow-500/10 border-l-yellow-500'
                              : reg.posicion <= 4
                                ? 'border-l-blue-500'
                                : reg.posicion <= 7
                                  ? 'border-l-orange-500'
                                  : reg.posicion <= 17
                                    ? 'border-l-gray-500'
                                    : 'border-l-red-500'
                            }`}
                        >
                          <td className="px-4 py-3 text-center font-bold text-primary">{reg.posicion}</td>
                          <td className="px-4 py-3">
                            <a
                              href={`/equipo/${encodeURIComponent(reg.equipo)}`}
                              className="flex items-center gap-3 hover:text-primary transition-colors cursor-pointer"
                            >
                              <TeamShield
                                escudo={reg.equipo_escudo}
                                nombre={reg.equipo}
                                className="size-8 rounded-lg object-contain drop-shadow-md"
                              />
                              <span
                                className={`font-bold text-sm ${equipo === reg.equipo ? 'text-yellow-400' : 'text-white'
                                  }`}
                              >
                                {reg.equipo}
                              </span>
                            </a>
                          </td>
                          <td className="px-4 py-3 text-center">
                            <div className="flex justify-center gap-1">
                              {reg.racha_detalles && reg.racha_detalles.length > 0 ? (
                                reg.racha_detalles.map((detalle, idx) => (
                                  <div key={idx} className="relative inline-block racha-item group">
                                    <span
                                      className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white mx-0.5 ${detalle.resultado === 'V' ? 'bg-green-500' :
                                          detalle.resultado === 'E' ? 'bg-yellow-500' :
                                            detalle.resultado === 'D' ? 'bg-red-500' :
                                              'bg-gray-500'
                                        }`}
                                    >
                                      {detalle.resultado}
                                    </span>
                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none z-20 transition-opacity duration-200">
                                      {detalle.titulo}
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <span className="text-gray-400">—</span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-center text-gray-300">
                            {(reg.partidos_ganados || 0) + (reg.partidos_empatados || 0) + (reg.partidos_perdidos || 0)}
                          </td>
                          <td className="px-4 py-3 text-center text-green-400">{reg.partidos_ganados}</td>
                          <td className="px-4 py-3 text-center text-yellow-400">{reg.partidos_empatados}</td>
                          <td className="px-4 py-3 text-center text-red-400">{reg.partidos_perdidos}</td>
                          <td className="px-4 py-3 text-center text-gray-300">{reg.goles_favor}</td>
                          <td className="px-4 py-3 text-center text-gray-300">{reg.goles_contra}</td>
                          <td
                            className={`px-4 py-3 text-center font-bold ${reg.diferencia_goles > 0
                                ? 'text-green-400'
                                : reg.diferencia_goles < 0
                                  ? 'text-red-400'
                                  : 'text-gray-400'
                              }`}
                          >
                            {reg.diferencia_goles > 0 ? `+${reg.diferencia_goles}` : reg.diferencia_goles}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span
                              className={`px-3 py-1.5 rounded-lg text-sm font-black ${reg.posicion <= 4 ? 'bg-primary/20 text-primary' : 'text-white'
                                }`}
                            >
                              {reg.puntos}
                            </span>
                          </td>
                        </tr>
                      ))}
                      {clasificacion.length === 0 && (
                        <tr>
                          <td colSpan="11" className="px-4 py-8 text-center text-gray-500">
                            Sin datos para esta jornada
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Legend */}
                <div className="pt-4 mt-4 border-t border-border-dark">
                  <div className="flex flex-wrap gap-6 text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-blue-500 rounded"></div>
                      <span className="text-gray-400">Champions League</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-orange-500 rounded"></div>
                      <span className="text-gray-400">Europa League</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-gray-500 rounded"></div>
                      <span className="text-gray-400">Resto</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-red-500 rounded"></div>
                      <span className="text-gray-400">Descenso</span>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {clasificacion.length === 0 && !equipo && (
          <div className="p-6 text-center">
            <div className="mb-4">
              <span className="material-symbols-outlined text-4xl text-gray-500">schedule</span>
            </div>
            <p className="text-gray-400 text-lg mb-2">No hay datos de clasificación disponibles.</p>
            <p className="text-gray-500 text-sm">Quizás estés viendo una jornada en el futuro.</p>
          </div>
        )}
      </GlassPanel>
    </div>
  )
}

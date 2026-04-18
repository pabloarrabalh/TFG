import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import api from '../services/apiClient'
import HelpButton from '../components/ui/HelpButton'
import ComparisonMetricsCards from '../components/comparison/ComparisonMetricsCards'
import { COMPARISON_DOMAINS } from '../components/comparison/comparisonConfig'
import { backendUrl } from '../config/backend'
import '../styles/jugador.css'
import { useTour } from '../context/TourContext'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'

// Caché de banderas
const flagCache = JSON.parse(localStorage.getItem('flag_cache') || '{}')

// Hook para cargar banderas
const useFlag = (nationality) => {
  const [flagUrl, setFlagUrl] = useState(null)
  
  useEffect(() => {
    if (!nationality || nationality === '0' || nationality === '—') {
      setFlagUrl(null)
      return
    }
    
    if (flagCache[nationality]) {
      setFlagUrl(flagCache[nationality])
      return
    }
    
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

function FlagIcon({ nationality }) {
  const flagUrl = useFlag(nationality)
  
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

export default function JugadorPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { tourActive, isPhaseCompleted, markPhaseCompleted, endTour, isManualExit } = useTour()
  const driverRef = useRef(null)
  
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeHistoricoView, setActiveHistoricoView] = useState('general')
  const [compareModalOpen, setCompareModalOpen] = useState(false)
  const [radarGenerated, setRadarGenerated] = useState(false)
  const [radarLoading, setRadarLoading] = useState(false)
  const [radarMediaGeneral, setRadarMediaGeneral] = useState(0)
  const radarContainerRef = useRef(null)
  const chartInstanceRef = useRef(null)
  const histogramScrollRef = useRef(null)
  
  const [comparisonEntries, setComparisonEntries] = useState([])
  const [season1, setSeason1] = useState('')
  const [season2, setSeason2] = useState('')
  const [domain, setDomain] = useState('general')
  
  // Estados para expandir/colapsar secciones de defensa
  const [expandDuelosTotales, setExpandDuelosTotales] = useState(false)
  const [expandDuelosAereos, setExpandDuelosAereos] = useState(false)

  // AI Insight
  const [insights, setInsights] = useState([])
  const [insightsLoading, setInsightsLoading] = useState(false)
  
  // Estados para popovers
  const [rolePopover, setRolePopover] = useState(null)
  const [percentilePopover, setPercentilePopover] = useState(null)
  const rolePopoverRef = useRef(null)
  const percentilePopoverRef = useRef(null)

  const temporada = searchParams.get('temporada') || '25/26'

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const { data: d } = await api.get(`/api/jugador/${id}/?temporada=${temporada}`)
      setData(d)
    } catch (e) {
      // Error loading jugador
    } finally {
      setLoading(false)
    }
  }, [id, temporada])

  useEffect(() => { fetchData() }, [fetchData])

  // Cargar insights cuando los datos del jugador están listos
  useEffect(() => {
    if (!data) return
    setInsightsLoading(true)
    fetch(backendUrl(`/api/jugador-insight/?jugador_id=${id}&temporada=${encodeURIComponent(temporada)}`))
      .then(r => r.json())
      .then(d => setInsights(d.insights || []))
      .catch(() => setInsights([]))
      .finally(() => setInsightsLoading(false))
  }, [data, id, temporada])

  // Cargar Chart.js dinámicamente
  useEffect(() => {
    if (!window.Chart) {
      const script = document.createElement('script')
      script.src = 'https://cdn.jsdelivr.net/npm/chart.js'
      script.async = true
      document.body.appendChild(script)
    }
  }, [])
  
  // Cerrar popovers al hacer click fuera, scroll o escape
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (rolePopoverRef.current && !rolePopoverRef.current.contains(e.target) && !e.target.closest('.role-badge-btn')) {
        setRolePopover(null)
      }
      if (percentilePopoverRef.current && !percentilePopoverRef.current.contains(e.target) && !e.target.closest('[data-stat-percentile]')) {
        setPercentilePopover(null)
      }
    }
    
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        setRolePopover(null)
        setPercentilePopover(null)
      }
    }
    
    const handleScroll = () => {
      setRolePopover(null)
      setPercentilePopover(null)
    }
    
    document.addEventListener('click', handleClickOutside)
    document.addEventListener('keydown', handleEscape)
    window.addEventListener('scroll', handleScroll, true)
    document.addEventListener('scroll', handleScroll, true)
    
    return () => {
      document.removeEventListener('click', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
      window.removeEventListener('scroll', handleScroll, true)
      document.removeEventListener('scroll', handleScroll, true)
    }
  }, [])
  
  // Función para formatear nombre de rol
  const formatRoleName = (roleName) => {
    return roleName
      .replace(/_/g, ' ')
      .split(' ')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ')
  }
  
  // Función para abrir popover de rol
  const openRolePopover = (e, roleName, position, value) => {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    setRolePopover({
      name: formatRoleName(roleName),
      description: data?.descripciones_roles?.[roleName] || 'Sin descripción disponible',
      position,
      value,
      x: rect.left,
      y: rect.bottom + 8
    })
  }
  
  // Función para abrir popover de percentil
  const openPercentilePopover = (e, statName, percentile) => {
    e.stopPropagation()
    const rect = e.currentTarget.getBoundingClientRect()
    setPercentilePopover({
      stat: statName,
      percentile,
      x: rect.left,
      y: rect.bottom + 8
    })
  }
  
  // Función para verificar si una stat es top (percentil >= 90)
  const isTopStat = (category, field) => {
    if (!data?.percentiles || !category || !field) return false
    const percentile = data.percentiles[category]?.[field]
    return percentile !== undefined && percentile !== null && percentile >= 90
  }
  
  // Función para obtener el percentil de una stat
  const getPercentile = (category, field) => {
    if (!data?.percentiles || !category || !field) return null
    return data.percentiles[category]?.[field]
  }

  const generateRadar = async () => {
    if (radarGenerated) return
    
    setRadarLoading(true)
    
    try {
      const tempDb = temporada.replace('/', '_')
      const response = await api.get(`/api/radar/${id}/${tempDb}/`)
      
      if (response.data && response.data.status === 'success') {
        renderRadar(
          response.data.data.radar_values,
          response.data.data.media_general,
          response.data.data.labels,
        )
      }
    } catch (error) {
      // Error loading radar
      setRadarLoading(false)
    }
  }

  const renderRadar = (radarValues, mediaGeneral, radarLabels) => {
    // Guardar el media_general en estado
    setRadarMediaGeneral(mediaGeneral || 0)
    
    const waitForChart = () => {
      if (typeof window.Chart === 'undefined') {
        setTimeout(waitForChart, 100)
        return
      }
      
      if (!radarContainerRef.current) return
      
      const container = radarContainerRef.current
      container.innerHTML = ''
      
      const canvas = document.createElement('canvas')
      canvas.width = 300
      canvas.height = 300
      container.appendChild(canvas)
      
      const ctx = canvas.getContext('2d')
      
      chartInstanceRef.current = new window.Chart(ctx, {
        type: 'radar',
        data: {
          labels: radarLabels || ['Ataque', 'Defensa', 'Regates', 'Pases', 'Comportamiento', 'Minutos', 'Puntos Fantasy'],
          datasets: [{
            label: 'Perfil Táctico',
            data: radarValues,
            borderColor: 'rgb(251, 146, 60)',
            backgroundColor: 'rgba(251, 146, 60, 0.3)',
            borderWidth: 2,
            pointRadius: 4,
            pointBackgroundColor: 'rgb(251, 146, 60)',
            pointBorderColor: '#fff',
            pointBorderWidth: 1.5,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          plugins: {
            legend: {
              display: false
            }
          },
          scales: {
            r: {
              min: 0,
              max: 100,
              ticks: {
                color: 'rgba(255,255,255,0.6)',
                font: { size: 9 },
                stepSize: 20
              },
              grid: {
                color: 'rgba(255,255,255,0.1)'
              },
              angleLines: {
                color: 'rgba(255,255,255,0.1)'
              }
            }
          }
        }
      })
      
      setRadarLoading(false)
      setRadarGenerated(true)
    }
    
    setTimeout(waitForChart, 200)
  }

  const normalizeHistoricoStats = (row = {}) => {
    const goles = Number(row.goles || 0)
    const xg = Number(row.xg || 0)
    const asistencias = Number(row.asistencias || 0)
    const xag = Number(row.xag || 0)

    return {
      puntos_por_partido: Number(row.puntos_por_partido || 0),
      partidos: Number(row.pj || row.partidos || 0),
      minutos: Number(row.minutos || 0),
      goles,
      asistencias,
      xg,
      xag,
      goles_vs_xg: Number((goles - xg).toFixed(2)),
      asistencias_vs_xag: Number((asistencias - xag).toFixed(2)),
      tiros: Number(row.tiros || 0),
      tiros_puerta: Number(row.tiros_puerta || 0),
      pases: Number(row.pases || 0),
      pases_accuracy: Number(row.pases_accuracy || 0),
      regates_completados: Number(row.regates_completados || 0),
      regates_fallidos: Number(row.regates_fallidos || 0),
      conducciones: Number(row.conducciones || 0),
      conducciones_progresivas: Number(row.conducciones_progresivas || 0),
      entradas: Number(row.entradas || 0),
      despejes: Number(row.despejes || 0),
      duelos_totales: Number(row.duelos_totales || 0),
      duelos_ganados: Number(row.duelos_ganados || 0),
      duelos_perdidos: Number(row.duelos_perdidos || 0),
      duelos_aereos_totales: Number(row.duelos_aereos_totales || 0),
      amarillas: Number(row.amarillas || 0),
      rojas: Number(row.rojas || 0),
    }
  }

  const buildTotalHistoricoStats = (historicoData = []) => {
    if (!historicoData.length) return {}

    const totals = historicoData.reduce((acc, row) => ({
      puntos_totales: acc.puntos_totales + Number(row.puntos_totales || 0),
      partidos: acc.partidos + Number(row.pj || 0),
      minutos: acc.minutos + Number(row.minutos || 0),
      goles: acc.goles + Number(row.goles || 0),
      asistencias: acc.asistencias + Number(row.asistencias || 0),
      tiros: acc.tiros + Number(row.tiros || 0),
      tiros_puerta: acc.tiros_puerta + Number(row.tiros_puerta || 0),
      xg: acc.xg + Number(row.xg || 0),
      xag: acc.xag + Number(row.xag || 0),
      pases: acc.pases + Number(row.pases || 0),
      pases_accuracy_sum: acc.pases_accuracy_sum + Number(row.pases_accuracy || 0),
      regates_completados: acc.regates_completados + Number(row.regates_completados || 0),
      regates_fallidos: acc.regates_fallidos + Number(row.regates_fallidos || 0),
      conducciones: acc.conducciones + Number(row.conducciones || 0),
      conducciones_progresivas: acc.conducciones_progresivas + Number(row.conducciones_progresivas || 0),
      entradas: acc.entradas + Number(row.entradas || 0),
      despejes: acc.despejes + Number(row.despejes || 0),
      duelos_totales: acc.duelos_totales + Number(row.duelos_totales || 0),
      duelos_ganados: acc.duelos_ganados + Number(row.duelos_ganados || 0),
      duelos_perdidos: acc.duelos_perdidos + Number(row.duelos_perdidos || 0),
      duelos_aereos_totales: acc.duelos_aereos_totales + Number(row.duelos_aereos_totales || 0),
      amarillas: acc.amarillas + Number(row.amarillas || 0),
      rojas: acc.rojas + Number(row.rojas || 0),
    }), {
      puntos_totales: 0,
      partidos: 0,
      minutos: 0,
      goles: 0,
      asistencias: 0,
      tiros: 0,
      tiros_puerta: 0,
      xg: 0,
      xag: 0,
      pases: 0,
      pases_accuracy_sum: 0,
      regates_completados: 0,
      regates_fallidos: 0,
      conducciones: 0,
      conducciones_progresivas: 0,
      entradas: 0,
      despejes: 0,
      duelos_totales: 0,
      duelos_ganados: 0,
      duelos_perdidos: 0,
      duelos_aereos_totales: 0,
      amarillas: 0,
      rojas: 0,
    })

    return {
      puntos_por_partido: totals.partidos > 0 ? totals.puntos_totales / totals.partidos : 0,
      pj: totals.partidos,
      minutos: totals.minutos,
      goles: totals.goles,
      asistencias: totals.asistencias,
      tiros: totals.tiros,
      tiros_puerta: totals.tiros_puerta,
      xg: totals.xg,
      xag: totals.xag,
      pases: totals.pases,
      pases_accuracy: historicoData.length > 0 ? totals.pases_accuracy_sum / historicoData.length : 0,
      regates_completados: totals.regates_completados,
      regates_fallidos: totals.regates_fallidos,
      conducciones: totals.conducciones,
      conducciones_progresivas: totals.conducciones_progresivas,
      entradas: totals.entradas,
      despejes: totals.despejes,
      duelos_totales: totals.duelos_totales,
      duelos_ganados: totals.duelos_ganados,
      duelos_perdidos: totals.duelos_perdidos,
      duelos_aereos_totales: totals.duelos_aereos_totales,
      amarillas: totals.amarillas,
      rojas: totals.rojas,
    }
  }

  const executeComparison = () => {
    if (!season1 || !season2 || !data) return

    setExpandDuelosTotales(false)
    setExpandDuelosAereos(false)

    const historicoData = data.historico || []
    const getSeasonStats = (season) => {
      if (season === 'total') return buildTotalHistoricoStats(historicoData)
      return historicoData.find((row) => row.temporada === season) || {}
    }

    const stats1 = normalizeHistoricoStats(getSeasonStats(season1))
    const stats2 = normalizeHistoricoStats(getSeasonStats(season2))

    setComparisonEntries([
      {
        id: `season-${season1}`,
        label: season1 === 'total' ? 'Ultimas 3 temporadas' : season1,
        minutes: stats1.minutos,
        stats: stats1,
      },
      {
        id: `season-${season2}`,
        label: season2 === 'total' ? 'Ultimas 3 temporadas' : season2,
        minutes: stats2.minutos,
        stats: stats2,
      },
    ])
  }

  // ── Tour guiado ──────────────────────────────────────────────────────────────
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!tourActive || isPhaseCompleted('jugador') || loading || !data) return
    const timer = setTimeout(() => {
      driverRef.current = driver({
        showProgress: true,
        allowClose: false,
        nextBtnText: 'Siguiente →',
        prevBtnText: '← Anterior',
        doneBtnText: 'Ver Amigos →',
        steps: [
          {
            element: '#tour-jugador-header',
            popover: {
              title: 'Ficha del jugador',
              description: 'Todo sobre el jugador: nombre, posición, edad, equipo y estadísticas rápidas de la temporada.',
              side: 'bottom',
              align: 'start',
            },
          },
          {
            element: '#tour-jugador-stats',
            popover: {
              title: 'Estadísticas detalladas',
              description: 'Estadísticas por categoría: ataque, defensa, pases... Los estadísticos en dorado están en el percentil 90 o superior.',
              side: 'bottom',
              align: 'start',
            },
          },
          {
            element: '#tour-jugador-histograma',
            popover: {
              title: 'Puntos por partido',
              description: 'Histograma desplazable con los puntos fantasy de cada partido de la temporada. Haz scroll para ver jornadas antiguas.',
              side: 'top',
              align: 'center',
            },
          },
          {
            element: '#tour-jugador-radar',
            popover: {
              title: 'Perfil táctico (Radar)',
              description: 'Genera un gráfico radar que compara las estadísticas del jugador con la media de su posición en percentiles.',
              side: 'left',
              align: 'start',
            },
          },
          {
            element: '#tour-jugador-predicciones',
            popover: {
              title: 'Predicciones vs realidad',
              description: 'Compara la puntuación predicha por la IA con la puntuación real obtenida en cada jornada. Evalúa la precisión del modelo.',
              side: 'top',
              align: 'center',
            },
          },
        ],
        onDestroyStarted: () => {
          driverRef.current?.destroy()
          markPhaseCompleted('jugador')
          endTour()
          navigate('/amigos')
        },
      })
      driverRef.current.drive()
    }, 800)
    return () => {
      clearTimeout(timer)
      driverRef.current?.destroy()
    }
  }, [tourActive, loading, data])

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background-dark">
        <div className="text-white text-xl">Cargando...</div>
      </div>
    )
  }

  const {
    jugador = {},
    equipo_temporada = null,
    posicion = '',
    edad = 0,
    stats = {},
    temporadas_disponibles = [],
    es_carrera = false,
    temporada_obj = {},
    temporada_display = '',
    ultimos_8 = [],
    roles = [],
    es_roles_por_temporada = false,
    radar_values = [],
    media_general = 0,
    historico = [],
    percentiles = {},
    descripciones_roles = {},
    predicciones = [],
  } = data || {}

  return (
    <div className="p-6 space-y-6 bg-background-dark min-h-full">
      {/* HEADER CON INFO DEL JUGADOR */}
      <div id="tour-jugador-header" className="glass-panel header-gradient rounded-2xl p-8 mb-6">
        <div className="flex flex-col md:flex-row gap-8 items-start md:items-center">
          {/* Badge y Info básica */}
          <div className="flex gap-6 items-center">
            <div className="player-badge">
              {jugador.nombre?.[0]?.toUpperCase() || '?'}
            </div>
            
            <div>
              <h1 className="text-4xl md:text-5xl font-black text-white mb-3 tracking-tight">
                {jugador.nombre} <br className="hidden md:block" />{jugador.apellido?.toUpperCase()}
              </h1>
              
              <div className="flex flex-wrap gap-2 mb-4">
                {posicion && (
                  <span className="posicion-badge">
                    <span className="material-symbols-outlined align-middle mr-2 icon-sm">sports_soccer</span>
                    {posicion}
                  </span>
                )}
                
                {jugador.nacionalidad && (
                  <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-white/5 border border-white/10">
                    <FlagIcon nationality={jugador.nacionalidad} />
                  </div>
                )}
                
                {edad > 0 && (
                  <span className="px-3 py-2 rounded-lg bg-white/10 text-gray-300 text-sm">
                    {edad} años
                  </span>
                )}
              </div>
              
              {equipo_temporada && (
                <div className="flex items-center gap-4 mb-2">
                  <img 
                    src={backendUrl(equipo_temporada.equipo.escudo)}
                    alt={equipo_temporada.equipo.nombre}
                    className="h-16 w-16 object-contain"
                    onError={(e) => e.target.style.display = 'none'}
                  />
                  <span className="text-lg font-bold text-cyan-300">{equipo_temporada.equipo.nombre}</span>
                </div>
              )}
            </div>
          </div>
          
          {/* Stats rápidas */}
          <div className="grid grid-cols-2 gap-3 md:ml-auto">
            <div className="stat-mini">
              <div className="stat-value text-primary">{stats.goles || 0}</div>
              <div className="stat-label">Goles</div>
            </div>
            <div className="stat-mini">
              <div className="stat-value text-green-400">{stats.asistencias || 0}</div>
              <div className="stat-label">Asistencias</div>
            </div>
            <div className="stat-mini">
              <div className="stat-value text-blue-400">{stats.promedio_puntos || 0}</div>
              <div className="stat-label">Promedio</div>
            </div>
            <div className="stat-mini">
              <div className="stat-value text-yellow-400">{stats.partidos || 0}</div>
              <div className="stat-label">Partidos</div>
            </div>
          </div>
        </div>
      </div>

      {/* SELECTOR DE TEMPORADAS */}
      {temporadas_disponibles && temporadas_disponibles.length > 0 && (
        <div className="glass-panel rounded-2xl p-6 mb-6">
          <h3 className="text-sm font-bold text-gray-300 mb-4 uppercase tracking-widest">SELECCIONA TEMPORADA</h3>
          <div className="flex gap-2 flex-wrap">
            <a
              href={`/jugador/${id}?temporada=carrera`}
              className={`temporada-btn ${es_carrera ? 'active' : ''}`}
            >
              Últimas 3 temporadas
            </a>
            {temporadas_disponibles.map(temp => (
              <a
                key={temp.nombre}
                href={`/jugador/${id}?temporada=${temp.display}`}
                className={`temporada-btn ${!es_carrera && temp.nombre === temporada_obj.nombre ? 'active' : ''}`}
              >
                {temp.display}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* GRID PRINCIPAL: Estadísticas + Gráfico + Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* IZQUIERDA: Stats y Gráfico (col-span-8) */}
        <div className="lg:col-span-8 space-y-6">
          {/* Estadísticas de la temporada en grid */}
          <div id="tour-jugador-stats" className="glass-panel rounded-2xl p-6">
            <h2 className="text-2xl font-black text-white mb-6 uppercase tracking-wider">
              Estadísticas {temporada_display}
            </h2>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="stat-mini">
                <div className="stat-value">{stats.partidos || 0}</div>
                <div className="stat-label">Partidos</div>
              </div>
              <div className="stat-mini">
                <div className="stat-value">{stats.minutos || 0}</div>
                <div className="stat-label">Minutos</div>
              </div>
              <div className="stat-mini">
                <div className="stat-value text-green-400">{stats.goles || 0}</div>
                <div className="stat-label">Goles</div>
              </div>
              <div className="stat-mini">
                <div className="stat-value text-yellow-400">{stats.asistencias || 0}</div>
                <div className="stat-label">Asistencias</div>
              </div>
            </div>

            {/* ESTADÍSTICAS ORGANIZADAS EN BLOQUES */}
            <div className="mt-8 pt-8 border-t border-border-dark space-y-8">
              
              {/* ATAQUE Y ORGANIZACIÓN lado a lado */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* BLOQUE ATAQUE */}
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
                    <span className="material-symbols-outlined text-red-400 icon-xl">local_fire_department</span>
                    Ataque
                  </h3>
                  <div className="space-y-2">
                    <div 
                      className={`flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2 ${isTopStat('ataque', 'goles') ? 'stat-golden' : ''}`}
                      onClick={(e) => isTopStat('ataque', 'goles') && openPercentilePopover(e, 'Goles', getPercentile('ataque', 'goles'))}
                      data-stat-percentile={isTopStat('ataque', 'goles') ? 'true' : undefined}
                      data-stat-category="ataque"
                      data-stat-field="goles"
                    >
                      <span className="text-sm text-gray-300">Goles</span>
                      <span className="text-lg font-bold text-white">{stats.ataque?.goles || 0}</span>
                    </div>
                    <div 
                      className={`flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2 ${isTopStat('ataque', 'xg') ? 'stat-golden' : ''}`}
                      onClick={(e) => isTopStat('ataque', 'xg') && openPercentilePopover(e, 'xG', getPercentile('ataque', 'xg'))}
                      data-stat-percentile={isTopStat('ataque', 'xg') ? 'true' : undefined}
                      data-stat-category="ataque"
                      data-stat-field="xg"
                    >
                      <span className="text-sm text-gray-300">xG</span>
                      <span className="text-lg font-bold text-white">{stats.ataque?.xg || 0}</span>
                    </div>
                    <div 
                      className={`flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2 ${isTopStat('ataque', 'tiros') ? 'stat-golden' : ''}`}
                      onClick={(e) => isTopStat('ataque', 'tiros') && openPercentilePopover(e, 'Total Tiros', getPercentile('ataque', 'tiros'))}
                      data-stat-percentile={isTopStat('ataque', 'tiros') ? 'true' : undefined}
                      data-stat-category="ataque"
                      data-stat-field="tiros"
                    >
                      <span className="text-sm text-gray-300">Total Tiros</span>
                      <span className="text-lg font-bold text-white">{stats.ataque?.tiros || 0}</span>
                    </div>
                    <div 
                      className={`flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2 ${isTopStat('ataque', 'tiros_puerta') ? 'stat-golden' : ''}`}
                      onClick={(e) => isTopStat('ataque', 'tiros_puerta') && openPercentilePopover(e, 'Tiros a Puerta', getPercentile('ataque', 'tiros_puerta'))}
                      data-stat-percentile={isTopStat('ataque', 'tiros_puerta') ? 'true' : undefined}
                      data-stat-category="ataque"
                      data-stat-field="tiros_puerta"
                    >
                      <span className="text-sm text-gray-300">Tiros a Puerta</span>
                      <span className="text-lg font-bold text-white">{stats.ataque?.tiros_puerta || 0}</span>
                    </div>
                  </div>
                </div>

                {/* BLOQUE ORGANIZACIÓN */}
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
                    <span className="material-symbols-outlined text-blue-400 icon-xl">hub</span>
                    Pase y Asistencias
                  </h3>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Asistencias</span>
                      <span className="text-lg font-bold text-white">{stats.asistencias || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">xA</span>
                      <span className="text-lg font-bold text-white">{stats.organizacion?.xag || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Pases Totales</span>
                      <span className="text-lg font-bold text-white">{stats.organizacion?.pases || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Precisión Pases</span>
                      <span className="text-lg font-bold text-white">{stats.organizacion?.pases_accuracy || 0}%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* REGATES E IMPULSIÓN Y DEFENSA lado a lado */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* BLOQUE REGATES */}
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
                    <span className="material-symbols-outlined text-purple-400 icon-xl">sprint</span>
                    Regates e Impulsión
                  </h3>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Regates Exitosos</span>
                      <span className="text-lg font-bold text-white">{stats.regates?.regates_completados || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Regates Fallidos</span>
                      <span className="text-lg font-bold text-white">{stats.regates?.regates_fallidos || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Conducciones</span>
                      <span className="text-lg font-bold text-white">{stats.regates?.conducciones || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Cond. Progresivas</span>
                      <span className="text-lg font-bold text-white">{stats.regates?.conducciones_progresivas || 0}</span>
                    </div>
                  </div>
                </div>

                {/* BLOQUE DEFENSA */}
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
                    <span className="material-symbols-outlined text-green-400 icon-xl">shield</span>
                    Defensa
                  </h3>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Entradas</span>
                      <span className="text-lg font-bold text-white">{stats.defensa?.entradas || 0}</span>
                    </div>
                    
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Despejes</span>
                      <span className="text-lg font-bold text-white">{stats.defensa?.despejes || 0}</span>
                    </div>
                    
                    {/* Duelos Totales - Botón Colapsable */}
                    <button
                      onClick={() => setExpandDuelosTotales(!expandDuelosTotales)}
                      className="w-full flex justify-between items-center bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg px-4 py-2 transition-colors"
                    >
                      <span className="text-sm text-gray-300">Duelos Totales</span>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-white">{stats.defensa?.duelos_totales || 0}</span>
                        <span className={`material-symbols-outlined text-sm transition-transform ${expandDuelosTotales ? 'rotate-180' : ''}`}>expand_more</span>
                      </div>
                    </button>
                    
                    {expandDuelosTotales && (
                      <div className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 ml-2 space-y-2">
                        <p className="text-xs text-gray-400 font-bold">Detalle de Duelos</p>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-300">Ganados</span>
                          <span className="text-lg font-bold text-green-400">{stats.defensa?.duelos_ganados || 0}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-300">Perdidos</span>
                          <span className="text-lg font-bold text-red-400">{stats.defensa?.duelos_perdidos || 0}</span>
                        </div>
                      </div>
                    )}
                    
                    {/* Duelos Aéreos - Botón Colapsable */}
                    <button
                      onClick={() => setExpandDuelosAereos(!expandDuelosAereos)}
                      className="w-full flex justify-between items-center bg-white/5 border border-white/10 hover:bg-white/10 rounded-lg px-4 py-2 transition-colors"
                    >
                      <span className="text-sm text-gray-300">Duelos Aéreos</span>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-white">{stats.defensa?.duelos_aereos_totales || 0}</span>
                        <span className={`material-symbols-outlined text-sm transition-transform ${expandDuelosAereos ? 'rotate-180' : ''}`}>expand_more</span>
                      </div>
                    </button>
                    
                    {expandDuelosAereos && (
                      <div className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 ml-2 space-y-2">
                        <p className="text-xs text-gray-400 font-bold">Detalle de Duelos Aéreos</p>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-300">Ganados</span>
                          <span className="text-lg font-bold text-green-400">{stats.defensa?.duelos_aereos_ganados || 0}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-gray-300">Perdidos</span>
                          <span className="text-lg font-bold text-red-400">{stats.defensa?.duelos_aereos_perdidos || 0}</span>
                        </div>
                        <div className="flex justify-between items-center pt-2 border-t border-white/10">
                          <span className="text-sm text-gray-400">Iguales</span>
                          <span className="text-lg font-bold text-gray-300">{(stats.defensa?.duelos_aereos_totales || 0) - (stats.defensa?.duelos_aereos_ganados || 0) - (stats.defensa?.duelos_aereos_perdidos || 0)}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* COMPORTAMIENTO */}
              <div>
                <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
                  <span className="material-symbols-outlined text-yellow-400 icon-xl">flag</span>
                  Comportamiento
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                    <span className="text-sm text-gray-300">Amarillas</span>
                    <span className="text-lg font-bold text-yellow-400">{stats.comportamiento?.amarillas || 0}</span>
                  </div>
                  <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                    <span className="text-sm text-gray-300">Rojas</span>
                    <span className="text-lg font-bold text-red-500">{stats.comportamiento?.rojas || 0}</span>
                  </div>
                </div>
              </div>

              {/* BLOQUE PORTERO (condicional) */}
              {posicion === "Portero" && (
                <div>
                  <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
                    <span className="material-symbols-outlined text-orange-400 icon-xl">sports_handball</span>
                    Portero
                  </h3>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Paradas</span>
                      <span className="text-lg font-bold text-white">{stats.portero?.paradas || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Goles Encajados</span>
                      <span className="text-lg font-bold text-white">{stats.portero?.goles_encajados || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Porterías a Cero</span>
                      <span className="text-lg font-bold text-white">{stats.portero?.porterias_cero || 0}</span>
                    </div>
                  </div>
                </div>
              )}

            </div>
          </div>

          {/* Gráfico de todos los partidos - HISTOGRAMA CON SCROLL */}
          <div id="tour-jugador-histograma" className="glass-panel rounded-2xl p-6">
            <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-wider">
              <span className="material-symbols-outlined align-middle mr-2 icon-lg">trending_up</span>
              Partidos de la Temporada (Puntos Fantasy)
            </h3>
            
            {ultimos_8 && ultimos_8.length > 0 ? (
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '12px' }}>
                {/* Botón izquierda */}
                <button
                  onClick={() => {
                    const container = histogramScrollRef.current
                    if (container) {
                      container.scrollBy({ left: -500, behavior: 'smooth' })
                    }
                  }}
                  className="flex-shrink-0 bg-gradient-to-r from-primary to-primary/70 hover:from-primary/90 hover:to-primary text-white rounded-lg p-3 transition-all shadow-lg hover:shadow-xl"
                  title="Ver partidos anteriores"
                >
                  <span className="material-symbols-outlined icon-2xl">navigate_before</span>
                </button>

                {/* Contenedor scrolleable */}
                <div
                  ref={histogramScrollRef}
                  style={{
                    overflowX: 'auto',
                    overflowY: 'hidden',
                    height: '340px',
                    flexShrink: 0,
                    flexGrow: 1,
                    scrollBehavior: 'smooth',
                    width: 0,  /* fuerza que el flex item no crezca más que su flex-grow */
                  }}
                >
                  {/* envoltorio interior que sí tiene el layout del histograma */}
                  <div
                    className="histogram-chart"
                    style={{ height: '320px' }}
                  >
                  {(() => {
                    // ultimos_8 now includes ALL jornadas from backend, even without data
                    if (!ultimos_8 || ultimos_8.length === 0) return null

                    return ultimos_8.map(stat => {
                      const jornada = stat.partido?.jornada?.numero_jornada
                      const puntos = stat.puntos_fantasy
                      const maxHeight = 230
                      const maxValue = 20
                      const minValue = -12
                      const range = maxValue - minValue

                      const barHeight = puntos !== null && puntos !== undefined
                        ? Math.max(4, ((Math.max(minValue, puntos) - minValue) / range) * maxHeight)
                        : null

                      const barClass = puntos === null ? '' :
                        puntos > 10 ? 'histogram-bar-high' :
                        puntos === 0 ? 'histogram-bar-zero' :
                        puntos > 0 ? 'histogram-bar-positive' :
                        'histogram-bar-negative'

                      return (
                        <div
                          key={jornada}
                          className="histogram-bar"
                          title={jornada ? `J${jornada}: ${puntos !== null ? puntos + ' pts' : 'sin datos'}` : ''}
                        >
                          {/* Valor arriba */}
                          <div className="histogram-bar-value">
                            {puntos !== null && puntos !== undefined ? (
                              <span style={{ color: puntos > 10 ? 'rgb(34,197,94)' : puntos > 0 ? 'rgb(34,197,94)' : 'rgb(239,68,68)' }}>
                                {puntos.toFixed(1)}
                              </span>
                            ) : null}
                          </div>
                          
                          {/* Barra */}
                          <div className={barClass} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '200px' }}>
                            {barHeight !== null ? (
                              <div
                                className="histogram-bar-inner"
                                style={{ width: 24, height: barHeight }}
                              />
                            ) : (
                              <div style={{
                                width: 24,
                                height: 8,
                                background: 'rgba(255,255,255,0.07)',
                                borderRadius: '4px 4px 0 0',
                                border: '1px dashed rgba(255,255,255,0.18)',
                              }} />
                            )}
                          </div>
                          
                          {/* Jornada */}
                          <div className="histogram-bar-label">J{jornada}</div>
                        </div>
                      )
                    })
                  })()}
                  </div>{/* fin histogram-chart inner */}
                </div>{/* fin scrolleable */}

                {/* Botón derecha */}
                <button
                  onClick={() => {
                    const container = histogramScrollRef.current
                    if (container) {
                      container.scrollBy({ left: 500, behavior: 'smooth' })
                    }
                  }}
                  className="flex-shrink-0 bg-gradient-to-r from-primary/70 to-primary hover:from-primary hover:to-primary/90 text-white rounded-lg p-3 transition-all shadow-lg hover:shadow-xl"
                  title="Ver próximos partidos"
                >
                  <span className="material-symbols-outlined icon-2xl">navigate_next</span>
                </button>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <span className="material-symbols-outlined text-4xl block mb-2">info</span>
                Sin datos de partidos
              </div>
            )}
          </div>

          {/* Gráfico Predicción vs Real - Solo para temporada actual */}
          {temporada === '25/26' && (
          <div id="tour-jugador-predicciones" className="glass-panel rounded-2xl p-6">
            <h3 className="text-xl font-bold text-white mb-2 uppercase tracking-wider">
              <span className="material-symbols-outlined align-middle mr-2 icon-lg">psychology</span>
              {predicciones && predicciones.some(p => p.is_early_jornada) ? (
                predicciones.every(p => p.is_early_jornada) ? 'Media vs Real' : 'Predicción / Media vs Real'
              ) : 'Predicción vs Real'}
            </h3>
            <p className="text-xs text-gray-400 mb-4">
              {predicciones && predicciones.some(p => p.is_early_jornada) 
                ? 'Para jornadas 1-5: Media histórica (datos insuficientes para predicción IA). Jornadas 6+: Predicción del modelo.'
                : 'Puntos predichos por el modelo vs. puntos reales obtenidos por jornada.'}
            </p>

            {predicciones && predicciones.length > 0 ? (
              <>
                {/* Leyenda */}
                <div className="flex gap-6 mb-2 text-xs flex-wrap">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm" style={{ background: 'linear-gradient(180deg,rgb(167,139,250),rgb(109,40,217))' }}></div>
                    <span className="text-gray-300">Predicción</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm" style={{ background: 'linear-gradient(180deg,rgb(156,163,175),rgb(107,114,128))' }}></div>
                    <span className="text-gray-300">Media</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm" style={{ background: 'rgba(255,255,255,0.15)', border: '1px dashed rgba(255,255,255,0.3)' }}></div>
                    <span className="text-gray-300">Sin datos (no disputado)</span>
                  </div>
                </div>
                <div className="pred-chart">
                  {(() => {
                    // Fill jornada gaps so skipped jornadas still render
                    const predMap = {}
                    predicciones.forEach(p => { predMap[p.jornada] = p })
                    const jornNums = predicciones.map(p => p.jornada).sort((a, b) => a - b)
                    const minJ = jornNums[0], maxJ = jornNums[jornNums.length - 1]
                    const allPreds = Array.from({ length: maxJ - minJ + 1 }, (_, i) => {
                      const j = minJ + i
                      return predMap[j] || { jornada: j, prediccion: null, real: null, is_early_jornada: j <= 5 }
                    })

                    return allPreds.map(p => {
                      const maxHeight = 250
                      const maxValue = 20
                      const minValue = -12
                      const range = maxValue - minValue

                      const predH = p.prediccion !== null
                        ? Math.max(4, ((p.prediccion - minValue) / range) * maxHeight)
                        : null

                      const realClass = p.real === null ? '' :
                        p.real > 10 ? 'histogram-bar-high' :
                        p.real === 0 ? 'histogram-bar-zero' :
                        p.real > 0 ? 'histogram-bar-positive' :
                        'histogram-bar-negative'

                      const realH = p.real !== null
                        ? Math.max(4, ((Math.max(minValue, p.real) - minValue) / range) * maxHeight)
                        : null

                      const label = p.is_early_jornada ? 'Media' : 'Pred'
                      const predGradient = p.is_early_jornada
                        ? 'linear-gradient(180deg,rgb(156,163,175),rgb(107,114,128))'
                        : 'linear-gradient(180deg,rgb(167,139,250),rgb(109,40,217))'
                      const predLabelColor = p.is_early_jornada ? 'rgb(156,163,175)' : 'rgb(167,139,250)'

                      // Generar tooltip dinámico
                      let tooltipText
                      if (p.prediccion === null && p.is_early_jornada) {
                        tooltipText = 'Sin datos suficientes para calcular la media de puntos previa'
                      } else {
                        tooltipText = `J${p.jornada} — ${label}: ${p.prediccion !== null ? p.prediccion.toFixed(1) : '—'} | Real: ${p.real ?? 'pendiente'}`
                      }

                      return (
                        <div
                          key={p.jornada}
                          className="histogram-bar"
                          style={{ minWidth: 52 }}
                          title={tooltipText}
                        >
                          {/* Valores arriba */}
                          <div className="histogram-bar-value" style={{ fontSize: '0.68rem', display: 'flex', gap: 4 }}>
                            {p.prediccion !== null && (
                              <span style={{ color: predLabelColor }}>{p.prediccion.toFixed(1)}</span>
                            )}
                            {p.real !== null && <span style={{ color: 'rgb(52,211,153)' }}>{p.real}</span>}
                          </div>
                          {/* Barras paralelas */}
                          <div className="histogram-bar-pred-pair">
                            {/* Predicción / Media */}
                            <div
                              className="histogram-bar-pred"
                              style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end' }}
                            >
                              {predH !== null ? (
                                <div
                                  className="histogram-bar-inner"
                                  style={{ width: 18, height: predH, background: predGradient }}
                                />
                              ) : (
                                <div style={{
                                  width: 18, height: 8,
                                  background: 'rgba(255,255,255,0.07)',
                                  borderRadius: '4px 4px 0 0',
                                  border: '1px dashed rgba(255,255,255,0.18)',
                                }} />
                              )}
                            </div>
                            {/* Real */}
                            <div
                              className={realClass}
                              style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end' }}
                            >
                              {realH !== null ? (
                                <div
                                  className="histogram-bar-inner"
                                  style={{ width: 18, height: realH }}
                                />
                              ) : (
                                <div style={{
                                  width: 18, height: 8,
                                  background: 'rgba(255,255,255,0.1)',
                                  borderRadius: '4px 4px 0 0',
                                  border: '1px dashed rgba(255,255,255,0.3)',
                                }} />
                              )}
                            </div>
                          </div>
                          <div className="histogram-bar-label">J{p.jornada}</div>
                        </div>
                      )
                    })
                  })()}
                </div>
              </>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <span className="material-symbols-outlined text-3xl block mb-2">model_training</span>
                <p className="text-sm">Aún no hay predicciones almacenadas para esta temporada.</p>
                <p className="text-xs mt-1 text-gray-500">
                  Las predicciones se generan automáticamente cuando se procesan estadísticas
                  de una jornada. También puedes lanzarlas manualmente:
                </p>
                <code className="block mt-2 text-xs bg-black/30 rounded px-3 py-2 text-green-400 font-mono text-left">
                  python manage.py generar_predicciones
                </code>
              </div>
            )}
          </div>
          )}

        </div>

        {/* DERECHA: Sidebar (col-span-4) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Perfil Táctico */}
          <div id="tour-jugador-radar" className="glass-panel rounded-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">
              <span className="material-symbols-outlined align-middle mr-2 icon-md">sports_soccer</span>
              Perfil Táctico
            </h3>
            <div className="flex flex-col items-center gap-4">
              {/* Contenedor del radar */}
              <div ref={radarContainerRef} className="flex justify-center rounded-lg p-4 w-full"></div>
              
              {/* Botón para generar perfil */}
              {!radarGenerated && !radarLoading && (
                <button 
                  onClick={generateRadar}
                  className="w-full px-4 py-2 bg-primary hover:bg-primary/90 text-white font-semibold rounded-lg transition flex items-center justify-center gap-2"
                >
                  <span className="material-symbols-outlined icon-md">play_arrow</span>
                  Generar Perfil Táctico
                </button>
              )}
              
              {/* Indicador de carga */}
              {radarLoading && (
                <div className="w-full flex flex-col items-center gap-2">
                  <div className="animate-spin">
                    <span className="material-symbols-outlined text-primary icon-3xl">hourglass_top</span>
                  </div>
                  <p className="text-xs text-gray-400 text-center">Generando análisis táctico...</p>
                </div>
              )}
              
              {/* Promedio */}
              {radarGenerated && (
                <div className="text-center w-full">
                  <p className="text-xs text-gray-400">
                    Percentil promedio: <span className="text-white font-bold">{radarMediaGeneral || 0}</span>
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Roles */}
          <div className="glass-panel rounded-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">
              <span className="material-symbols-outlined align-middle mr-2 icon-md">star</span>
              Roles Destacados
            </h3>
            {roles && roles.length > 0 ? (
              es_roles_por_temporada ? (
                // Roles divididos por temporada (modo carrera)
                <div className="space-y-6">
                  {roles.map((tempRoles, idx) => (
                    <div key={idx}>
                      <h4 className="text-sm font-bold text-primary mb-3 uppercase tracking-wider">
                        Temporada {tempRoles.temporada}
                      </h4>
                      <div className="flex flex-wrap gap-3">
                        {tempRoles.roles.map((role, roleIdx) => {
                          const fieldName = Object.keys(role)[0]
                          const values = role[fieldName]
                          
                          return (
                            <button 
                              key={roleIdx}
                              className="role-badge-btn bg-primary text-black border-2 border-white rounded-lg px-4 py-2 font-bold text-sm"
                              onClick={(e) => openRolePopover(e, fieldName, values[0], values[1])}
                            >
                              {formatRoleName(fieldName)}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                // Roles de una sola temporada
                <div className="flex flex-wrap gap-3">
                  {roles.map((role, idx) => {
                    const fieldName = Object.keys(role)[0]
                    const values = role[fieldName]
                    
                    return (
                      <button 
                        key={idx}
                        className="role-badge-btn bg-primary text-black border-2 border-white rounded-lg px-4 py-2 font-bold text-sm"
                        onClick={(e) => openRolePopover(e, fieldName, values[0], values[1])}
                      >
                        {formatRoleName(fieldName)}
                      </button>
                    )
                  })}
                </div>
              )
            ) : (
              <div className="text-center py-6 text-gray-400">
                <span className="material-symbols-outlined text-3xl block mb-2">grade</span>
                <p className="text-sm">Sin roles destacados</p>
              </div>
            )}
          </div>

          {/* AI Insight */}
          <div className="glass-panel rounded-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">
              <span className="material-symbols-outlined align-middle mr-2 icon-md">psychology</span>
              AI Insight
            </h3>
            {insightsLoading ? (
              <div className="flex flex-col items-center gap-2 py-6 text-gray-400">
                <div className="animate-spin">
                  <span className="material-symbols-outlined text-primary icon-3xl">hourglass_top</span>
                </div>
                <p className="text-xs">Analizando al jugador...</p>
              </div>
            ) : insights.length > 0 ? (
              <div className="space-y-3">
                {insights.map((ins, idx) => (
                  <div
                    key={idx}
                    className="flex gap-3 items-start bg-white/5 border border-white/10 rounded-xl px-4 py-3"
                  >
                    <p className="text-sm text-gray-200 leading-relaxed">{ins.texto}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 py-6 text-gray-500">
                <span className="material-symbols-outlined text-3xl">insights</span>
                <p className="text-xs">No procede por sus estadísticas. ¡Revisa otros jugadores para probar esta funcionalidad!</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* HISTÓRICO DE CARRERA */}
      {historico && historico.length > 0 && (
        <div className="glass-panel rounded-2xl p-8">
          <h2 className="text-3xl font-black text-white mb-8 uppercase tracking-wider">
            HISTÓRICO DE <span className="text-primary">CARRERA</span>
          </h2>
          
          <div className="flex justify-between items-center mb-6">
            <div className="flex gap-2 flex-wrap">
              <button 
                className={`table-type-btn ${activeHistoricoView === 'general' ? 'active' : ''}`}
                onClick={() => setActiveHistoricoView('general')}
              >
                General
              </button>
              <button 
                className={`table-type-btn ${activeHistoricoView === 'definicio' ? 'active' : ''}`}
                onClick={() => setActiveHistoricoView('definicio')}
              >
                Ataque
              </button>
              <button 
                className={`table-type-btn ${activeHistoricoView === 'organizacion' ? 'active' : ''}`}
                onClick={() => setActiveHistoricoView('organizacion')}
              >
                Organización
              </button>
              <button 
                className={`table-type-btn ${activeHistoricoView === 'regates' ? 'active' : ''}`}
                onClick={() => setActiveHistoricoView('regates')}
              >
                Regate
              </button>
              <button 
                className={`table-type-btn ${activeHistoricoView === 'defensa' ? 'active' : ''}`}
                onClick={() => setActiveHistoricoView('defensa')}
              >
                Defensa
              </button>
            </div>
            <button 
              onClick={() => setCompareModalOpen(true)}
              className="px-6 py-2 bg-primary hover:bg-primary/80 text-white font-bold rounded-lg transition-colors uppercase text-sm tracking-wide flex items-center gap-2"
            >
              <span className="material-symbols-outlined icon-md">compare_arrows</span>
              Comparar
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm historico-table">
              <thead>
                <tr>
                  <th>Temporada</th>
                  <th>Equipo</th>
                  
                  {activeHistoricoView === 'general' && (
                    <>
                      <th>Pts Tot</th>
                      <th>Pts/PJ</th>
                      <th>PJ</th>
                      <th>Minutos</th>
                      <th>Dorsal</th>
                    </>
                  )}
                  
                  {activeHistoricoView === 'definicio' && (
                    <>
                      <th>Goles</th>
                      <th>xG</th>
                      <th>Tiros</th>
                      <th>T. Puerta</th>
                    </>
                  )}
                  
                  {activeHistoricoView === 'organizacion' && (
                    <>
                      <th>Pases</th>
                      <th>Pases %</th>
                      <th>xA</th>
                      <th>Asistencias</th>
                    </>
                  )}
                  
                  {activeHistoricoView === 'regates' && (
                    <>
                      <th>Reg. C.</th>
                      <th>Reg. F.</th>
                      <th>Cond.</th>
                      <th>Cond. Prog.</th>
                      <th>Dist.</th>
                    </>
                  )}
                  
                  {activeHistoricoView === 'defensa' && (
                    <>
                      <th>Despejes</th>
                      <th>Entradas</th>
                      <th>Duelos</th>
                      <th>D. Aéreos</th>
                      <th>Bloqueos</th>
                      <th>Amarillas</th>
                      <th>Rojas</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {historico.map((row, idx) => (
                  <tr key={idx} className="border-b border-border-dark/50 hover:bg-white/5 transition-colors">
                    <td className="px-4 py-3 font-bold text-primary">{row.temporada}</td>
                    <td className="px-4 py-3 font-semibold text-gray-200">{row.equipo}</td>
                    
                    {activeHistoricoView === 'general' && (
                      <>
                        <td className="px-4 py-3 text-center font-bold text-yellow-400">{row.puntos_totales || 0}</td>
                        <td className="px-4 py-3 text-center font-bold text-yellow-400">{row.puntos_por_partido || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.pj || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.minutos || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.dorsal || '-'}</td>
                      </>
                    )}
                    
                    {activeHistoricoView === 'definicio' && (
                      <>
                        <td className="px-4 py-3 text-center font-bold text-green-400">{row.goles || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.xg || 0}</td>
                        <td className="px-4 py-3 text-center font-bold text-orange-400">{row.tiros || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.tiros_puerta || 0}</td>
                      </>
                    )}
                    
                    {activeHistoricoView === 'organizacion' && (
                      <>
                        <td className="px-4 py-3 text-center text-gray-300">{row.pases || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.pases_accuracy || 0}%</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.xag || 0}</td>
                        <td className="px-4 py-3 text-center text-green-400 font-bold">{row.asistencias || 0}</td>
                      </>
                    )}
                    
                    {activeHistoricoView === 'regates' && (
                      <>
                        <td className="px-4 py-3 text-center font-bold text-purple-400">{row.regates_completados || 0}</td>
                        <td className="px-4 py-3 text-center text-red-400">{row.regates_fallidos || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.conducciones || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.conducciones_progresivas || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.distancia_conduccion || 0}</td>
                      </>
                    )}
                    
                    {activeHistoricoView === 'defensa' && (
                      <>
                        <td className="px-4 py-3 text-center text-gray-300">{row.despejes || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.entradas || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.duelos_totales || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.duelos_aereos_totales || 0}</td>
                        <td className="px-4 py-3 text-center text-gray-300">{row.bloqueos || 0}</td>
                        <td className="px-4 py-3 text-center text-yellow-500 font-bold">{row.amarillas || 0}</td>
                        <td className="px-4 py-3 text-center text-red-600 font-bold">{row.rojas || 0}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* COMPARISON MODAL */}
      {compareModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-surface-dark rounded-2xl p-8 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto glass-panel">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-2xl font-black text-white uppercase tracking-wider">
                Comparar <span className="text-primary">Temporadas</span>
              </h3>
              <button 
                onClick={() => {
                  setCompareModalOpen(false)
                  setExpandDuelosTotales(false)
                  setExpandDuelosAereos(false)
                  setComparisonEntries([])
                }}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <span className="material-symbols-outlined icon-2xl">close</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div>
                <label className="block text-sm font-bold text-gray-300 mb-2">Primera Temporada</label>
                <select 
                  value={season1}
                  onChange={(e) => {
                    setSeason1(e.target.value)
                    setComparisonEntries([])
                  }}
                  className="w-full px-3 py-2 bg-black border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none"
                >
                  <option value="">Selecciona una temporada</option>
                  {historico.map((row, idx) => (
                    <option key={idx} value={row.temporada}>{row.temporada}</option>
                  ))}
                  <option value="total">ULTIMAS 3 TEMPORADAS</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-300 mb-2">Segunda Temporada</label>
                <select 
                  value={season2}
                  onChange={(e) => {
                    setSeason2(e.target.value)
                    setComparisonEntries([])
                  }}
                  className="w-full px-3 py-2 bg-black border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none"
                >
                  <option value="">Selecciona una temporada</option>
                  {historico.map((row, idx) => (
                    <option key={idx} value={row.temporada}>{row.temporada}</option>
                  ))}
                  <option value="total">ULTIMAS 3 TEMPORADAS</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-300 mb-2">Dominio</label>
                <select 
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="w-full px-3 py-2 bg-black border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none"
                >
                  {COMPARISON_DOMAINS.map((dom) => (
                    <option key={dom.key} value={dom.key}>{dom.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <button 
              onClick={executeComparison}
              className="w-full px-4 py-3 bg-primary hover:bg-primary/80 text-white font-bold rounded-lg transition-colors uppercase mb-6"
            >
              Ejecutar Comparación
            </button>
            <ComparisonMetricsCards
              entries={comparisonEntries}
              domain={domain}
              emptyMessage={'Selecciona dos temporadas y pulsa "Ejecutar comparacion"'}
            />
          </div>
        </div>
      )}
      
      {/* ROLE POPOVER */}
      {rolePopover && (
        <div 
          ref={rolePopoverRef}
          className="role-popover w-72 text-white rounded-xl shadow-2xl border border-primary/50 p-4"
          style={{
            left: `${Math.min(rolePopover.x, window.innerWidth - 300)}px`,
            top: `${rolePopover.y}px`,
            zIndex: 1000
          }}
        >
          <button 
            onClick={() => setRolePopover(null)}
            className="absolute -top-3 -right-3 text-gray-400 hover:text-white transition-colors rounded-full p-1.5 bg-slate-900/95 border border-primary/50"
          >
            <span className="material-symbols-outlined icon-md">close</span>
          </button>
          <div className="mb-3">
            <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Rol Destacado</p>
            <h3 className="text-lg font-black text-primary mb-2">{rolePopover.name}</h3>
            <p className="text-gray-300 text-sm leading-relaxed">{rolePopover.description}</p>
          </div>
          <div className="rounded-lg p-3 border border-primary/20 bg-primary/5">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="text-gray-400 font-semibold">Posición</span>
                <span className="text-primary font-black text-lg">#{rolePopover.position}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-400 font-semibold">Valor</span>
                <span className="text-white font-black text-2xl">{rolePopover.value}</span>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* PERCENTILE POPOVER */}
      {percentilePopover && (
        <div 
          ref={percentilePopoverRef}
          className="percentile-popover w-72 text-white rounded-lg shadow-2xl bg-amber-900/90 border-2 border-amber-600 p-3"
          style={{
            left: `${Math.min(percentilePopover.x, window.innerWidth - 300)}px`,
            top: `${percentilePopover.y}px`,
            zIndex: 1000
          }}
        >
          <button 
            onClick={() => setPercentilePopover(null)}
            className="absolute -top-2 -right-2 text-gray-300 hover:text-white transition-colors rounded-full p-1 bg-amber-900/90 border border-amber-600"
          >
            <span className="material-symbols-outlined icon-sm">close</span>
          </button>
          <div>
            <p className="text-xs font-bold text-yellow-300 uppercase tracking-wide mb-2">⭐ Percentil {percentilePopover.percentile} — {percentilePopover.stat}</p>
            <p className="text-xs text-gray-100 leading-tight">
              Estar en el <strong>{percentilePopover.percentile}º percentil</strong> en <strong>{percentilePopover.stat}</strong> significa que supera al <strong>{percentilePopover.percentile}%</strong> de jugadores de su misma posición en la temporada <strong>{temporada}</strong>.
            </p>
          </div>
        </div>
      )}
      <HelpButton title="Guía del jugador" sections={[
        { title: 'General', fields: [
          { label: 'PTS', description: 'Puntos fantasy totales acumulados en la temporada o carrera.' },
          { label: 'PJ', description: 'Partidos jugados.' },
          { label: 'MIN', description: 'Minutos totales jugados.' },
          { label: 'Percentil', description: 'Posición del jugador entre el 0% y 100% respecto al resto de jugadores de su misma posición en esa stat.' },
        ]},
        { title: 'Ataque', fields: [
          { label: 'xG', description: 'Expected Goals: suma de probabilidades de que cada ocasión hubiera acabado en gol.' },
          { label: 'xAG', description: 'Expected Assisted Goals: probabilidad total de generar asistencias de gol.' },
          { label: 'Tiros', description: 'Disparos totales realizados.' },
          { label: 'T/Puerta', description: 'Tiros que terminaron entre los tres palos.' },
        ]},
        { title: 'Organización', fields: [
          { label: 'Pases', description: 'Total de pases intentados.' },
          { label: 'Pases %', description: 'Porcentaje de pases completados sobre el total intentado.' },
        ]},
        { title: 'Defensa', fields: [
          { label: 'Entradas', description: 'Número de entradas (tackles) realizadas.' },
          { label: 'Despejes', description: 'Balones despejados.' },
          { label: 'Duelos', description: 'Total de duelos disputados.' },
          { label: 'Aéreos', description: 'Duelos aéreos disputados.' },
        ]},
        { title: 'Portero', fields: [
          { label: '% Paradas', description: 'Porcentaje de disparos a puerta que el portero detuvo.' },
          { label: 'GEC', description: 'Goles en contra encajados en la temporada.' },
        ]},
        { title: 'Roles XAI', fields: [
          { label: 'Rol', description: 'Papel detectado automáticamente según el perfil de juego: rematador, organizador, defensor, etc.' },
          { label: 'Puntuación', description: 'Nivel de ajuste del jugador a ese rol (cuanto más bajo el número, más prominente el rol).' },
        ]},
      ]} />
    </div>
  )
}

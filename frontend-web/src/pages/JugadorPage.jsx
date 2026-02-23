import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import api from '../services/apiClient'

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
  
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeHistoricoView, setActiveHistoricoView] = useState('general')
  const [compareModalOpen, setCompareModalOpen] = useState(false)
  const [radarGenerated, setRadarGenerated] = useState(false)
  const [radarLoading, setRadarLoading] = useState(false)
  const radarContainerRef = useRef(null)
  const chartInstanceRef = useRef(null)
  
  const [comparisonData, setComparisonData] = useState(null)
  const [season1, setSeason1] = useState('')
  const [season2, setSeason2] = useState('')
  const [domain, setDomain] = useState('todo')
  
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
      console.error('Error loading jugador:', e)
    } finally {
      setLoading(false)
    }
  }, [id, temporada])

  useEffect(() => { fetchData() }, [fetchData])

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
        renderRadar(response.data.data.radar_values, response.data.data.media_general)
      }
    } catch (error) {
      console.error('Error loading radar:', error)
      setRadarLoading(false)
    }
  }

  const renderRadar = (radarValues, mediaGeneral) => {
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
          labels: ['Ataque', 'Defensa', 'Regates', 'Pases', 'Comportamiento', 'Minutos', 'Puntos Fantasy'],
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

  const executeComparison = () => {
    if (!season1 || !season2 || !data) return
    
    const historicoData = data.historico || []
    
    const getSeasonStats = (season) => {
      if (season === 'total') {
        return historicoData.reduce((acc, row) => {
          Object.keys(row).forEach(key => {
            if (typeof row[key] === 'number') {
              acc[key] = (acc[key] || 0) + row[key]
            }
          })
          return acc
        }, {})
      }
      return historicoData.find(r => r.temporada === season) || {}
    }
    
    const stats1 = getSeasonStats(season1)
    const stats2 = getSeasonStats(season2)
    
    setComparisonData({
      season1,
      season2,
      stats1,
      stats2
    })
  }

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
    descripciones_roles = {}
  } = data || {}

  return (
    <div className="p-6 space-y-6 bg-background-dark min-h-full">
      <style>{`
        .glass-panel {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgb(75, 85, 99);
          border-radius: 1rem;
          backdrop-filter: blur(10px);
        }
        
        .stat-mini {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgb(75, 85, 99);
          border-radius: 0.75rem;
          padding: 1rem;
          text-align: center;
        }
        
        .stat-value {
          font-size: 1.875rem;
          font-weight: bold;
          color: rgb(245, 245, 245);
        }
        
        .stat-label {
          color: rgb(156, 163, 175);
          font-size: 0.75rem;
          margin-top: 0.5rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        
        .player-badge {
          width: 120px;
          height: 120px;
          border-radius: 1rem;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 3px solid;
          font-weight: 900;
          font-size: 2.5rem;
          background: linear-gradient(135deg, rgb(59, 130, 246), rgb(139, 92, 246));
          border-color: #39ff14;
          box-shadow: 0 0 15px rgba(57, 255, 20, 0.3);
        }
        
        .header-gradient {
          background: linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%);
        }
        
        .posicion-badge {
          display: inline-block;
          background: rgba(59, 130, 246, 0.2);
          border: 1px solid rgb(59, 130, 246);
          color: rgb(147, 197, 253);
          padding: 0.5rem 1rem;
          border-radius: 0.5rem;
          font-weight: bold;
          font-size: 0.875rem;
        }
        
        .temporada-btn {
          padding: 0.5rem 1rem;
          border-radius: 0.5rem;
          border: 1px solid rgb(75, 85, 99);
          background: rgba(255, 255, 255, 0.05);
          color: rgb(200, 200, 200);
          cursor: pointer;
          transition: all 0.2s;
          font-size: 0.875rem;
          text-decoration: none;
          display: inline-block;
          font-weight: 500;
        }
        
        .temporada-btn:hover {
          background: rgba(59, 130, 246, 0.2);
          border-color: rgb(59, 130, 246);
          color: white;
        }
        
        .temporada-btn.active {
          background: rgb(59, 130, 246);
          border-color: rgb(59, 130, 246);
          color: white;
          box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
        }
        
        .table-type-btn {
          padding: 0.5rem 1rem;
          border-radius: 0.5rem;
          border: 1px solid rgb(75, 85, 99);
          background: rgba(255, 255, 255, 0.05);
          color: rgb(200, 200, 200);
          cursor: pointer;
          transition: all 0.2s;
          font-weight: 500;
          font-size: 0.875rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        
        .table-type-btn:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: rgb(59, 130, 246);
          color: white;
        }
        
        .table-type-btn.active {
          background: rgb(34, 197, 94);
          border-color: rgb(34, 197, 94);
          color: white;
        }
        
        .historico-table {
          width: 100%;
          border-collapse: collapse;
        }
        
        .historico-table th {
          background: transparent;
          border-bottom: 2px solid rgb(75, 85, 99);
          border-top: none;
          border-left: none;
          border-right: none;
          padding: 0.75rem 1rem;
          text-align: center;
          color: rgb(200, 200, 200);
          font-weight: bold;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        
        .historico-table th:first-child,
        .historico-table th:nth-child(2) {
          text-align: left;
        }
        
        .historico-table td {
          border: none;
          border-bottom: 1px solid rgba(75, 85, 99, 0.3);
          padding: 0.75rem 1rem;
          color: rgb(220, 220, 220);
        }
        
        .historico-table tbody tr:hover {
          background: rgba(59, 130, 246, 0.05);
        }
        
        .historico-table tbody tr:last-child td {
          border-bottom: 2px solid rgb(75, 85, 99);
        }
        
        .histogram-chart {
          position: relative;
          height: 280px;
          margin: 2rem 0;
          padding: 3rem 1rem 2rem 1rem;
          border-bottom: 1px solid rgb(75, 85, 99);
          display: flex;
          align-items: flex-end;
          gap: 0.75rem;
          justify-content: center;
        }
        
        .histogram-bar {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: flex-end;
          flex: 0 1 auto;
          cursor: pointer;
          transition: all 0.2s;
          min-width: 48px;
          max-width: 64px;
        }
        
        .histogram-bar-inner {
          width: 100%;
          border-radius: 8px 8px 0 0;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
        }
        
        .histogram-bar-positive .histogram-bar-inner {
          background: linear-gradient(180deg, rgb(52, 211, 153), rgb(16, 185, 129));
          box-shadow: 0 0 16px rgba(52, 211, 153, 0.5);
        }
        
        .histogram-bar-negative .histogram-bar-inner {
          background: linear-gradient(180deg, rgb(248, 113, 113), rgb(239, 68, 68));
          box-shadow: 0 0 16px rgba(248, 113, 113, 0.5);
        }
        
        .histogram-bar-zero .histogram-bar-inner {
          background: linear-gradient(180deg, rgb(234, 179, 8), rgb(202, 138, 4));
          box-shadow: 0 0 16px rgba(234, 179, 8, 0.5);
        }
        
        .histogram-bar-high .histogram-bar-inner {
          background: linear-gradient(180deg, rgb(59, 130, 246), rgb(37, 99, 235));
          box-shadow: 0 0 16px rgba(59, 130, 246, 0.5);
        }
        
        .histogram-bar:hover .histogram-bar-inner {
          filter: brightness(1.15);
        }
        
        .histogram-bar-label {
          position: absolute;
          bottom: -26px;
          font-size: 0.75rem;
          color: rgb(156, 163, 175);
          font-weight: 600;
          white-space: nowrap;
        }
        
        .histogram-bar-value {
          position: absolute;
          top: -24px;
          font-size: 0.875rem;
          color: white;
          font-weight: 700;
          background: rgba(0, 0, 0, 0.6);
          padding: 2px 6px;
          border-radius: 4px;
          white-space: nowrap;
        }
        
        .placeholder-box {
          background: rgba(255, 255, 255, 0.02);
          border: 2px dashed rgb(107, 114, 128);
          border-radius: 0.75rem;
          padding: 2rem;
          text-align: center;
          color: rgb(156, 163, 175);
        }
        
        /* Stats doradas (top 10%) */
        .stat-golden {
          background: linear-gradient(135deg, rgba(251, 191, 36, 0.4) 0%, rgba(251, 146, 60, 0.4) 100%);
          border: 2px solid rgba(251, 146, 60, 0.7);
          border-left: 4px solid rgb(251, 191, 36);
          cursor: pointer;
          box-shadow: 0 0 16px rgba(251, 146, 60, 0.3);
          transition: all 0.2s;
        }
        
        .stat-golden:hover {
          box-shadow: 0 0 24px rgba(251, 146, 60, 0.5);
          transform: translateY(-2px);
        }
        
        /* Popovers */
        .role-popover, .percentile-popover {
          position: fixed;
          z-index: 9999;
          background: rgba(15, 23, 42, 0.98);
          border-radius: 0.75rem;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
          animation: fadeIn 0.2s ease;
        }
        
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        .role-badge-btn {
          transition: all 0.2s;
        }
        
        .role-badge-btn:hover {
          box-shadow: 0 0 15px rgba(57, 255, 20, 0.4);
          transform: scale(1.05);
        }
      `}</style>
      
      {/* HEADER CON INFO DEL JUGADOR */}
      <div className="glass-panel header-gradient rounded-2xl p-8 mb-6">
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
                    <span className="material-symbols-outlined align-middle mr-2" style={{ fontSize: '1rem' }}>sports_soccer</span>
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
                    src={`http://localhost:8000${equipo_temporada.equipo.escudo}`}
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
          <div className="glass-panel rounded-2xl p-6">
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
                    <span className="material-symbols-outlined text-red-400" style={{ fontSize: '1.4rem' }}>local_fire_department</span>
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
                    <span className="material-symbols-outlined text-blue-400" style={{ fontSize: '1.4rem' }}>hub</span>
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
                    <span className="material-symbols-outlined text-purple-400" style={{ fontSize: '1.4rem' }}>sprint</span>
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
                    <span className="material-symbols-outlined text-green-400" style={{ fontSize: '1.4rem' }}>shield</span>
                    Defensa
                  </h3>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Entradas</span>
                      <span className="text-lg font-bold text-white">{stats.defensa?.entradas || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Despeje</span>
                      <span className="text-lg font-bold text-white">{stats.defensa?.despejes || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Duelos Totales</span>
                      <span className="text-lg font-bold text-white">{stats.defensa?.duelos_totales || 0}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/5 border border-white/10 rounded-lg px-4 py-2">
                      <span className="text-sm text-gray-300">Duelos Aéreos</span>
                      <span className="text-lg font-bold text-white">{stats.defensa?.duelos_aereos_totales || 0}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* COMPORTAMIENTO */}
              <div>
                <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
                  <span className="material-symbols-outlined text-yellow-400" style={{ fontSize: '1.4rem' }}>flag</span>
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
                    <span className="material-symbols-outlined text-orange-400" style={{ fontSize: '1.4rem' }}>sports_handball</span>
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

          {/* Gráfico de últimos 12 partidos - HISTOGRAMA */}
          <div className="glass-panel rounded-2xl p-6">
            <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-wider">
              <span className="material-symbols-outlined align-middle mr-2" style={{ fontSize: '1.3rem' }}>trending_up</span>
              Últimos 12 Partidos (Puntos Fantasy)
            </h3>
            
            {ultimos_8 && ultimos_8.length > 0 ? (
              <div className="histogram-chart">
                {ultimos_8.map((stat, idx) => {
                  const maxHeight = 300
                  const maxValue = 20
                  const minValue = -12
                  const heightPercent = ((stat.puntos_fantasy - minValue) / (maxValue - minValue)) * 100
                  const heightPx = (heightPercent / 100) * maxHeight
                  
                  return (
                    <div 
                      key={idx} 
                      className={`histogram-bar ${
                        stat.puntos_fantasy > 10 ? 'histogram-bar-high' :
                        stat.puntos_fantasy === 0 ? 'histogram-bar-zero' :
                        stat.puntos_fantasy > 0 ? 'histogram-bar-positive' :
                        'histogram-bar-negative'
                      }`}
                      title={`Jornada ${stat.partido?.jornada?.numero_jornada}: ${stat.puntos_fantasy} puntos`}
                    >
                      <div className="histogram-bar-value">{stat.puntos_fantasy}</div>
                      <div className="histogram-bar-inner" style={{ height: `${heightPx}px` }}></div>
                      <div className="histogram-bar-label">J{stat.partido?.jornada?.numero_jornada}</div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <span className="material-symbols-outlined text-4xl block mb-2">info</span>
                Sin datos de partidos
              </div>
            )}
          </div>
        </div>

        {/* DERECHA: Sidebar (col-span-4) */}
        <div className="lg:col-span-4 space-y-6">
          {/* Perfil Táctico */}
          <div className="glass-panel rounded-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">
              <span className="material-symbols-outlined align-middle mr-2" style={{ fontSize: '1.2rem' }}>sports_soccer</span>
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
                  <span className="material-symbols-outlined" style={{ fontSize: '1.2rem' }}>play_arrow</span>
                  Generar Perfil Táctico
                </button>
              )}
              
              {/* Indicador de carga */}
              {radarLoading && (
                <div className="w-full flex flex-col items-center gap-2">
                  <div className="animate-spin">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: '2rem' }}>hourglass_top</span>
                  </div>
                  <p className="text-xs text-gray-400 text-center">Generando análisis táctico...</p>
                </div>
              )}
              
              {/* Promedio */}
              {radarGenerated && (
                <div className="text-center w-full">
                  <p className="text-xs text-gray-400">
                    Percentil promedio: <span className="text-white font-bold">{media_general || 0}</span>
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Roles */}
          <div className="glass-panel rounded-2xl p-6">
            <h3 className="text-lg font-bold text-white mb-4 uppercase tracking-wider">
              <span className="material-symbols-outlined align-middle mr-2" style={{ fontSize: '1.2rem' }}>star</span>
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
              <span className="material-symbols-outlined align-middle mr-2" style={{ fontSize: '1.2rem' }}>psychology</span>
              AI Insight
            </h3>
            <div className="placeholder-box">
              <span className="material-symbols-outlined text-4xl block mb-2">insights</span>
              <p className="text-sm">Análisis en desarrollo</p>
            </div>
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
              <span className="material-symbols-outlined" style={{ fontSize: '1.2rem' }}>compare_arrows</span>
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
                onClick={() => setCompareModalOpen(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <span className="material-symbols-outlined" style={{ fontSize: '1.5rem' }}>close</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div>
                <label className="block text-sm font-bold text-gray-300 mb-2">Primera Temporada</label>
                <select 
                  value={season1}
                  onChange={(e) => setSeason1(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-darker border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none"
                >
                  <option value="">Selecciona una temporada</option>
                  {historico.map((row, idx) => (
                    <option key={idx} value={row.temporada}>{row.temporada}</option>
                  ))}
                  <option value="total">TOTAL (Todas las temporadas)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-300 mb-2">Segunda Temporada</label>
                <select 
                  value={season2}
                  onChange={(e) => setSeason2(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-darker border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none"
                >
                  <option value="">Selecciona una temporada</option>
                  {historico.map((row, idx) => (
                    <option key={idx} value={row.temporada}>{row.temporada}</option>
                  ))}
                  <option value="total">TOTAL (Todas las temporadas)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-300 mb-2">Dominio</label>
                <select 
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-darker border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none"
                >
                  <option value="todo">Todo</option>
                  <option value="general">General</option>
                  <option value="definicio">Definición</option>
                  <option value="organizacion">Organización</option>
                  <option value="regates">Regates</option>
                  <option value="defensa">Defensa</option>
                </select>
              </div>
            </div>

            <button 
              onClick={executeComparison}
              className="w-full px-4 py-3 bg-primary hover:bg-primary/80 text-white font-bold rounded-lg transition-colors uppercase mb-6"
            >
              Ejecutar Comparación
            </button>

            {comparisonData ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b-2 border-primary/50">
                      <th className="text-left px-4 py-2 text-gray-300 font-bold">Estadística</th>
                      <th className="text-center px-4 py-2 text-primary font-bold">{comparisonData.season1}</th>
                      <th className="text-center px-4 py-2 text-primary font-bold">{comparisonData.season2}</th>
                      <th className="text-center px-4 py-2 text-yellow-400 font-bold">Diferencia</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(comparisonData.stats1).filter(k => typeof comparisonData.stats1[k] === 'number').map((key, idx) => {
                      const val1 = comparisonData.stats1[key] || 0
                      const val2 = comparisonData.stats2[key] || 0
                      const diff = val2 - val1
                      
                      return (
                        <tr key={idx} className="border-b border-border-dark/30 hover:bg-white/5 transition-colors">
                          <td className="px-4 py-2 text-gray-300">{key.replace(/_/g, ' ')}</td>
                          <td className="px-4 py-2 text-center text-white font-bold">{val1}</td>
                          <td className="px-4 py-2 text-center text-white font-bold">{val2}</td>
                          <td className={`px-4 py-2 text-center font-bold ${diff > 0 ? 'text-green-400' : diff < 0 ? 'text-red-400' : 'text-gray-400'}`}>
                            {diff > 0 ? '+' : ''}{diff}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400">
                <p>Selecciona dos temporadas y un dominio para ver la comparación</p>
              </div>
            )}
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
            <span className="material-symbols-outlined" style={{ fontSize: '1.2rem' }}>close</span>
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
            <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>close</span>
          </button>
          <div>
            <p className="text-xs font-bold text-yellow-300 uppercase tracking-wide mb-2">⭐ Percentil {percentilePopover.percentile} — {percentilePopover.stat}</p>
            <p className="text-xs text-gray-100 leading-tight">
              Estar en el <strong>{percentilePopover.percentile}º percentil</strong> en <strong>{percentilePopover.stat}</strong> significa que supera al <strong>{percentilePopover.percentile}%</strong> de jugadores de su misma posición en la temporada <strong>{temporada}</strong>.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

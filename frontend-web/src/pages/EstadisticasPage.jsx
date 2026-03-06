import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'
import HelpButton from '../components/ui/HelpButton'

const BACKEND = 'http://localhost:8000'

export default function EstadisticasPage() {
  const navigate = useNavigate()
  const [estadisticas, setEstadisticas] = useState([])
  const [loading, setLoading] = useState(true)
  const [topLoading, setTopLoading] = useState(false)
  const [tipo, setTipo] = useState(null)
  const [search, setSearch] = useState('')
  const [temporada, setTemporada] = useState('25_26')
  const [jornada, setJornada] = useState(null)
  const [jornadaActual, setJornadaActual] = useState(1)
  const [currentPage, setCurrentPage] = useState(0)
  const [itemsPerPage, setItemsPerPage] = useState(20) // Cargar 20 del backend
  const [displayCount, setDisplayCount] = useState(10) // Mostrar solo 10 inicialmente
  const [totalItems, setTotalItems] = useState(0)
  const [sortBy, setSortBy] = useState(null) // null, 'alfabetico', 'puntos_fantasy', 'goles', etc.
  const [sortOrder, setSortOrder] = useState('asc') // 'asc' o 'desc'
  const [compareModalOpen, setCompareModalOpen] = useState(false)
  const [jugadoresComparacion, setJugadoresComparacion] = useState([null, null, null, null])
  const [comparisonTemporales, setComparisonTemporales] = useState(['', '', '', ''])
  const [comparisonDatas, setComparisonDatas] = useState([null, null, null, null])
  const [comparisonAvailableSeasons, setComparisonAvailableSeasons] = useState([[], [], [], []])
  const [comparisonLoading, setComparisonLoading] = useState(false)
  const [comparisonDomain, setComparisonDomain] = useState('general')
  const [searchJugadores, setSearchJugadores] = useState(['', '', '', ''])
  const [topStats, setTopStats] = useState({})
  const [topViewMode, setTopViewMode] = useState('total') // 'total', 'per90', 'percentil'
  const [posicionPercentiles, setPosicionPercentiles] = useState('')
  const [filtroModalOpen, setFiltroModalOpen] = useState(false)
  const [mostrarDescripcionPercentiles, setMostrarDescripcionPercentiles] = useState(false)
  const [expandedCategories, setExpandedCategories] = useState({
    goles: true,
    asistencias: true,
    puntos_fantasy: true,
    xag: true,
    tiros: true,
    regates_completados: true,
    goles_vs_xg_encima: true,
    goles_vs_xg_debajo: true,
    asistencias_vs_xag_encima: true,
    asistencias_vs_xag_debajo: true,
    corners: true,
    penaltis_marcados: true,
    faltas_recibidas: true,
  })
  const [posicionPercentilesFiltro, setPosicionPercentilesFiltro] = useState('')
  const [filtros, setFiltros] = useState({
    minJornada: '',
    maxJornada: '',
    minGoles: '',
    maxGoles: '',
    minAsistencias: '',
    maxAsistencias: '',
    minPuntos: '',
    maxPuntos: '',
    minPartidos: '',
    maxPartidos: '',
    minTarjetas: '',
    maxTarjetas: '',
    posicion: '',
    golesVsXg: '',  // '' | 'encima' | 'debajo'
    asistenciasVsXag: ''  // '' | 'encima' | 'debajo'
  })

  // Ref para debounce de búsqueda
  const searchTimerRef = useRef(null)

  // Leer jornada actual del sidebar (solo actualiza jornadaActual, no la selección)
  useEffect(() => {
    const saved = localStorage.getItem('jornada_global')
    if (saved) {
      const num = parseInt(saved)
      setJornadaActual(num)
      // NO se setea jornada aquí para que el select muestre "Todas" por defecto
    }
  }, [])

  // Escuchar cambios de jornada desde el sidebar
  useEffect(() => {
    const handleJornadaChange = (e) => {
      const newJornada = e.detail.jornada
      setJornadaActual(newJornada)
      setJornada(String(newJornada))
    }
    
    window.addEventListener('jornadaChanged', handleJornadaChange)
    return () => window.removeEventListener('jornadaChanged', handleJornadaChange)
  }, [])

  const TIPO_OPCIONES = [
    { key: 'goles', label: 'Goles' },
    { key: 'asistencias', label: 'Asistencias' },
    { key: 'amarillas', label: 'Amarillas' },
    { key: 'rojas', label: 'Rojas' },
    { key: 'puntos_fantasy', label: 'Puntos' },
  ]

  const TOP_CATEGORIES = [
    { key: 'goles', label: 'Goles' },
    { key: 'asistencias', label: 'Asistencias' },
    { key: 'puntos_fantasy', label: 'Puntos Fantasy' },
    { key: 'xag', label: 'xAG' },
    { key: 'tiros', label: 'Disparos' },
    { key: 'regates_completados', label: 'Regates' },
    { key: 'goles_vs_xg_encima', label: 'Marcando por encima de la probabilidad', baseKey: 'goles_vs_xg', reverseSort: false },
    { key: 'goles_vs_xg_debajo', label: 'Marcando por debajo de la probabilidad', baseKey: 'goles_vs_xg', reverseSort: true },
    { key: 'asistencias_vs_xag_encima', label: 'Asistiendo por encima de la probabilidad', baseKey: 'asistencias_vs_xag', reverseSort: false },
    { key: 'asistencias_vs_xag_debajo', label: 'Asistiendo por debajo de la probabilidad', baseKey: 'asistencias_vs_xag', reverseSort: true },
    { key: 'corners', label: 'Corners' },
    { key: 'penaltis_marcados', label: 'Penaltis Marcados' },
    { key: 'faltas_recibidas', label: 'Faltas Recibidas' },
  ]

  const fetchEstadisticas = async () => {
    setLoading(true)
    try {
      // Si no hay jornada seleccionada, no cargues nada
      if (jornada === null) {
        setEstadisticas([])
        return
      }

      // Cargar 20 items por página desde el inicio
      const limit = 20
      const offset = currentPage * 20

      const params = new URLSearchParams({
        temporada,
        limit,
        offset,
      })
      if (search) params.append('search', search)
      // Solo add tipo si está seleccionado
      if (tipo) params.append('tipo', tipo)
      
      // Manejo de jornada/vuelta
      if (jornada === 'acumulado') {
        // Si temporada no es 25/26, sumar las 38 jornadas completas
        const jornadaHasta = temporada === '25_26' ? jornadaActual : 38
        params.append('jornada_hasta', jornadaHasta)
      } else if (jornada === 'primera_vuelta') {
        // Primera vuelta: J1-J18
        params.append('jornada_hasta', 18)
      } else if (jornada === 'segunda_vuelta') {
        // Segunda vuelta: J19-J38
        params.append('jornada_desde', 19)
        params.append('jornada_hasta', 38)
      } else if (jornada) {
        params.append('jornada', jornada)
      }

      const { data } = await api.get(`/api/estadisticas/?${params}`)
      const jugadores = data.estadisticas || []
      setTotalItems(data.total_count || jugadores.length)
      // Apply client-side sorting
      const sorted = applyClientSorting(jugadores)
      setEstadisticas(sorted)
    } catch (e) {
      console.error('Error fetching estadisticas:', e)
      setEstadisticas([])
      setTotalItems(0)
    } finally {
      setLoading(false)
    }
  }

  const applyClientSorting = (items) => {
    if (!sortBy) {
      // Si no hay sorting, ordenar alfabéticamente por defecto
      return [...items].sort((a, b) => {
        const nameA = `${a.nombre} ${a.apellido}`.toLowerCase()
        const nameB = `${b.nombre} ${b.apellido}`.toLowerCase()
        return nameA.localeCompare(nameB)
      })
    }

    const sorted = [...items].sort((a, b) => {
      let valA = a[sortBy] || 0
      let valB = b[sortBy] || 0

      if (typeof valA === 'string') {
        valA = valA.toLowerCase()
        valB = valB.toLowerCase()
        return sortOrder === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA)
      }

      return sortOrder === 'asc' ? valA - valB : valB - valA
    })

    return sorted
  }

  const fetchTopStats = async () => {
    if (jornada === null) return // No fetch if no specific jornada selected
    
    setTopLoading(true)
    try {
      const params = new URLSearchParams({ temporada, limit: 100 })
      if (jornada === 'acumulado') {
        params.append('jornada_hasta', jornadaActual)
      } else if (jornada) {
        params.append('jornada', jornada)
      }

      const tops = {}
      const keysToFetch = new Set()
      
      // Recopilar todas las claves únicas a solicitar (usar baseKey si existe)
      for (const cat of TOP_CATEGORIES) {
        const keyToFetch = cat.baseKey || cat.key
        keysToFetch.add(keyToFetch)
      }

      // Hacer todas las solicitudes en paralelo
      const promises = Array.from(keysToFetch).map(keyToFetch =>
        api.get(`/api/estadisticas/?${params}&tipo=${keyToFetch}`)
          .then(({ data }) => ({ keyToFetch, data: data.estadisticas || [] }))
          .catch(() => ({ keyToFetch, data: [] }))
      )
      
      const results = await Promise.all(promises)
      results.forEach(({ keyToFetch, data }) => {
        tops[keyToFetch] = data
      })
      
      setTopStats(tops)
    } catch (e) {
      setTopStats({})
    } finally {
      setTopLoading(false)
    }
  }

  useEffect(() => {
    setCurrentPage(0)
    setDisplayCount(10) // Reset a mostrar solo 10 al cambiar filtros
    setItemsPerPage(20) // 20 items por página
  }, [tipo, temporada, jornada, jornadaActual])

  // Separe la dependencia de currentPage para que se llame cuando cambia de página
  useEffect(() => {
    fetchEstadisticas()
  }, [tipo, temporada, jornada, jornadaActual, currentPage])

  useEffect(() => {
    fetchTopStats()
  }, [temporada, jornada, jornadaActual])

  // Re-sort cuando cambia sortBy o sortOrder
  useEffect(() => {
    if (estadisticas.length > 0) {
      const sorted = applyClientSorting(estadisticas)
      setEstadisticas(sorted)
    }
  }, [sortBy, sortOrder])

  const handleSearch = (e) => {
    const q = e.target.value
    setSearch(q)
    clearTimeout(searchTimerRef.current)
    
    if (q.trim().length === 0) {
      // Si está vacío, buscar inmediatamente
      setCurrentPage(0)
      setDisplayCount(10)
      fetchEstadisticas()
      return
    }
    
    // Debounce de 500ms para búsqueda
    searchTimerRef.current = setTimeout(() => {
      setCurrentPage(0)
      setDisplayCount(10)
      fetchEstadisticas()
    }, 500)
  }

  // Función para normalizar posiciones (PT, DF, MC, DT)
  const normalizePosicion = (posicion) => {
    if (!posicion) return ''
    const pos = posicion.trim().toUpperCase()
    if (pos === 'PORTERO' || pos === 'PT') return 'PT'
    if (pos === 'DEFENSA' || pos === 'DF') return 'DF'
    if (pos === 'CENTROCAMPISTA' || pos === 'MC') return 'MC'
    if (pos === 'DELANTERO' || pos === 'DT') return 'DT'
    return pos
  }

  const fetchComparacionData = async (jugadorId, temporadaStr) => {
    try {
      const response = await fetch(`http://localhost:8000/api/jugador/${jugadorId}/?temporada=${temporadaStr}`)
      if (!response.ok) return null
      const data = await response.json()
      return data
    } catch (e) {
      console.error('Error fetching comparison data:', e)
      return null
    }
  }

  // Al seleccionar un jugador para comparar, carga sus temporadas disponibles
  const fetchPlayerSeasons = async (jugadorId, slotIdx) => {
    try {
      const response = await fetch(`http://localhost:8000/api/jugador/${jugadorId}/`)
      if (!response.ok) return
      const data = await response.json()
      const seasons = data.temporadas_disponibles || []
      setComparisonAvailableSeasons(prev => {
        const n = [...prev]
        n[slotIdx] = seasons
        return n
      })
    } catch (e) {
      console.error('Error fetching player seasons:', e)
    }
  }

  const COMPARISON_DOMAINS = [
    { key: 'general',  label: 'General' },
    { key: 'ataque',   label: 'Ataque' },
    { key: 'pase',     label: 'Pase' },
    { key: 'regates',  label: 'Regates' },
    { key: 'defensa',  label: 'Defensa' },
  ]

  const getStatsByDomain = (d, domain) => {
    if (!d?.stats) return []
    const s = d.stats
    switch (domain) {
      case 'general':  return [
        { label: 'Partidos',  value: s.partidos || 0 },
        { label: 'Minutos',   value: s.minutos || 0 },
        { label: 'Goles',     value: s.goles || 0,     color: 'text-green-400' },
        { label: 'Asistencias', value: s.asistencias || 0, color: 'text-blue-400' },
        { label: 'Fantasy',   value: s.puntos_fantasy || 0, color: 'text-yellow-400' },
      ]
      case 'ataque': return [
        { label: 'Goles',         value: s.ataque?.goles || 0,         color: 'text-green-400' },
        { label: 'xG',            value: s.ataque?.xg || 0 },
        { label: 'Tiros',         value: s.ataque?.tiros || 0 },
        { label: 'Tiros Puerta',  value: s.ataque?.tiros_puerta || 0 },
      ]
      case 'pase': return [
        { label: 'Asistencias',  value: s.asistencias || 0,                      color: 'text-blue-400' },
        { label: 'xAG',          value: s.organizacion?.xag || 0 },
        { label: 'Pases',        value: s.organizacion?.pases || 0 },
        { label: 'Precisión %',  value: s.organizacion?.pases_accuracy || 0 },
      ]
      case 'regates': return [
        { label: 'Regates ✓',    value: s.regates?.regates_completados || 0,    color: 'text-purple-400' },
        { label: 'Regates ✗',    value: s.regates?.regates_fallidos || 0,       color: 'text-red-400' },
        { label: 'Conducciones', value: s.regates?.conducciones || 0 },
        { label: 'Cond. Prog.',  value: s.regates?.conducciones_progresivas || 0 },
      ]
      case 'defensa': return [
        { label: 'Entradas',     value: s.defensa?.entradas || 0 },
        { label: 'Despejes',     value: s.defensa?.despejes || 0 },
        { label: 'Duelos',       value: s.defensa?.duelos_totales || 0 },
        { label: 'D. Ganados',   value: s.defensa?.duelos_ganados || 0,          color: 'text-green-400' },
        { label: 'D. Aéreos',    value: s.defensa?.duelos_aereos_totales || 0 },
        { label: 'Amarillas',    value: s.comportamiento?.amarillas || 0,        color: 'text-yellow-400' },
        { label: 'Rojas',        value: s.comportamiento?.rojas || 0,            color: 'text-red-500' },
      ]
      default: return []
    }
  }

  const toggleComparacion = (jugador) => {
    setJugadoresComparacion(prev => {
      const existe = prev.find(j => j.jugador_id === jugador.jugador_id)
      if (existe) {
        return prev.filter(j => j.jugador_id !== jugador.jugador_id)
      } else if (prev.length < 4) {
        return [...prev, jugador]
      }
      return prev
    })
  }

  const getFilteredEstadisticas = () => {
    return estadisticas.filter(jug => {
      // Filtro de jornada (por ahora solo usamos jornada desde el parámetro)
      // Los filtros de minJornada/maxJornada se aplicarían si hubiera datos por jornada individual
      
      // Filtro de rango de goles
      if (filtros.minGoles && (jug.goles || 0) < parseFloat(filtros.minGoles)) return false
      if (filtros.maxGoles && (jug.goles || 0) > parseFloat(filtros.maxGoles)) return false
      
      // Filtro de rango de asistencias
      if (filtros.minAsistencias && (jug.asistencias || 0) < parseFloat(filtros.minAsistencias)) return false
      if (filtros.maxAsistencias && (jug.asistencias || 0) > parseFloat(filtros.maxAsistencias)) return false

      // Filtro de rango de puntos fantasy
      if (filtros.minPuntos && (jug.puntos_fantasy || 0) < parseFloat(filtros.minPuntos)) return false
      if (filtros.maxPuntos && (jug.puntos_fantasy || 0) > parseFloat(filtros.maxPuntos)) return false
      
      // Filtro de rango de partidos
      if (filtros.minPartidos && (jug.partidos || 0) < parseInt(filtros.minPartidos)) return false
      if (filtros.maxPartidos && (jug.partidos || 0) > parseInt(filtros.maxPartidos)) return false
      
      // Filtro de rango de tarjetas (amarillas + rojas)
      const tarjetas = (jug.amarillas || 0) + (jug.rojas || 0)
      if (filtros.minTarjetas && tarjetas < parseInt(filtros.minTarjetas)) return false
      if (filtros.maxTarjetas && tarjetas > parseInt(filtros.maxTarjetas)) return false
      
      // Filtro de posición (normalizar ambos lados de la comparación)
      if (filtros.posicion) {
        const posNormalizada = normalizePosicion(jug.posicion)
        if (posNormalizada !== filtros.posicion) return false
      }
      
      // Filtro Goles vs xG
      if (filtros.golesVsXg) {
        const diff = (jug.goles || 0) - (jug.xg || 0)
        if (filtros.golesVsXg === 'encima' && diff <= 0) return false
        if (filtros.golesVsXg === 'debajo' && diff >= 0) return false
      }
      
      // Filtro Asistencias vs xAG
      if (filtros.asistenciasVsXag) {
        const diff = (jug.asistencias || 0) - (jug.xag || 0)
        if (filtros.asistenciasVsXag === 'encima' && diff <= 0) return false
        if (filtros.asistenciasVsXag === 'debajo' && diff >= 0) return false
      }
      
      return true
    })
  }

  const getTopValidValue = (jugador, field, mode) => {
    const total = jugador[field] || 0
    const minutos = jugador.minutos || 1
    const pj = jugador.partidos || 1

    if (mode === 'per90') {
      return (total / (minutos / 90))
    } else if (mode === 'percentil') {
      // Percentil relativo a los otros en la lista
      return jugador[`${field}_percentil`] || 0
    } else {
      return total
    }
  }

  const getSortedTopStats = (cat, mode) => {
    const categoryKey = cat.baseKey || cat.key
    let data = topStats[categoryKey] || []
    
    // Filtrar por posición en todos los modos (si está seleccionada)
    if (posicionPercentiles) {
      data = data.filter(j => normalizePosicion(j.posicion) === posicionPercentiles)
    }
    
    const sorted = [...data]

    if (mode === 'per90') {
      sorted.sort((a, b) => {
        const aVal = (a[categoryKey] || 0) / (a.minutos ? a.minutos / 90 : 1)
        const bVal = (b[categoryKey] || 0) / (b.minutos ? b.minutos / 90 : 1)
        // Si reverseSort, invertir el orden
        return cat.reverseSort ? aVal - bVal : bVal - aVal
      })
    } else if (mode === 'percentil') {
      sorted.sort((a, b) => (b[`${categoryKey}_percentil`] || 0) - (a[`${categoryKey}_percentil`] || 0))
    } else {
      sorted.sort((a, b) => {
        const diff = (b[categoryKey] || 0) - (a[categoryKey] || 0)
        return cat.reverseSort ? -diff : diff
      })
    }

    return sorted.slice(0, 5)
  }

  const getStatValue = (jugador, field, mode) => {
    const total = jugador[field] || 0
    const pj = jugador.partidos || 1
    const minutos = jugador.minutos || 1

    if (mode === 'per90') {
      return formatStat((total / (minutos / 90)))
    } else {
      return formatStat(total)
    }
  }

  const calculatePercentil = (jugador, field, categoryData) => {
    if (!categoryData || categoryData.length === 0) return 0
    // Ya la paginación es manejada por fetchEstadisticas
    return estadisticas
  }

  const formatStat = (value) => {
    if (value === null || value === undefined) return '-'
    if (Number.isInteger(value)) return value.toString()
    return value.toFixed(3)
  }

  const handleColumnSort = (field) => {
    if (sortBy === field) {
      // Si ya está ordenado por este campo, invertir orden
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      // Si es un nuevo campo, ordenar ascendente
      setSortBy(field)
      setSortOrder('asc')
    }
  }

  const getDisplayedJugadores = () => {
    // Mostrar solo los primeros displayCount items
    return estadisticas.slice(0, displayCount)
  }

  return (
    <div className="p-6 space-y-6 bg-background-dark min-h-full">
      {/* Header */}
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-black text-white mb-2">Estadísticas Completas</h1>
        <p className="text-gray-400">Analiza el rendimiento de los jugadores de LaLiga</p>
      </div>

      {/* Filtros */}
      <GlassPanel className="max-w-6xl mx-auto p-6">
        <div className="space-y-4">
          {/* Búsqueda y Jornada */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input
              type="text"
              placeholder="Buscar jugador..."
              value={search}
              onChange={handleSearch}
              className="px-4 py-2 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary"
            />
            <select
              value={jornada === null ? '' : jornada}
              onChange={(e) => setJornada(e.target.value === '' ? null : e.target.value)}
              className="px-4 py-2 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary"
            >
              <option value="">Selecciona una jornada</option>
              <option value="acumulado">
                {temporada === '25_26' 
                  ? `Hasta jornada ${jornadaActual} (acumulado)` 
                  : 'Temporada completa (38 jornadas)'}
              </option>
              {(temporada === '24_25' || temporada === '23_24') && (
                <>
                  <option value="primera_vuelta">Primera vuelta (J1-J18)</option>
                  <option value="segunda_vuelta">Segunda vuelta (J19-J38)</option>
                </>
              )}
              {Array.from({ length: 38 }).map((_, i) => (
                <option key={i + 1} value={i + 1}>Jornada {i + 1}</option>
              ))}
            </select>
            <select
              value={temporada}
              onChange={(e) => {
                setTemporada(e.target.value)
                setCurrentPage(0)
              }}
              className="px-4 py-2 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary"
            >
              <option value="25_26">Temporada 25/26</option>
              <option value="24_25">Temporada 24/25</option>
              <option value="23_24">Temporada 23/24</option>
            </select>
          </div>

          {/* Tipo de Estadística */}
          <div className="flex gap-2 flex-wrap">
            {TIPO_OPCIONES.map(opt => (
              <button
                key={opt.key}
                onClick={() => setTipo(tipo === opt.key ? null : opt.key)}
                className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${
                  tipo === opt.key
                    ? 'bg-primary text-black'
                    : 'bg-white/10 text-gray-300 hover:bg-white/20'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Controles: Botón Filtros + Comparar */}
          <div className="flex gap-4 flex-wrap items-center justify-end">
            <div className="flex gap-3">
              <button
                onClick={() => setFiltroModalOpen(true)}
                className="px-6 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold transition-all flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-sm">tune</span>
                Filtros
              </button>

              {/* Botón de comparación */}
              <button
                onClick={() => setCompareModalOpen(true)}
                className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white font-bold transition-all"
              >
                Comparar
              </button>
            </div>
          </div>
        </div>
      </GlassPanel>

      {/* Modal de Filtros */}
      {filtroModalOpen && (
        <div className="fixed inset-0 bg-black/80 z-[9999] flex items-center justify-center" onClick={() => setFiltroModalOpen(false)}>
          <div className="bg-surface-dark rounded-2xl max-w-2xl w-full mx-4 max-h-[85vh] overflow-y-auto glass-panel flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 bg-surface-dark flex items-center justify-between px-6 py-4 border-b border-border-dark rounded-t-2xl">
                <h2 className="text-xl font-black text-white">Filtros Avanzados</h2>
                <button
                  onClick={() => setFiltroModalOpen(false)}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <span className="material-symbols-outlined icon-2xl">close</span>
                </button>
              </div>

              <div className="px-6 py-4 space-y-4 overflow-y-auto flex-1">
                {/* Posición - ARRIBA PARA TODOS */}
                <div className="bg-primary/10 rounded-lg p-4 border border-primary/30">
                  <label className="text-sm font-bold text-primary mb-2 block">Posición</label>
                  <select
                    value={filtros.posicion}
                    onChange={(e) => setFiltros({...filtros, posicion: e.target.value})}
                    className="w-full px-3 py-2 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                  >
                    <option value="">Todas las posiciones</option>
                    <option value="PT">Portero (PT)</option>
                    <option value="DF">Defensa (DF)</option>
                    <option value="MC">Mediocampista (MC)</option>
                    <option value="DT">Delantero (DT)</option>
                  </select>
                </div>

                {/* Rango de Jornadas */}
                <div className="bg-white/5 rounded-lg p-4 border border-border-dark/50">
                  <label className="text-sm font-bold text-gray-300 mb-2 block">Rango de Jornadas</label>
                  <div className="flex gap-3 items-center">
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Inicial"
                        min="1"
                        max="38"
                        value={filtros.minJornada}
                        onChange={(e) => setFiltros({...filtros, minJornada: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                    <span className="text-gray-400 font-bold text-sm">a</span>
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Final"
                        min="1"
                        max="38"
                        value={filtros.maxJornada}
                        onChange={(e) => setFiltros({...filtros, maxJornada: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                  </div>
                </div>

                {/* Goles */}
                <div>
                  <label className="text-sm font-bold text-gray-300 mb-2 block">Goles</label>
                  <div className="flex gap-3 items-center">
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Mín"
                        value={filtros.minGoles}
                        onChange={(e) => setFiltros({...filtros, minGoles: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                    <span className="text-gray-400 text-sm">a</span>
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Máx"
                        value={filtros.maxGoles}
                        onChange={(e) => setFiltros({...filtros, maxGoles: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                  </div>
                </div>

                {/* Marcando por encima/debajo de xG */}
                <div>
                  <label className="text-sm font-bold text-green-400 mb-2 block">Marcando vs xG</label>
                  <select
                    value={filtros.golesVsXg}
                    onChange={(e) => setFiltros({...filtros, golesVsXg: e.target.value})}
                    className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                  >
                    <option value="">Todos</option>
                    <option value="encima">POR ENCIMA de sus posibilidades</option>
                    <option value="debajo">POR DEBAJO de sus posibilidades</option>
                  </select>
                </div>

                {/* Asistencias */}
                <div>
                  <label className="text-sm font-bold text-gray-300 mb-2 block">Asistencias</label>
                  <div className="flex gap-3 items-center">
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Mín"
                        value={filtros.minAsistencias}
                        onChange={(e) => setFiltros({...filtros, minAsistencias: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                    <span className="text-gray-400 text-sm">a</span>
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Máx"
                        value={filtros.maxAsistencias}
                        onChange={(e) => setFiltros({...filtros, maxAsistencias: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                  </div>
                </div>

                {/* Puntos Fantasy */}
                <div>
                  <label className="text-sm font-bold text-yellow-400 mb-2 block">Puntos Fantasy</label>
                  <div className="flex gap-3 items-center">
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Mín"
                        value={filtros.minPuntos}
                        onChange={(e) => setFiltros({...filtros, minPuntos: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                    <span className="text-gray-400 text-sm">a</span>
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Máx"
                        value={filtros.maxPuntos}
                        onChange={(e) => setFiltros({...filtros, maxPuntos: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                  </div>
                </div>

                {/* Asistiendo por encima/debajo de xAG */}
                <div>
                  <label className="text-sm font-bold text-blue-400 mb-2 block">Asistiendo vs xAG</label>
                  <select
                    value={filtros.asistenciasVsXag}
                    onChange={(e) => setFiltros({...filtros, asistenciasVsXag: e.target.value})}
                    className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                  >
                    <option value="">Todos</option>
                    <option value="encima">POR ENCIMA de sus posibilidades</option>
                    <option value="debajo">POR DEBAJO de sus posibilidades</option>
                  </select>
                </div>

                {/* Partidos Jugados */}
                <div>
                  <label className="text-sm font-bold text-gray-300 mb-2 block">Partidos Jugados</label>
                  <div className="flex gap-3 items-center">
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Mín"
                        value={filtros.minPartidos}
                        onChange={(e) => setFiltros({...filtros, minPartidos: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                    <span className="text-gray-400 text-sm">a</span>
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Máx"
                        value={filtros.maxPartidos}
                        onChange={(e) => setFiltros({...filtros, maxPartidos: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                  </div>
                </div>

                {/* Tarjetas */}
                <div>
                  <label className="text-sm font-bold text-gray-300 mb-2 block">Tarjetas (Amarillas + Rojas)</label>
                  <div className="flex gap-3 items-center">
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Mín"
                        value={filtros.minTarjetas}
                        onChange={(e) => setFiltros({...filtros, minTarjetas: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                    <span className="text-gray-400 text-sm">a</span>
                    <div className="flex-1">
                      <input
                        type="number"
                        placeholder="Máx"
                        value={filtros.maxTarjetas}
                        onChange={(e) => setFiltros({...filtros, maxTarjetas: e.target.value})}
                        className="w-full px-3 py-1 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-sm"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="border-t border-border-dark flex justify-between items-center px-6 py-4 bg-surface-dark rounded-b-2xl">
                <button
                  onClick={() => setFiltros({
                    minJornada: '',
                    maxJornada: '',
                    minGoles: '',
                    maxGoles: '',
                    minAsistencias: '',
                    maxAsistencias: '',
                    minPuntos: '',
                    maxPuntos: '',
                    minPartidos: '',
                    maxPartidos: '',
                    minTarjetas: '',
                    maxTarjetas: '',
                    posicion: '',
                    golesVsXg: '',
                    asistenciasVsXag: ''
                  })}
                  className="px-4 py-2 text-sm rounded-lg border border-border-dark text-white hover:bg-white/5 transition-all font-bold"
                >
                  Limpiar
                </button>
                <button
                  onClick={() => setFiltroModalOpen(false)}
                  className="px-6 py-2 text-sm rounded-lg bg-primary hover:bg-primary/80 text-white transition-all font-bold"
                >
                  Aplicar filtros
                </button>
              </div>
          </div>
        </div>
      )}

      {/* Modal de Comparación - 4 Jugadores */}
      {compareModalOpen && (
        <div className="fixed inset-0 bg-black/80 z-[99999] flex items-center justify-center" onClick={() => setCompareModalOpen(false)}>
          <div className="bg-surface-dark rounded-2xl max-w-6xl w-full mx-4 max-h-[92vh] overflow-y-auto glass-panel flex flex-col" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="sticky top-0 bg-surface-dark rounded-t-2xl flex justify-between items-center px-8 py-5 border-b border-border-dark z-10">
              <h3 className="text-2xl font-black text-white uppercase tracking-wider">
                Comparar <span className="text-primary">Jugadores</span>
              </h3>
              <button 
                onClick={() => {
                  setCompareModalOpen(false)
                  setJugadoresComparacion([null, null, null, null])
                  setComparisonTemporales(['', '', '', ''])
                  setComparisonDatas([null, null, null, null])
                  setComparisonAvailableSeasons([[], [], [], []])
                  setSearchJugadores(['', '', '', ''])
                }}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <span className="material-symbols-outlined icon-2xl">close</span>
              </button>
            </div>

            <div className="px-8 py-6 space-y-6">
              {/* PASO 1: Selección de jugadores y temporadas */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[0, 1, 2, 3].map(slotIdx => (
                  <div key={slotIdx} className="border border-border-dark rounded-xl p-4 bg-white/5 flex flex-col gap-3">
                    <h4 className="text-xs font-black text-gray-400 uppercase tracking-wider">Jugador {slotIdx + 1}</h4>

                    {!jugadoresComparacion[slotIdx] ? (
                      <>
                        <input
                          type="text"
                          placeholder="Buscar jugador..."
                          value={searchJugadores[slotIdx]}
                          onChange={(e) => {
                            const n = [...searchJugadores]
                            n[slotIdx] = e.target.value
                            setSearchJugadores(n)
                          }}
                          className="w-full px-3 py-2 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-xs"
                        />
                        <div className="max-h-48 overflow-y-auto border border-border-dark rounded-lg bg-black/30 divide-y divide-border-dark">
                          {estadisticas
                            .filter(j => {
                              const fullName = (j.nombre + ' ' + j.apellido).toLowerCase()
                              const alreadySelected = jugadoresComparacion.some(jug => jug?.jugador_id === j.jugador_id)
                              return fullName.includes(searchJugadores[slotIdx].toLowerCase()) && !alreadySelected
                            })
                            .slice(0, 8)
                            .map(jug => {
                              const capturedJug = jug
                              const capturedSlot = slotIdx
                              return (
                                <button
                                  key={jug.jugador_id}
                                  onClick={() => {
                                    const n = [...jugadoresComparacion]
                                    n[capturedSlot] = capturedJug
                                    setJugadoresComparacion(n)
                                    // Limpiar datos previos de este slot
                                    setComparisonTemporales(prev => { const t = [...prev]; t[capturedSlot] = ''; return t })
                                    setComparisonDatas(prev => { const d = [...prev]; d[capturedSlot] = null; return d })
                                    fetchPlayerSeasons(capturedJug.jugador_id, capturedSlot)
                                  }}
                                  className="w-full text-left p-2 hover:bg-white/10 transition-colors flex items-center gap-2"
                                >
                                  {jug.equipo_escudo && (
                                    <TeamShield escudo={jug.equipo_escudo} nombre={jug.equipo} className="w-5 h-5 flex-shrink-0" />
                                  )}
                                  <div className="min-w-0">
                                    <p className="font-bold text-white text-xs truncate">{jug.nombre} {jug.apellido}</p>
                                    <p className="text-xs text-gray-400 truncate">{jug.equipo}</p>
                                  </div>
                                </button>
                              )
                            })}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="bg-primary/20 border border-primary rounded-lg p-2">
                          {jugadoresComparacion[slotIdx].equipo_escudo && (
                            <TeamShield escudo={jugadoresComparacion[slotIdx].equipo_escudo} nombre={jugadoresComparacion[slotIdx].equipo} className="w-6 h-6 mb-1" />
                          )}
                          <p className="font-bold text-white text-xs">{jugadoresComparacion[slotIdx].nombre} {jugadoresComparacion[slotIdx].apellido}</p>
                          <p className="text-xs text-gray-400">{jugadoresComparacion[slotIdx].equipo}</p>
                          <button
                            onClick={() => {
                              const s = slotIdx
                              setJugadoresComparacion(prev => { const n = [...prev]; n[s] = null; return n })
                              setComparisonTemporales(prev => { const n = [...prev]; n[s] = ''; return n })
                              setComparisonDatas(prev => { const n = [...prev]; n[s] = null; return n })
                              setComparisonAvailableSeasons(prev => { const n = [...prev]; n[s] = []; return n })
                            }}
                            className="text-primary hover:text-white text-xs mt-1 font-bold"
                          >
                            Cambiar jugador
                          </button>
                        </div>

                        <div>
                          <label className="block text-xs font-bold text-gray-300 mb-1">Temporada</label>
                          <select
                            value={comparisonTemporales[slotIdx]}
                            onChange={(e) => {
                              const val = e.target.value
                              const s = slotIdx
                              setComparisonTemporales(prev => { const n = [...prev]; n[s] = val; return n })
                            }}
                            className="w-full px-2 py-1 bg-black border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none text-xs"
                          >
                            <option value="">Elige temporada</option>
                            <option value="carrera">Últimas 3 temporadas</option>
                            {comparisonAvailableSeasons[slotIdx].map(temp => (
                              <option key={temp.nombre} value={temp.display}>{temp.display}</option>
                            ))}
                          </select>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>

              {/* SELECTOR DE DOMINIO */}
              <div className="flex gap-2 flex-wrap items-center pt-2">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-wider mr-2">Ver:</span>
                {COMPARISON_DOMAINS.map(dom => (
                  <button
                    key={dom.key}
                    onClick={() => setComparisonDomain(dom.key)}
                    className={`px-4 py-1 rounded-lg font-bold text-sm transition-all ${
                      comparisonDomain === dom.key
                        ? 'bg-primary text-black'
                        : 'bg-white/10 text-gray-300 hover:bg-white/20'
                    }`}
                  >
                    {dom.label}
                  </button>
                ))}
              </div>

              {/* BOTÓN ÚNICO CARGAR */}
              {jugadoresComparacion.some(j => j) && comparisonTemporales.some((t, i) => t && jugadoresComparacion[i]) && (
                <button
                  onClick={async () => {
                    setComparisonLoading(true)
                    // Capturar los valores actuales para evitar stale closures
                    const jugadoresSnapshot = [...jugadoresComparacion]
                    const temporalesSnapshot = [...comparisonTemporales]
                    const promises = [0, 1, 2, 3].map(async (i) => {
                      if (jugadoresSnapshot[i] && temporalesSnapshot[i]) {
                        return fetchComparacionData(jugadoresSnapshot[i].jugador_id, temporalesSnapshot[i])
                      }
                      return null
                    })
                    const results = await Promise.all(promises)
                    setComparisonDatas(results)
                    setComparisonLoading(false)
                  }}
                  disabled={comparisonLoading}
                  className="w-full px-6 py-3 bg-primary hover:bg-primary/80 disabled:opacity-50 text-white font-black rounded-xl transition-colors uppercase tracking-wider flex items-center justify-center gap-2"
                >
                  {comparisonLoading ? (
                    <><span className="material-symbols-outlined animate-spin text-sm">refresh</span> Cargando...</>
                  ) : (
                    <><span className="material-symbols-outlined text-sm">compare_arrows</span> Cargar comparación</>
                  )}
                </button>
              )}

              {/* TABLA DE COMPARACIÓN */}
              {comparisonDatas.some(d => d) && (() => {
                const activeSlots = [0, 1, 2, 3].filter(i => comparisonDatas[i] && jugadoresComparacion[i])
                if (activeSlots.length === 0) return null

                const allStats = activeSlots.map(i => getStatsByDomain(comparisonDatas[i], comparisonDomain))
                const statLabels = allStats[0]?.map(s => s.label) || []

                return (
                  <div className="rounded-xl border border-border-dark overflow-hidden">
                    {/* Cabecera jugadores */}
                    <div className={`grid border-b border-border-dark bg-surface-dark/60`} style={{ gridTemplateColumns: `180px repeat(${activeSlots.length}, 1fr)` }}>
                      <div className="px-4 py-3 text-xs font-bold text-gray-400 uppercase">Estadística</div>
                      {activeSlots.map(i => (
                        <div key={i} className="px-4 py-3 text-center">
                          {jugadoresComparacion[i].equipo_escudo && (
                            <TeamShield escudo={jugadoresComparacion[i].equipo_escudo} nombre={jugadoresComparacion[i].equipo} className="w-5 h-5 inline-block mr-1" />
                          )}
                          <p className="text-xs font-black text-white truncate">{jugadoresComparacion[i].nombre} {jugadoresComparacion[i].apellido}</p>
                          <p className="text-xs text-gray-400">{comparisonTemporales[i]}</p>
                        </div>
                      ))}
                    </div>

                    {/* Filas de stats */}
                    {statLabels.map((label, rowIdx) => {
                      const values = activeSlots.map(i => allStats[activeSlots.indexOf(i)][rowIdx]?.value ?? 0)
                      const maxVal = Math.max(...values)
                      return (
                        <div
                          key={label}
                          className={`grid border-b border-border-dark/50 ${ rowIdx % 2 === 0 ? 'bg-white/3' : 'bg-transparent'}`}
                          style={{ gridTemplateColumns: `180px repeat(${activeSlots.length}, 1fr)` }}
                        >
                          <div className="px-4 py-3 text-xs text-gray-400 font-bold flex items-center">{label}</div>
                          {activeSlots.map((i, colIdx) => {
                            const stat = allStats[colIdx][rowIdx]
                            const isTop = stat?.value === maxVal && maxVal > 0
                            return (
                              <div key={i} className={`px-4 py-3 text-center font-bold text-sm ${ isTop ? 'bg-primary/10' : '' }`}>
                                <span className={stat?.color || (isTop ? 'text-primary' : 'text-white')}>
                                  {stat?.value ?? 0}
                                </span>
                                {isTop && values.filter(v => v === maxVal).length === 1 && (
                                  <span className="ml-1 text-xs text-primary">↑</span>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )
                    })}
                  </div>
                )
              })()}

              {!comparisonDatas.some(d => d) && (
                <div className="text-center py-10 text-gray-400">
                  <span className="material-symbols-outlined text-4xl block mb-3 opacity-30">compare_arrows</span>
                  <p>Selecciona jugadores, elige temporadas y pulsa "Cargar comparación"</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tabla Principal */}
      {jornada === null ? (
        <GlassPanel className="max-w-6xl mx-auto p-12 text-center">
          <div className="space-y-4">
            <div>
              <span className="material-symbols-outlined text-6xl block mb-4 text-gray-400">calendar_month</span>
              <h2 className="text-2xl font-bold text-white mb-2">Selecciona una jornada</h2>
              <p className="text-gray-400 leading-relaxed max-w-md mx-auto">
                Selecciona una jornada para ver <strong>datos sólo de esa</strong> o <strong>hasta la jornada actual para ver el acumulado</strong>
              </p>
            </div>
          </div>
        </GlassPanel>
      ) : loading || topLoading ? (
        <div className="max-w-6xl mx-auto p-12 text-center">
          <LoadingSpinner />
          <p className="text-gray-400 mt-4">Cargando datos completos...</p>
        </div>
      ) : estadisticas.length === 0 ? (
        <div className="max-w-6xl mx-auto p-8 text-center">
          <p className="text-gray-400">Sin resultados</p>
        </div>
      ) : (
        <>
          <GlassPanel className="max-w-6xl mx-auto overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-dark bg-surface-dark/50">
                    <th className="px-4 py-3 text-left font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('nombre')}>
                      Jugador {sortBy === 'nombre' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs">Equipo</th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs">Pos</th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('puntos_fantasy')}>
                      Puntos {sortBy === 'puntos_fantasy' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('goles')}>
                      Goles {sortBy === 'goles' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('asistencias')}>
                      Asistencias {sortBy === 'asistencias' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('xg')}>
                      xG {sortBy === 'xg' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('xag')}>
                      xAG {sortBy === 'xag' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('amarillas')}>
                      Amarillas {sortBy === 'amarillas' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('rojas')}>
                      Rojas {sortBy === 'rojas' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                    <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs cursor-pointer hover:text-white transition-colors" onClick={() => handleColumnSort('partidos')}>
                      PJ {sortBy === 'partidos' && <span>{sortOrder === 'asc' ? '↑' : '↓'}</span>}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {getDisplayedJugadores().map((jug) => (
                    <tr key={jug.jugador_id} className="border-b border-border-dark hover:bg-white/5 transition-colors">
                      <td className="px-4 py-3">
                        <button
                          onClick={() => navigate(`/jugador/${jug.jugador_id}`)}
                          className="font-bold text-white hover:text-primary hover:underline transition-colors text-left"
                        >
                          {jug.nombre} {jug.apellido}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-2">
                          {jug.equipo_escudo && (
                            <TeamShield
                              escudo={jug.equipo_escudo}
                              nombre={jug.equipo}
                              className="w-6 h-6"
                            />
                          )}
                          <span className="text-xs text-gray-400">{jug.equipo}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center text-xs text-gray-400">{jug.posicion}</td>
                      <td className="px-4 py-3 text-center font-bold text-yellow-400">{formatStat(jug.puntos_fantasy)}</td>
                      <td className="px-4 py-3 text-center font-bold text-white">{formatStat(jug.goles)}</td>
                      <td className="px-4 py-3 text-center font-bold text-white">{formatStat(jug.asistencias)}</td>
                      <td className="px-4 py-3 text-center text-gray-400">{formatStat(jug.xg)}</td>
                      <td className="px-4 py-3 text-center text-gray-400">{formatStat(jug.xag)}</td>
                      <td className="px-4 py-3 text-center font-bold text-yellow-400">{formatStat(jug.amarillas)}</td>
                      <td className="px-4 py-3 text-center font-bold text-red-500">{formatStat(jug.rojas)}</td>
                      <td className="px-4 py-3 text-center text-gray-400">{jug.partidos}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassPanel>

          {/* Botón mostrar más y Paginación */}
          {jornada && (
            <div className="max-w-6xl mx-auto mt-6 flex items-center justify-center gap-2 flex-wrap">
              {/* Mostrar "Mostrar más" si estamos en página 1 y hay más items disponibles */}
              {currentPage === 0 && displayCount === 10 && estadisticas.length > 10 && (
                <button
                  onClick={() => setDisplayCount(20)}
                  className="px-4 py-2 bg-primary hover:bg-primary/90 text-black font-bold rounded-lg transition-colors"
                >
                  Mostrar más
                </button>
              )}
              
              {/* Controles de paginación: mostrar si estamos en desde al menos 20 items o en página 2+ */}
              {(displayCount === 20 || currentPage > 0) && (
                <>
                  <button
                    onClick={() => {
                      if (currentPage > 0) {
                        setCurrentPage(prev => prev - 1)
                        setDisplayCount(10) // Reset display count al cambiar página
                      }
                    }}
                    disabled={currentPage === 0 && displayCount === 10}
                    className="px-4 py-2 bg-white/10 hover:bg-white/20 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-lg transition-colors"
                  >
                    Anterior
                  </button>
                  <span className="text-gray-400 font-bold">
                    Página {currentPage + 1}
                  </span>
                  <button
                    onClick={() => {
                      setCurrentPage(prev => prev + 1)
                      setDisplayCount(10) // Reset display count al cambiar página
                    }}
                    disabled={estadisticas.length < 20}
                    className="px-4 py-2 bg-white/10 hover:bg-white/20 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-lg transition-colors"
                  >
                    Siguiente
                  </button>
                </>
              )}
            </div>
          )}
        </>
      )}

      {/* TOP Jugadores */}
      {jornada && (
        <>
          <div className="max-w-6xl mx-auto">
            <div className="mb-6">
              <h2 className="text-2xl font-black text-white mb-4">Top Jugadores</h2>
            </div>
          
            <div className="flex gap-2 flex-wrap items-center">
            <button
              onClick={() => setTopViewMode('total')}
              className={`px-4 py-2 rounded-lg font-bold transition-all ${
                topViewMode === 'total'
                  ? 'bg-primary text-black'
                  : 'bg-white/10 text-gray-300 hover:bg-white/20'
              }`}
            >
              Total
            </button>
            <button
              onClick={() => setTopViewMode('per90')}
              className={`px-4 py-2 rounded-lg font-bold transition-all ${
                topViewMode === 'per90'
                  ? 'bg-primary text-black'
                  : 'bg-white/10 text-gray-300 hover:bg-white/20'
              }`}
            >
              Por 90 min
            </button>
            <div className="relative">
              <button
                onClick={() => {
                  setTopViewMode('percentil')
                  setMostrarDescripcionPercentiles(!mostrarDescripcionPercentiles)
                }}
                className={`px-4 py-2 rounded-lg font-bold transition-all ${
                  topViewMode === 'percentil'
                    ? 'bg-primary text-black'
                    : 'bg-white/10 text-gray-300 hover:bg-white/20'
                }`}
              >
                Percentiles
              </button>
              {mostrarDescripcionPercentiles && (
                <div className="absolute top-full left-0 mt-2 bg-surface-dark border border-border-dark rounded-lg p-4 w-96 shadow-2xl z-50">
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-bold text-white text-sm">¿Qué son los Percentiles?</h3>
                    <button
                      onClick={() => setMostrarDescripcionPercentiles(false)}
                      className="text-gray-400 hover:text-white transition-colors"
                    >
                      <span className="material-symbols-outlined text-sm">close</span>
                    </button>
                  </div>
                  <div className="space-y-3 text-xs text-gray-300">
                    <p>
                      <strong className="text-primary">Percentil</strong> = porcentaje de jugadores de tu misma posición que tienes por debajo en esa estadística.
                    </p>
                    <p className="flex gap-2">
                      <span>📈</span>
                      <span><strong className="text-green-400">Alto (80-100%)</strong> = Excelente en esa stat. Eres mejor que la mayoría.</span>
                    </p>
                    <p className="flex gap-2">
                      <span>📊</span>
                      <span><strong className="text-yellow-400">Medio (40-60%)</strong> = Rendimiento promedio en esa posición.</span>
                    </p>
                    <p className="flex gap-2">
                      <span>📉</span>
                      <span><strong className="text-orange-400">Bajo (0-20%)</strong> = Hay muchos jugadores mejores en esa stat.</span>
                    </p>
                    <p className="mt-2 text-gray-400">Ejemplo: Si tienes <strong>92% en despejes</strong>, significa que <strong>92 de cada 100 porteros</strong> despejan menos que tú.</p>
                  </div>
                </div>
              )}
            </div>

            {/* Posición filter - ahora visible para todos los modos */}
            {topLoading && <p className="text-gray-400 text-xs">Actualizando...</p>}
            <select
              value={posicionPercentiles}
              onChange={(e) => setPosicionPercentiles(e.target.value)}
              className="px-4 py-2 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary font-bold text-sm"
            >
              <option value="">Todas posiciones</option>
              <option value="PT">Portero (PT)</option>
              <option value="DF">Defensa (DF)</option>
              <option value="MC">Mediocampista (MC)</option>
              <option value="DT">Delantero (DT)</option>
            </select>
          </div>
        </div>

        {loading || topLoading ? (
          <div className="max-w-6xl mx-auto p-12 text-center">
            <LoadingSpinner />
            <p className="text-gray-400 mt-4">Cargando datos completos...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {TOP_CATEGORIES.map(cat => (
              <GlassPanel key={cat.key} className="overflow-hidden">
                <button
                  onClick={() => setExpandedCategories(prev => ({ ...prev, [cat.key]: !prev[cat.key] }))}
                  className="w-full text-lg font-bold text-white p-4 border-b border-border-dark bg-surface-dark/30 hover:bg-surface-dark/50 transition-colors flex items-center justify-between"
                >
                  <span>{cat.label}</span>
                  <span className="text-sm">
                    {expandedCategories[cat.key] ? '▼' : '▶'}
                  </span>
                </button>
                {expandedCategories[cat.key] && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border-dark bg-surface-dark/50">
                          <th className="px-4 py-3 text-left font-bold text-gray-400 uppercase text-xs">Jugador</th>
                          <th className="px-4 py-3 text-center font-bold text-gray-400 uppercase text-xs">
                            {topViewMode === 'per90' ? `${cat.label} /90` : topViewMode === 'percentil' ? 'Percentil' : cat.label}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {getSortedTopStats(cat, topViewMode).map((jug, idx) => {
                          const baseKey = cat.baseKey || cat.key
                          return (
                            <tr key={jug.jugador_id} className="border-b border-border-dark hover:bg-white/5 transition-colors">
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-primary">{idx + 1}</span>
                                  <div className="min-w-0">
                                    <button
                                      onClick={() => navigate(`/jugador/${jug.jugador_id}`)}
                                      className="font-bold text-white text-sm truncate hover:text-primary hover:underline transition-colors text-left"
                                    >
                                      {jug.nombre} {jug.apellido}
                                    </button>
                                    <div className="flex gap-2 items-center text-xs text-gray-400">
                                      <span>{jug.posicion}</span>
                                      <span>•</span>
                                      <span>{jug.equipo}</span>
                                    </div>
                                  </div>
                                </div>
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span className="font-bold text-white">
                                  {topViewMode === 'percentil'
                                    ? `${jug[`${baseKey}_percentil`] || 0}%`
                                    : formatStat(getTopValidValue(jug, baseKey, topViewMode))
                                  }
                                </span>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </GlassPanel>
            ))}
          </div>
        )}
      </>
      )}
    </div>
  )
}

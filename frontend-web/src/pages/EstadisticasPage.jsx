import { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'
import HelpButton from '../components/ui/HelpButton'
import ComparisonMetricsCards from '../components/comparison/ComparisonMetricsCards'
import { COMPARISON_DOMAINS } from '../components/comparison/comparisonConfig'
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  Tooltip as RechartsTooltip,
} from 'recharts'

const MAX_COMPARE_PLAYERS = 8
const COMPARE_COLORS = ['#22d3ee', '#fb7185', '#a3e635', '#facc15', '#60a5fa', '#f97316', '#34d399', '#c084fc']

const createEmptyComparisonSlot = () => ({
  player: null,
  temporada: '',
  data: null,
  radar: null,
  availableSeasons: [],
  search: '',
  searchResults: [],
  searchLoading: false,
})

const getCompareCardMinWidth = (count) => {
  if (count >= 6) return 160
  if (count >= 4) return 180
  return 220
}

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
  const [compareSlots, setCompareSlots] = useState([createEmptyComparisonSlot(), createEmptyComparisonSlot()])
  const [comparisonLoading, setComparisonLoading] = useState(false)
  const [comparisonDomain, setComparisonDomain] = useState('general')
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
  const compareSearchTimerRef = useRef({})

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
      // No se sobreescribe jornada para preservar la selección del usuario en el select
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
      const { data } = await api.get(`/api/jugador/${jugadorId}/?temporada=${encodeURIComponent(temporadaStr)}`)
      return data
    } catch (e) {
      console.error('Error fetching comparison data:', e)
      return null
    }
  }

  const fetchComparacionRadar = async (jugadorId, temporadaStr) => {
    if (!temporadaStr || temporadaStr === 'carrera') return null

    try {
      const temporadaApi = temporadaStr.replace('/', '_')
      const { data } = await api.get(`/api/radar/${jugadorId}/${temporadaApi}/`)
      if (data?.status !== 'success') return null
      return data.data
    } catch (e) {
      console.error('Error fetching comparison radar:', e)
      return null
    }
  }

  const normalizeComparisonStats = (payload) => {
    const s = payload?.stats || {}
    const ataque = s.ataque || {}
    const organizacion = s.organizacion || {}
    const regates = s.regates || {}
    const defensa = s.defensa || {}
    const comportamiento = s.comportamiento || {}

    const goles = Number(s.goles ?? ataque.goles ?? 0)
    const xg = Number(s.xg ?? ataque.xg ?? 0)
    const asistencias = Number(s.asistencias ?? 0)
    const xag = Number(s.xag ?? organizacion.xag ?? 0)
    const partidos = Number(s.partidos ?? 0)
    const minutos = Number(s.minutos ?? 0)
    const puntosPorPartido = Number(s.promedio_puntos ?? s.puntos_por_partido ?? 0)

    return {
      puntos_por_partido: Number(puntosPorPartido.toFixed(2)),
      partidos,
      minutos,
      goles,
      asistencias,
      xg,
      xag,
      goles_vs_xg: Number((goles - xg).toFixed(2)),
      asistencias_vs_xag: Number((asistencias - xag).toFixed(2)),
      tiros: Number(ataque.tiros ?? 0),
      tiros_puerta: Number(ataque.tiros_puerta ?? 0),
      pases: Number(organizacion.pases ?? 0),
      pases_accuracy: Number(organizacion.pases_accuracy ?? 0),
      regates_completados: Number(regates.regates_completados ?? 0),
      regates_fallidos: Number(regates.regates_fallidos ?? 0),
      conducciones: Number(regates.conducciones ?? 0),
      conducciones_progresivas: Number(regates.conducciones_progresivas ?? 0),
      entradas: Number(defensa.entradas ?? 0),
      despejes: Number(defensa.despejes ?? 0),
      duelos_totales: Number(defensa.duelos_totales ?? 0),
      duelos_ganados: Number(defensa.duelos_ganados ?? 0),
      duelos_perdidos: Number(defensa.duelos_perdidos ?? 0),
      duelos_aereos_totales: Number(defensa.duelos_aereos_totales ?? 0),
      amarillas: Number(comportamiento.amarillas ?? 0),
      rojas: Number(comportamiento.rojas ?? 0),
    }
  }

  const updateCompareSlot = (slotIdx, patch) => {
    setCompareSlots(prev => prev.map((slot, idx) => {
      if (idx !== slotIdx) return slot
      const patchObj = typeof patch === 'function' ? patch(slot) : patch
      return { ...slot, ...patchObj }
    }))
  }

  const resetComparison = () => {
    setCompareSlots([createEmptyComparisonSlot(), createEmptyComparisonSlot()])
    setComparisonDomain('general')
    setComparisonLoading(false)
  }

  const addCompareSlot = () => {
    setCompareSlots(prev => {
      if (prev.length >= MAX_COMPARE_PLAYERS) return prev
      return [...prev, createEmptyComparisonSlot()]
    })
  }

  const removeCompareSlot = (slotIdx) => {
    setCompareSlots(prev => {
      if (prev.length <= 2) return prev
      return prev.filter((_, idx) => idx !== slotIdx)
    })
  }

  const handleCompareSearch = (slotIdx, query) => {
    updateCompareSlot(slotIdx, { search: query })
    clearTimeout(compareSearchTimerRef.current[slotIdx])

    if (query.trim().length < 2) {
      updateCompareSlot(slotIdx, { searchResults: [], searchLoading: false })
      return
    }

    updateCompareSlot(slotIdx, { searchLoading: true })

    compareSearchTimerRef.current[slotIdx] = setTimeout(async () => {
      try {
        const { data } = await api.get(`/api/buscar/?q=${encodeURIComponent(query.trim())}`)
        const selectedIds = compareSlots
          .map(slot => slot.player?.jugador_id)
          .filter(Boolean)

        const results = (data?.results || [])
          .filter(item => item.type === 'jugador' && !selectedIds.includes(item.id))
          .map(item => ({
            jugador_id: item.id,
            nombreCompleto: item.nombre,
            posicion: item.posicion,
          }))

        updateCompareSlot(slotIdx, { searchResults: results, searchLoading: false })
      } catch (error) {
        updateCompareSlot(slotIdx, { searchResults: [], searchLoading: false })
      }
    }, 320)
  }

  const handleSelectComparePlayer = async (slotIdx, selectedPlayer) => {
    const alreadySelected = compareSlots.some(
      (slot, idx) => idx !== slotIdx && slot.player?.jugador_id === selectedPlayer.jugador_id
    )
    if (alreadySelected) return

    updateCompareSlot(slotIdx, { searchLoading: true })

    try {
      const { data } = await api.get(`/api/jugador/${selectedPlayer.jugador_id}/`)
      const seasons = data?.temporadas_disponibles || []
      const defaultSeason = seasons[0]?.display || ''

      updateCompareSlot(slotIdx, {
        player: {
          jugador_id: data?.jugador?.id || selectedPlayer.jugador_id,
          nombre: data?.jugador?.nombre || selectedPlayer.nombreCompleto,
          apellido: data?.jugador?.apellido || '',
          equipo: data?.equipo_temporada?.equipo?.nombre || '',
          equipo_escudo: data?.equipo_temporada?.equipo?.escudo || '',
          posicion: data?.jugador?.posicion || selectedPlayer.posicion || '',
        },
        temporada: defaultSeason,
        availableSeasons: seasons,
        data: null,
        radar: null,
        search: '',
        searchResults: [],
        searchLoading: false,
      })
    } catch (error) {
      updateCompareSlot(slotIdx, { searchLoading: false })
    }
  }

  const clearComparePlayer = (slotIdx) => {
    updateCompareSlot(slotIdx, createEmptyComparisonSlot())
  }

  const handleCompareSeasonChange = (slotIdx, temporadaValue) => {
    updateCompareSlot(slotIdx, {
      temporada: temporadaValue,
      data: null,
      radar: null,
    })
  }

  const runComparison = async () => {
    const readySlots = compareSlots.filter(slot => slot.player && slot.temporada)
    if (readySlots.length < 2) return

    setComparisonLoading(true)
    try {
      const updatedSlots = await Promise.all(
        compareSlots.map(async (slot) => {
          if (!slot.player || !slot.temporada) {
            return { ...slot, data: null, radar: null }
          }

          const [comparisonData, radarData] = await Promise.all([
            fetchComparacionData(slot.player.jugador_id, slot.temporada),
            fetchComparacionRadar(slot.player.jugador_id, slot.temporada),
          ])

          return {
            ...slot,
            data: comparisonData,
            radar: radarData,
          }
        })
      )

      setCompareSlots(updatedSlots)
    } finally {
      setComparisonLoading(false)
    }
  }

  useEffect(() => {
    return () => {
      Object.values(compareSearchTimerRef.current).forEach(timerId => clearTimeout(timerId))
    }
  }, [])

  const comparisonReadyCount = useMemo(
    () => compareSlots.filter(slot => slot.player && slot.temporada).length,
    [compareSlots]
  )

  const activeComparisonSlots = useMemo(
    () => compareSlots.map((slot, idx) => ({ slot, idx })).filter(({ slot }) => slot.player && slot.data),
    [compareSlots]
  )

  const activeRadarSlots = useMemo(
    () => compareSlots.map((slot, idx) => ({ slot, idx })).filter(({ slot }) => slot.player && slot.radar),
    [compareSlots]
  )

  const comparisonRadarData = useMemo(() => {
    if (activeRadarSlots.length === 0) return []

    const labels = activeRadarSlots[0]?.slot?.radar?.labels || []
    return labels.map((label, radarIdx) => {
      const row = { metric: label }
      activeRadarSlots.forEach(({ slot, idx }) => {
        row[`player_${idx}`] = slot.radar?.radar_values?.[radarIdx] ?? 0
      })
      return row
    })
  }, [activeRadarSlots])

  const comparisonCardMinWidth = useMemo(
    () => getCompareCardMinWidth(compareSlots.length),
    [compareSlots.length]
  )

  const comparisonEntries = useMemo(
    () => activeComparisonSlots.map(({ slot, idx }) => {
      const playerName = `${slot.player?.nombre || ''} ${slot.player?.apellido || ''}`.trim()
      const stats = normalizeComparisonStats(slot.data)
      return {
        id: `${slot.player?.jugador_id || idx}-${slot.temporada || 'temp'}`,
        label: slot.temporada || 'Temporada',
        subLabel: playerName,
        minutes: stats.minutos,
        stats,
      }
    }),
    [activeComparisonSlots]
  )

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
                onClick={() => {
                  const newTipo = tipo === opt.key ? null : opt.key
                  setTipo(newTipo)
                  setSortBy(newTipo)
                  setSortOrder('desc')
                }}
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

      {/* Modal de Comparación Dinámica */}
      {compareModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center" onClick={() => setCompareModalOpen(false)}>
          <div className="bg-surface-dark rounded-2xl p-8 max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto glass-panel" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-6">
              <div>
                <h3 className="text-2xl font-black text-white uppercase tracking-wider">
                  Comparar <span className="text-primary">Jugadores</span>
                </h3>
                <p className="text-xs text-gray-400 mt-1">Radar superpuesto y comparación por dominio</p>
              </div>
              <button
                onClick={() => {
                  setCompareModalOpen(false)
                  resetComparison()
                }}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <span className="material-symbols-outlined icon-2xl">close</span>
              </button>
            </div>

            <div className="space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-gray-300">
                  Jugadores listos para comparar: <span className="font-black text-white">{comparisonReadyCount}</span>
                </p>
                <button
                  onClick={addCompareSlot}
                  disabled={compareSlots.length >= MAX_COMPARE_PLAYERS}
                  className="px-4 py-2 rounded-lg bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed text-black font-bold transition-all flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-sm">person_add</span>
                  Añadir jugador
                </button>
              </div>

              <div
                className="grid gap-4"
                style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${comparisonCardMinWidth}px, 1fr))` }}
              >
                {compareSlots.map((slot, slotIdx) => (
                  <div key={`${slotIdx}-${slot.player?.jugador_id || 'empty'}`} className="border border-border-dark rounded-xl p-4 bg-white/5 flex flex-col gap-3">
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="text-xs font-black text-gray-400 uppercase tracking-wider">Jugador {slotIdx + 1}</h4>
                      {compareSlots.length > 2 && (
                        <button
                          onClick={() => removeCompareSlot(slotIdx)}
                          className="text-xs text-red-300 hover:text-red-200"
                        >
                          Quitar
                        </button>
                      )}
                    </div>

                    {!slot.player ? (
                      <>
                        <input
                          type="text"
                          placeholder="Buscar jugador..."
                          value={slot.search}
                          onChange={(e) => handleCompareSearch(slotIdx, e.target.value)}
                          className="w-full px-3 py-2 bg-background-dark border border-border-dark text-white rounded-lg focus:outline-none focus:border-primary text-xs"
                        />

                        <div className="max-h-44 overflow-y-auto border border-border-dark rounded-lg bg-black/30 divide-y divide-border-dark">
                          {slot.searchLoading && (
                            <p className="p-3 text-xs text-gray-400">Buscando jugadores...</p>
                          )}

                          {!slot.searchLoading && slot.search.trim().length >= 2 && slot.searchResults.length === 0 && (
                            <p className="p-3 text-xs text-gray-500">Sin resultados</p>
                          )}

                          {!slot.searchLoading && slot.searchResults.map(result => (
                            <button
                              key={`${slotIdx}-${result.jugador_id}`}
                              onClick={() => handleSelectComparePlayer(slotIdx, result)}
                              className="w-full text-left p-2 hover:bg-white/10 transition-colors"
                            >
                              <p className="font-bold text-white text-xs truncate">{result.nombreCompleto}</p>
                              <p className="text-xs text-gray-400">{result.posicion || 'Jugador'}</p>
                            </button>
                          ))}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="bg-primary/20 border border-primary rounded-lg p-3">
                          {slot.player.equipo_escudo && (
                            <TeamShield escudo={slot.player.equipo_escudo} nombre={slot.player.equipo} className="w-6 h-6 mb-2" />
                          )}
                          <p className="font-bold text-white text-xs truncate">
                            {slot.player.nombre} {slot.player.apellido}
                          </p>
                          <p className="text-xs text-gray-400 truncate">{slot.player.equipo}</p>
                          <button
                            onClick={() => clearComparePlayer(slotIdx)}
                            className="text-primary hover:text-white text-xs mt-2 font-bold"
                          >
                            Cambiar jugador
                          </button>
                        </div>

                        <div>
                          <label className="block text-xs font-bold text-gray-300 mb-1">Temporada</label>
                          <select
                            value={slot.temporada}
                            onChange={(e) => handleCompareSeasonChange(slotIdx, e.target.value)}
                            className="w-full px-2 py-1 bg-black border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none text-xs"
                          >
                            <option value="">Elige temporada</option>
                            <option value="carrera">Últimas 3 temporadas</option>
                            {slot.availableSeasons.map(temp => (
                              <option key={`${slotIdx}-${temp.nombre}`} value={temp.display}>{temp.display}</option>
                            ))}
                          </select>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-bold text-gray-300 mb-2">Dominio</label>
                  <select
                    value={comparisonDomain}
                    onChange={(e) => setComparisonDomain(e.target.value)}
                    className="w-full px-3 py-2 bg-black border border-border-dark/50 rounded-lg text-white focus:border-primary focus:outline-none"
                  >
                    {COMPARISON_DOMAINS.map(dom => (
                      <option key={dom.key} value={dom.key}>{dom.label}</option>
                    ))}
                  </select>
                </div>

                <div className="flex items-end">
                  <button
                    onClick={runComparison}
                    disabled={comparisonLoading || comparisonReadyCount < 2}
                    className="w-full px-4 py-3 bg-primary hover:bg-primary/80 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-lg transition-colors uppercase"
                  >
                    {comparisonLoading ? 'Cargando...' : 'Ejecutar comparación'}
                  </button>
                </div>
              </div>

              {activeRadarSlots.length >= 2 ? (
                <div className="rounded-xl border border-border-dark bg-black/20 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                    <h4 className="text-sm font-black uppercase text-white">Radar superpuesto</h4>
                    <p className="text-xs text-gray-400">Perfil táctico (percentiles 0-100)</p>
                  </div>

                  <div className="h-[360px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart data={comparisonRadarData}>
                        <PolarGrid stroke="rgba(255,255,255,0.15)" />
                        <PolarAngleAxis dataKey="metric" tick={{ fill: '#d1d5db', fontSize: 11 }} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#9ca3af', fontSize: 10 }} />
                        {activeRadarSlots.map(({ slot, idx }) => {
                          const color = COMPARE_COLORS[idx % COMPARE_COLORS.length]
                          return (
                            <Radar
                              key={`radar-${slot.player.jugador_id}-${idx}`}
                              name={`${slot.player.nombre} ${slot.player.apellido}`.trim()}
                              dataKey={`player_${idx}`}
                              stroke={color}
                              fill={color}
                              fillOpacity={0.18}
                              strokeWidth={2}
                            />
                          )
                        })}
                        <RechartsTooltip
                          formatter={(value) => `${Number(value || 0).toFixed(1)}%`}
                          contentStyle={{
                            backgroundColor: '#111827',
                            border: '1px solid #374151',
                            color: '#f9fafb',
                          }}
                        />
                        <Legend wrapperStyle={{ color: '#d1d5db', fontSize: 12 }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-border-dark bg-black/20 p-4 text-center text-sm text-gray-400">
                  El radar comparativo aparece cuando cargas al menos 2 jugadores con temporada.
                </div>
              )}

              <ComparisonMetricsCards
                entries={comparisonEntries}
                domain={comparisonDomain}
                emptyMessage={'Selecciona al menos 2 jugadores y pulsa "Ejecutar comparacion"'}
              />
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

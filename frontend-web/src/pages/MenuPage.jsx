import { useEffect, useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import apiClient from '../services/apiClient'
import { useAuth } from '../context/AuthContext'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'
import HelpButton from '../components/ui/HelpButton'
import { Riple } from 'react-loading-indicators'
import { useTour } from '../context/TourContext'
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'

const BACKEND = 'http://localhost:8000'

// ─── Mapa de explicaciones de features XAI ─────────────────────────────────
const FEATURE_EXPLICACIONES = {
  // ── Forma y puntuación ───────────────────────────────────────────────
  num_roles:                  { positiva: 'Jugador versátil. Ha ocupado muchos roles distintos esta temporada.',         negativa: 'Rol limitado. Juega casi siempre en la misma posición sin variación.' },
  num_roles_criticos:         { positiva: 'Roles clave. Ocupa posiciones decisivas en el esquema del equipo.',            negativa: 'Sin rol protagonista. No suele ocupar posiciones decisivas.' },
  pf_roll5:                   { positiva: 'Buena racha. Lleva 5 partidos puntuando por encima de su media.',               negativa: 'Mala racha. Ha bajado el rendimiento en los últimos 5 partidos.' },
  pf_ewma5:                   { positiva: 'Tendencia ascendente. Su puntuación mejora semana a semana.',                   negativa: 'Tendencia bajista. Su puntuación cae en las últimas jornadas.' },
  // ── Portero ──────────────────────────────────────────────────────────
  psxg_ewma5:                 { positiva: 'Portero sólido. Para más de lo que se espera estadísticamente.',                negativa: 'Portero con dificultades. Encaja más de lo que el xG predice.' },
  psxg_roll5:                 { positiva: 'Racha de grandes paradas. Ha superado el xG en los últimos 5 partidos.',        negativa: 'Racha floja bajo palos. Ha encajado más de lo esperado en los últimos 5 partidos.' },
  save_advantage:             { positiva: 'Por encima del xG. Realiza paradas que el modelo no predice.',                  negativa: 'Por debajo del xG. Encaja más goles de los que el modelo esperaría.' },
  // ── Ataque / remates ─────────────────────────────────────────────────
  shots_ewma5:                { positiva: 'Muy disparador. Genera muchos remates y pone en aprietos al rival.',           negativa: 'Poco rematador. No genera suficientes disparos a puerta.' },
  xg_ewma5:                   { positiva: 'Muchas ocasiones claras. Recibe balones en posición de gol con frecuencia.',    negativa: 'Pocas oportunidades claras. No llega habitualmente al área con peligro.' },
  goals_ewma5:                { positiva: 'Tendencia goleadora al alza. Está marcando con más frecuencia semana a semana.',negativa: 'Tendencia goleadora a la baja. Marca cada vez menos goles.' },
  shots_on_target_ewma5:      { positiva: 'Tendencia de disparos a puerta al alza. Cada vez más preciso y peligroso.',    negativa: 'Tendencia de disparos a puerta a la baja. Pierde precisión en el remate.' },
  // ── Conducción y regates ─────────────────────────────────────────────
  succ_dribbles_roll5:        { positiva: 'Regates completados. Ha superado con éxito a rivales en los últimos 5 partidos.', negativa: 'Pocos regates completados. No logra superar rivales en conducción últimamente.' },
  dribble_attempts_roll5:     { positiva: 'Muy intentador en regate. Busca superar rivales con mucha frecuencia.',         negativa: 'Pocos intentos de regate. No busca superar rivales ni avanzar con el balón.' },
  prog_dribbles_roll5:        { positiva: 'Conducciones progresivas. Avanza con el balón haciendo daño hacia el área rival.', negativa: 'Pocas conducciones progresivas. No lleva el balón hacia zonas de peligro.' },
  progressive_pressure:       { positiva: 'Gran avance con balón. Conduce y progresa metros con el esférico.',             negativa: 'Poca conducción en progresión. No avanza con el balón hacia la portería.' },
  prog_dist_ewma5:            { positiva: 'Gran movilidad ofensiva. Recorre muchos metros en zona de progresión.',         negativa: 'Poca movilidad progresiva. No avanza mucho en zona de creación.' },
  distance_per_dribble:       { positiva: 'Regateador efectivo. Avanza mucho terreno por regate completado.',              negativa: 'Regates poco productivos. Avanza poco terreno por cada regate.' },
  // ── Pases ────────────────────────────────────────────────────────────
  pass_comp_pct_ewma5:        { positiva: 'Pases precisos. Tiene una tasa de acierto alta en la distribución reciente.',   negativa: 'Impreciso en el pase. Ha fallado muchos pases en las últimas jornadas.' },
  pass_comp_pct_roll5:        { positiva: 'Sólido en el juego de pase. Muy fiable con el balón en los últimos 5 partidos.', negativa: 'Bajo porcentaje de pases completados en los últimos 5 partidos.' },
  passes_ewma5:               { positiva: 'Tendencia de pases al alza. Cada vez más implicado en la circulación del juego.', negativa: 'Tendencia de pases a la baja. Pierde protagonismo en la distribución.' },
  pass_productivity:          { positiva: 'Alta productividad en pases. Muchos pases completados con gran precisión.',      negativa: 'Baja productividad en pases. Poco volumen o poca precisión de pase.' },
  // ── Defensa ──────────────────────────────────────────────────────────
  def_actions_ewma5:          { positiva: 'Muy activo defensivamente. Realiza entradas, despejes e intercepciones.',       negativa: 'Poca acción defensiva. No registra acciones de recuperación recientemente.' },
  tackles_ewma5:              { positiva: 'Tendencia de entradas al alza. Cada vez más activo en la recuperación defensiva.', negativa: 'Tendencia de entradas a la baja. Menos actividad defensiva en las últimas jornadas.' },
  intercepts_ewma5:           { positiva: 'Tendencia de interceptaciones al alza. Mejora su lectura defensiva semana a semana.', negativa: 'Tendencia de interceptaciones a la baja. Pierde lecturas defensivas.' },
  defensive_intensity:        { positiva: 'Alta intensidad defensiva. Mucha presión, duelos y recuperaciones de balón.',    negativa: 'Baja intensidad defensiva. Poca presión ni acciones de recuperación.' },
  // ── Rival y contexto ─────────────────────────────────────────────────
  opp_gc_ewma5:               { positiva: 'Rival con fuga defensiva. El equipo contrario encaja muchos goles últimamente.', negativa: 'Rival sólido atrás. El equipo contrario ha encajado poco recientemente.' },
  opp_form_ewma5:             { positiva: 'Rival en mal momento. Ha perdido varios puntos en sus últimas jornadas.',       negativa: 'Rival en buena forma. Ha sumado muchos puntos últimamente.' },
  odds_prob_loss:             { positiva: 'Favorito según las casas. Las apuestas le dan pocas opciones al rival.',        negativa: 'Probable derrota. Las cuotas le dan posibilidades bajas de ganar.' },
  odds_expected_goals_against:{ positiva: 'Pocas llegadas esperadas del rival. El equipo defenderá bien según las cuotas.', negativa: 'Muchas llegadas esperadas del rival. Se esperan oportunidades en contra.' },
  is_home:                    { positiva: 'Juega en casa. El factor local suele ayudar al rendimiento.',                   negativa: 'Juega fuera. Actuar de visitante penaliza estadísticamente.' },
  // ── Disponibilidad y minutos ─────────────────────────────────────────
  minutes_pct_ewma5:          { positiva: 'Minutos elevados. Ha jugado muchos minutos en sus últimos partidos.',           negativa: 'Pocos minutos recientes. Ha tenido poco protagonismo en las últimas jornadas.' },
  minutes_pct_roll5:          { positiva: 'Continuidad de juego. Ha completado la mayoría de los últimos 5 partidos.',     negativa: 'Intermitente. No ha jugado completo con regularidad en los últimos 5 partidos.' },
  starter_pct_roll3:          { positiva: 'Titular asegurado. Ha salido de inicio en los últimos 3 partidos.',             negativa: 'Sin sitio en el once. Ha sido suplente en varios de los últimos 3 partidos.' },
  availability_momentum:      { positiva: 'Disponibilidad al alza. Ha estado apto y sin lesiones en las últimas semanas.',  negativa: 'Historial de ausencias. Ha perdido partidos por lesión o sanción recientemente.' },
  // ── Features avanzados / índices ─────────────────────────────────────
  creativity_index:           { positiva: 'Alto índice de creatividad. Combina pases precisos y regates para crear juego.', negativa: 'Bajo índice de creatividad. Escasa inventiva y poca generación de ocasiones.' },
  availability_threat:        { positiva: 'Disponible y peligroso. Sin lesiones y generando ocasiones de gol.',            negativa: 'Dudas de disponibilidad o con poca peligrosidad ofensiva.' },
  goal_productivity:          { positiva: 'Alta productividad goleadora. Combina tiros, xG y precisión de forma eficiente.', negativa: 'Baja productividad goleadora. No convierte ni genera suficiente peligro de gol.' },
  es_mediocampista_elite:     { positiva: 'Mediocampista de élite. Sus métricas de pase y control están al máximo nivel.',  negativa: 'Por debajo del nivel élite en el mediocampo. Métricas por debajo de la media.' },
  tiene_rol_mediocampista_core:{ positiva: 'Mediocentro titular. Ocupa el rol central del mediocampo con continuidad.',    negativa: 'Fuera del centro del juego. No ocupa el eje del mediocampo habitualmente.' },
}

function getFeatureExpl(f, isPositive) {
  // 1. Exact match
  const mapa = FEATURE_EXPLICACIONES[f.feature]
  if (mapa) return isPositive ? mapa.positiva : mapa.negativa

  // 2. Prefix match: strip _roll5/_ewma5/_roll3/_ewma3 suffix and find any key sharing same base
  const base = f.feature.replace(/_(roll|ewma)\d+$/, '')
  if (base !== f.feature) {
    const altKey = Object.keys(FEATURE_EXPLICACIONES).find(k => {
      const kb = k.replace(/_(roll|ewma)\d+$/, '')
      return kb !== k && kb === base
    })
    if (altKey) {
      const mapaAlt = FEATURE_EXPLICACIONES[altKey]
      return isPositive ? mapaAlt.positiva : mapaAlt.negativa
    }
  }

  // 3. Backend fallback (if not a generic "Factor: xxx" text)
  const backendText = isPositive ? f.explicacion_positiva : f.explicacion_negativa
  if (backendText && !backendText.startsWith('Factor:')) return backendText
  return f.explicacion && !f.explicacion.startsWith('Factor:') ? f.explicacion : f.feature
}

function formatTime(hora) {
  if (!hora) return 'Por definir'
  return hora.slice(0, 5)
}
function formatDate(fecha) {
  if (!fecha) return ''
  const [y, m, d] = fecha.split('-')
  return `${d}/${m}`
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
  'Real Oviedo': 'oviedo',
}
const obtenerEscudo = (nombre) => ESCUDO_MAP[nombre] || (nombre?.toLowerCase().replace(/\s+/g, '_')) || null

function EscudoImg({ nombre, size = 28 }) {
  const s = obtenerEscudo(nombre)
  if (!s) return <span className="text-gray-400 text-xs font-bold">{(nombre || '?')[0]}</span>
  return (
    <img
      src={`/static/escudos/${s}.png`}
      alt={nombre}
      style={{ width: size, height: size }}
      className="object-contain rounded"
      onError={e => { e.target.style.display = 'none' }}
    />
  )
}

export default function MenuPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { tourActive, isPhaseCompleted, markPhaseCompleted, openSidebarRef, setTourJugadorId, endTour, isManualExit } = useTour()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [jornada, setJornada] = useState(null)
  const [jugadoresDestacados, setJugadoresDestacados] = useState(null)
  const [loadingJugadores, setLoadingJugadores] = useState(true)
  const driverRef = useRef(null)

  // Estado para el modal de predicción
  const [modalDet, setModalDet] = useState(null)   // jugador object
  const [detLoadingPred, setDetLoadingPred] = useState(false)
  const [detPrediccion, setDetPrediccion] = useState(null)
  const [detFeaturesImpacto, setDetFeaturesImpacto] = useState([])
  const [detExplicacion, setDetExplicacion] = useState(null)

  const loadMenuData = (jornadaNum) => {
    setLoading(true)
    const url = jornadaNum ? `/api/menu/?jornada=${jornadaNum}` : '/api/menu/'
    apiClient.get(url)
      .then(({ data }) => setData(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const loadJugadoresDestacados = (jornadaNum) => {
    // La próxima jornada es jornadaNum + 1
    const proxima = jornadaNum ? jornadaNum + 1 : null
    if (!proxima) {
      setLoadingJugadores(false)
      return
    }
    setLoadingJugadores(true)
    setJugadoresDestacados(null)
    apiClient.get(`/api/menu/top-jugadores/?jornada=${proxima}`)
      .then(({ data }) => setJugadoresDestacados(data.jugadores_destacados_por_posicion || {}))
      .catch(() => setJugadoresDestacados({}))
      .finally(() => setLoadingJugadores(false))
  }

  useEffect(() => {
    // Cargar jornada inicial del localStorage
    const saved = localStorage.getItem('jornada_global')
    const jornadaInicial = saved ? parseInt(saved) : null
    setJornada(jornadaInicial)
    loadMenuData(jornadaInicial)
    loadJugadoresDestacados(jornadaInicial)
  }, [])

  // Escuchar cambios de jornada desde el sidebar
  useEffect(() => {
    const handleJornadaChange = (e) => {
      const newJornada = e.detail.jornada
      setJornada(newJornada)
      loadMenuData(newJornada)
      loadJugadoresDestacados(newJornada)
    }
    
    window.addEventListener('jornadaChanged', handleJornadaChange)
    return () => window.removeEventListener('jornadaChanged', handleJornadaChange)
  }, [])

  // Save first jugador ID so ClasificacionPage tour can navigate to it
  useEffect(() => {
    if (!tourActive || !jugadoresDestacados) return
    const posKeys = Object.keys(jugadoresDestacados)
    if (posKeys.length > 0) {
      const first = jugadoresDestacados[posKeys[0]]?.[0]
      if (first?.id) setTourJugadorId(first.id)
    }
  }, [jugadoresDestacados, tourActive])

  // Run tour phase for this page
  useEffect(() => {
    if (!tourActive || isPhaseCompleted('menu') || loading) return
    const timer = setTimeout(() => {
      driverRef.current = driver({
        showProgress: true,
        allowClose: true,
        nextBtnText: 'Siguiente →',
        prevBtnText: '← Anterior',
        doneBtnText: 'Salir del tour',
        steps: [
          {
            element: '#tour-menu-welcome',
            popover: {
              title: 'Panel principal',
              description: 'Aquí tienes un resumen de todo lo importante: clasificación, próximos partidos y predicciones de jugadores generadas por IA.',
              side: 'bottom',
              align: 'start',
            },
          },
          {
            element: '#tour-menu-clasificacion',
            popover: {
              title: 'Clasificación Top 5',
              description: 'Los 5 mejores equipos de LaLiga actualizado jornada a jornada. Pulsa «Ver clasificación completa» para la tabla entera.',
              side: 'right',
              align: 'start',
            },
          },
          {
            element: '#tour-menu-proxima-jornada',
            popover: {
              title: 'Próxima jornada',
              description: 'Los partidos que se jugarán en la próxima jornada con fechas y horarios actualizados.',
              side: 'right',
              align: 'start',
            },
          },
          {
            element: '#tour-menu-favoritos-partidos',
            popover: {
              title: 'Tus equipos favoritos',
              description: 'Los partidos de los equipos que marcaste como favoritos para seguirlos de cerca sin buscarlos.',
              side: 'left',
              align: 'start',
            },
          },
          {
            element: '#tour-menu-destacados',
            popover: {
              title: 'Jugadores destacados por IA',
              description: 'Los jugadores con mayor puntuación predicha para la próxima jornada, calculada por nuestros modelos de Machine Learning. ¡Ideal para elegir tu equipo fantasy!',
              side: 'left',
              align: 'start',
            },
          },
        ],
        onDestroyStarted: () => {
          driverRef.current?.destroy()
          markPhaseCompleted('menu')
          if (isManualExit()) {
            endTour()
          } else {
            endTour()
            openSidebarRef.current?.()
            navigate('/mi-plantilla')
          }
        },
      })
      driverRef.current.drive()
    }, 600)
    return () => {
      clearTimeout(timer)
      driverRef.current?.destroy()
    }
  }, [tourActive, loading])

  // Función para abrir el modal de predicción de un jugador
  const abrirModalPrediccion = async (jugador, posicionUI = null) => {
    setModalDet(jugador)
    setDetPrediccion(null)
    setDetFeaturesImpacto([])
    setDetExplicacion(null)
    setDetLoadingPred(true)

    try {
      // Mapeo posiciones: españolas → códigos backend
      const mapPosicionesBknd = {
        'Portero': 'PT',
        'Defensa': 'DF',
        'Centrocampista': 'MC',
        'Delantero': 'DT'
      }
      
      // Mapeo de modelos disponibles por posición (igual a MiPlantillaPage)
      const modelosPorPos = {
        'PT': 'Random Forest',
        'DF': 'Random Forest',
        'MC': 'Ridge',
        'DT': 'Ridge'
      }
      
      const mapModeloBackend = {
        'Random Forest': 'RF',
        'Ridge': 'Ridge',
        'ElasticNet': 'ElasticNet',
        'Baseline': 'Baseline'
      }
      
      // Usar jornada correcta del servidor (próxima para predicción)
      const jornadaParaPred = data?.proxima_jornada?.numero || data?.jornada_actual?.numero || null
      
      // Convertir posición UI a código backend
      const posicionBackend = mapPosicionesBknd[posicionUI] || mapPosicionesBknd[jugador.posicion] || 'DT'
      
      // Determinar modelo según posición
      const modeloUI = modelosPorPos[posicionBackend] || 'Random Forest'
      const modeloBackend = mapModeloBackend[modeloUI] || 'RF'
      
      // Payload igual a MiPlantillaPage
      const payload = { 
        jugador_id: jugador.id, 
        jornada: jornadaParaPred, 
        posicion: posicionBackend,
        modelo: modeloBackend
      }
      
      console.log('Enviando predicción:', payload)
      const response = await apiClient.post(`/api/explicar-prediccion/`, payload)
      const respData = response.data || {}
      console.log('Response from explicar-prediccion:', respData)

      // Buscar status success como MiPlantillaPage
      if (respData.status === 'success') {
        // Predicción válida
        if (respData.prediccion != null) {
          setDetPrediccion({
            value: respData.prediccion,
            type: respData.type || 'prediccion',
            modelo: respData.modelo || modeloBackend
          })
          console.log('Setting detPrediccion:', { value: respData.prediccion, tipo: respData.type, modelo: respData.modelo })
        }
        
        // Features de impacto (es features_impacto, no explicacion)
        if (Array.isArray(respData.features_impacto)) {
          console.log('Features de impacto:', respData.features_impacto)
          setDetFeaturesImpacto(respData.features_impacto)
        }
        
        // Explicación general
        if (respData.explicacion_texto) {
          setDetExplicacion(respData.explicacion_texto)
        }
      } else if (respData.prediccion != null) {
        // Fallback si no viene status pero sí predicción
        setDetPrediccion({
          value: respData.prediccion,
          type: respData.type || 'prediccion',
          modelo: respData.modelo || modeloBackend
        })
        if (Array.isArray(respData.features_impacto)) {
          setDetFeaturesImpacto(respData.features_impacto)
        }
      }
    } catch (error) {
      console.error('Error al cargar predicción:', error)
    } finally {
      setDetLoadingPred(false)
    }
  }

  if (loading && !data) return <LoadingSpinner />

  const { clasificacion_top = [], jornada_actual, proxima_jornada, partidos_proxima_jornada = [], partidos_favoritos = [] } = data || {}

  const POSICIONES_GRID = [['Portero', 'Defensa'], ['Centrocampista', 'Delantero']]

  return (
    <div className="p-6 space-y-6 bg-background-dark min-h-full">
      {/* Header */}
      <div id="tour-menu-welcome" className="mb-8">
        <h2 className="text-3xl font-black text-white mb-2">¡Bienvenido de vuelta!</h2>
        <p className="text-gray-400 text-lg">Gestiona tu equipo y sigue la liga</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 max-w-screen-2xl mx-auto">
        {/* Left column */}
        <div className="xl:col-span-4 space-y-6">

          {/* Clasificación top 5 */}
          <GlassPanel id="tour-menu-clasificacion" className="overflow-hidden">
            <div className="p-6 border-b border-white/10">
              <div className="flex items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-2">
                  <img src={`${BACKEND}/static/logos/laliga.png`} alt="LaLiga" className="h-8 object-contain" onError={(e) => { e.currentTarget.style.display = 'none' }} />
                  <span className="text-sm font-bold text-white">LaLiga</span>
                </div>
                {jornada_actual && <span className="text-xs text-gray-500 font-bold uppercase tracking-widest">J{jornada_actual.numero}</span>}
              </div>
              <h3 className="text-xl font-black text-white">Clasificación</h3>
            </div>

            <table className="w-full">
              <thead>
                <tr className="text-left border-b border-white/10">
                  <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-gray-500">#</th>
                  <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-gray-500">Equipo</th>
                  <th className="px-6 py-4 text-xs font-bold uppercase tracking-widest text-gray-500 text-center">Pts</th>
                </tr>
              </thead>
              <tbody>
                {clasificacion_top.length > 0 ? clasificacion_top.map((reg) => (
                  <tr key={reg.posicion} className="hover:bg-white/5 border-b border-white/5 group transition-colors">
                    <td className="px-6 py-4 text-sm font-bold text-primary">{reg.posicion}</td>
                    <td className="px-6 py-4">
                      <Link to={`/equipo/${encodeURIComponent(reg.equipo)}`} className="flex items-center gap-3 hover:text-primary transition-colors">
                        <TeamShield escudo={reg.equipo_escudo} nombre={reg.equipo} className="size-8 rounded-lg object-contain" />
                        <p className="font-bold text-white text-sm">{reg.equipo}</p>
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className={`px-3 py-1.5 rounded-lg text-sm font-bold ${reg.posicion === 1 ? 'bg-primary/20 text-primary' : 'bg-white/20 text-white'}`}>
                        {reg.puntos}
                      </span>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan="3" className="px-6 py-8 text-center text-gray-500">Sin datos</td></tr>
                )}
              </tbody>
            </table>

            <div className="p-4 border-t border-white/10">
              <Link to="/clasificacion" className="flex items-center justify-center gap-2 text-primary hover:text-primary-dark transition-colors font-bold text-sm">
                Ver clasificación completa
                <span className="material-symbols-outlined text-sm">arrow_forward</span>
              </Link>
            </div>
          </GlassPanel>

          {/* Próximos partidos */}
          <GlassPanel id="tour-menu-proxima-jornada" className="p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-gradient-to-r from-primary to-blue-500 rounded-xl p-3">
                <span className="material-symbols-outlined text-white text-xl font-bold">calendar_today</span>
              </div>
              <div>
                <h3 className="text-xl font-black text-white">Próximos Partidos</h3>
                <p className="text-xs text-gray-500 font-bold uppercase tracking-widest">
                  {proxima_jornada ? `Jornada ${proxima_jornada.numero}` : 'Próxima jornada'}
                </p>
              </div>
            </div>

            {partidos_proxima_jornada.length > 0 ? (
              <div className="space-y-3 max-h-96 overflow-y-auto custom-scrollbar">
                {partidos_proxima_jornada.map((p, i) => (
                  <div key={i} className="bg-surface-dark border border-border-dark rounded-xl p-4 hover:bg-white/5 hover:border-primary/50 transition-all">
                    <div className="grid items-center gap-2 grid-cols-[1fr_auto_1fr]">
                      <Link to={`/equipo/${encodeURIComponent(p.equipo_local)}`} className="flex items-center gap-2 min-w-0 hover:text-primary transition-colors">
                        <TeamShield escudo={p.equipo_local_escudo} nombre={p.equipo_local} className="size-10 object-contain flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="font-bold text-white text-xs truncate">{p.equipo_local}</p>
                          <p className="text-xs text-gray-400">Local</p>
                        </div>
                      </Link>
                      <div className="text-center flex-shrink-0 px-2">
                        <p className="text-xs text-gray-400 font-bold">VS</p>
                        <p className="text-xs text-primary font-bold">{formatTime(p.hora)}</p>
                        <p className="text-xs text-gray-500 font-bold">{formatDate(p.fecha)}</p>
                      </div>
                      <Link to={`/equipo/${encodeURIComponent(p.equipo_visitante)}`} className="flex items-center gap-2 min-w-0 flex-row-reverse hover:text-primary transition-colors justify-self-end">
                        <TeamShield escudo={p.equipo_visitante_escudo} nombre={p.equipo_visitante} className="size-10 object-contain flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="font-bold text-white text-xs truncate text-right">{p.equipo_visitante}</p>
                          <p className="text-xs text-gray-400 text-right">Visitante</p>
                        </div>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-gray-400 py-8">
                <span className="material-symbols-outlined text-4xl mb-2 block">schedule</span>
                <p>No hay partidos programados</p>
              </div>
            )}
          </GlassPanel>
        </div>

        {/* Right column */}
        <div className="xl:col-span-8 space-y-6">
          {/* Favoritos */}
          {user ? (
            partidos_favoritos.length > 0 ? (
              <GlassPanel id="tour-menu-favoritos-partidos" className="p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="bg-gradient-to-r from-primary to-green-500 rounded-xl p-3">
                    <span className="material-symbols-outlined text-white text-xl font-bold">favorite</span>
                  </div>
                  <div>
                    <h3 className="text-xl font-black text-white">Tus Equipos Favoritos</h3>
                    <p className="text-xs text-gray-500 font-bold uppercase tracking-widest">
                      {proxima_jornada ? `Próximos Partidos - Jornada ${proxima_jornada.numero}` : 'Próximos Partidos'}
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {partidos_favoritos.map((p, i) => (
                    <div key={i} className="bg-surface-dark border border-border-dark rounded-xl p-4 hover:bg-white/5 transition-all">
                      <div className="grid items-center gap-2 grid-cols-[1fr_auto_1fr]">
                        <Link to={`/equipo/${encodeURIComponent(p.equipo_local)}`} className="flex items-center gap-3 hover:text-primary transition-colors">
                          <TeamShield escudo={p.equipo_local_escudo} nombre={p.equipo_local} className="size-10 object-contain" />
                          <div>
                            <p className="font-bold text-white text-sm">{p.equipo_local}</p>
                            <p className="text-xs text-gray-400">Local</p>
                          </div>
                        </Link>
                        <div className="text-center px-2">
                          <p className="text-xs text-gray-400 font-bold">VS</p>
                          <p className="text-xs text-primary font-bold">{formatTime(p.hora)}</p>
                          <p className="text-xs text-gray-500">{formatDate(p.fecha)}</p>
                        </div>
                        <Link to={`/equipo/${encodeURIComponent(p.equipo_visitante)}`} className="flex items-center gap-3 hover:text-primary transition-colors flex-row-reverse justify-self-end">
                          <TeamShield escudo={p.equipo_visitante_escudo} nombre={p.equipo_visitante} className="size-10 object-contain" />
                          <div>
                            <p className="font-bold text-white text-sm text-right">{p.equipo_visitante}</p>
                            <p className="text-xs text-gray-400 text-right">Visitante</p>
                          </div>
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </GlassPanel>
            ) : (
              <GlassPanel className="p-6 text-center">
                <span className="material-symbols-outlined text-4xl text-gray-400 mb-2 block">favorite_border</span>
                <p className="text-gray-400 text-sm">No tienes equipos favoritos seleccionados</p>
                <Link to="/favoritos/select" className="text-primary hover:text-primary-dark transition-colors text-sm font-bold mt-2 inline-block">Selecciona tus favoritos</Link>
              </GlassPanel>
            )
          ) : (
            <GlassPanel className="p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="bg-gradient-to-r from-primary to-green-500 rounded-xl p-3">
                  <span className="material-symbols-outlined text-white text-xl font-bold">favorite</span>
                </div>
                <div>
                  <h3 className="text-xl font-black text-white">Tus Equipos Favoritos</h3>
                </div>
              </div>
              <div className="text-center">
                <p className="text-gray-400 text-sm">Inicia sesión para seleccionar y ver tus equipos favoritos</p>
                <Link to="/login" className="text-primary hover:text-primary-dark transition-colors text-sm font-bold mt-2 inline-block">Inicia sesión / Regístrate</Link>
              </div>
            </GlassPanel>
          )}

          {/* Jugadores destacados */}
          <GlassPanel id="tour-menu-destacados" className="p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-gradient-to-r from-yellow-500 to-orange-500 rounded-xl p-3">
                <span className="material-symbols-outlined text-white text-xl font-bold">trending_up</span>
              </div>
              <div>
                <h3 className="text-xl font-black text-white">Jugadores Destacados</h3>
                <p className="text-xs text-gray-500 font-bold uppercase tracking-widest">
                  {proxima_jornada ? `Predicción — J${proxima_jornada.numero}` : 'Predicción próxima jornada'}
                </p>
              </div>
            </div>

            {!user ? (
              <div className="text-center bg-surface-dark border border-border-dark rounded-2xl p-8 space-y-3">
                <span className="material-symbols-outlined text-4xl text-primary block mb-2">person_add</span>
                <p className="text-white font-bold">Inicia sesión para ver jugadores destacados</p>
                <p className="text-sm text-gray-400">Accede a tu cuenta para disfrutar de predicciones personalizadas y seguimiento de jugadores</p>
                <Link
                  to="/login"
                  className="inline-block mt-4 bg-primary hover:bg-primary-dark text-black px-6 py-2 rounded-lg font-bold uppercase tracking-wider transition-all text-sm"
                >
                  Iniciar sesión
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-6">
                {POSICIONES_GRID.flat().map((posicion) => {
                  const jugadores = jugadoresDestacados?.[posicion] || []
                  const isLoadingPos = loadingJugadores
                  return (
                    <div key={posicion}>
                      <h4 className="text-sm font-bold text-primary mb-3 uppercase">{posicion}</h4>
                      {isLoadingPos ? (
                        <div className="flex items-center justify-center h-24">
                          <Riple color="#32cd32" size="medium" text="" textColor="" />
                        </div>
                      ) : jugadores.length > 0 ? (
                        <div className="space-y-2">
                          {jugadores.map((jug) => (
                            <button
                              key={jug.id}
                              onClick={() => abrirModalPrediccion(jug, posicion)}
                              className="w-full flex items-center gap-3 p-3 bg-surface-dark border border-border-dark rounded-lg hover:bg-white/5 hover:border-primary/50 transition-all group text-left"
                            >
                              <div className="flex-shrink-0">
                                <TeamShield escudo={jug.equipo_escudo} nombre={jug.equipo} className="size-8 rounded-lg object-contain" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="font-bold text-white text-sm group-hover:text-primary transition-colors">
                                  {jug.nombre} {jug.apellido}
                                </p>
                                <p className="text-xs text-gray-500">{jug.equipo} • #{jug.dorsal}</p>
                              </div>
                              <div className="flex items-center gap-3 flex-shrink-0">
                                <div className="text-right">
                                  <p className="text-xs text-gray-400">vs</p>
                                  <p className="text-xs font-bold text-white">{jug.proximo_rival}</p>
                                </div>
                                <span className="text-sm font-bold text-primary bg-primary/20 px-2.5 py-1 rounded whitespace-nowrap">
                                  {jug.prediccion.toFixed(1)} pts
                                </span>
                              </div>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-gray-500 italic py-4 text-center">Sin datos disponibles</p>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </GlassPanel>
        </div>
      </div>

      {/* ══ MODAL: Predicción de jugador ════════════════════════════════════ */}
      {modalDet && (
        <div className="fixed inset-0 bg-black/70 z-[99999] flex items-center justify-center p-4" onClick={() => setModalDet(null)}>
          <div className="bg-surface-dark border border-border-dark rounded-2xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-black text-white truncate">{modalDet.nombre} {modalDet.apellido}</h2>
              <button onClick={() => setModalDet(null)} className="text-gray-400 hover:text-white flex-shrink-0"><span className="material-symbols-outlined">close</span></button>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Equipo</span>
                <div className="flex items-center gap-2"><EscudoImg nombre={modalDet.equipo} size={24} /><span className="text-white text-sm font-bold">{modalDet.equipo || '-'}</span></div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Próximo rival</span>
                <div className="flex items-center gap-2">
                  {modalDet.proximo_rival && <EscudoImg nombre={modalDet.proximo_rival} size={24} />}
                  <span className="text-white text-sm font-bold">{modalDet.proximo_rival || 'TBD'}</span>
                </div>
              </div>
              <div className="border-t border-border-dark pt-3">
                <p className="text-sm font-bold text-white mb-2">Predicción</p>
                {detLoadingPred ? (
                  <div className="flex items-center gap-2 text-xs text-gray-400 italic">
                    <span className="animate-spin inline-block w-3 h-3 border-2 border-yellow-400 border-t-transparent rounded-full" />
                    Analizando al jugador...
                  </div>
                ) : detPrediccion != null ? (
                  <div>
                    {detPrediccion.type === 'media' ? (
                      <div className="bg-blue-500/20 border border-blue-500/40 rounded-lg p-3 mb-3">
                        <p className="text-xs font-bold text-blue-300 mb-1">📊 MEDIA HISTÓRICA</p>
                        <div className="text-2xl font-black text-blue-400">{Number(detPrediccion.value).toFixed(2)} pts</div>
                        <p className="text-xs text-blue-200/70 mt-1">Promedio de puntos en partidos anteriores sin IA</p>
                      </div>
                    ) : (
                      <div className="bg-yellow-500/20 border border-yellow-500/40 rounded-lg p-3 mb-3">
                        <p className="text-xs font-bold text-yellow-300 mb-1">🤖 PREDICCIÓN CON IA</p>
                        <div className="text-2xl font-black text-yellow-400">{Number(detPrediccion.value).toFixed(2)} pts</div>
                        <p className="text-xs text-yellow-200/70 mt-1">Estimación basada en modelo de machine learning</p>
                      </div>
                    )}
                    {detPrediccion.modelo && (
                      <p className="text-xs text-gray-400 mb-3">Modelo: <span className="text-primary font-bold">{detPrediccion.modelo}</span></p>
                    )}
                    {detPrediccion.type !== 'media' && detFeaturesImpacto.length > 0 && (() => {
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
                                      <span className="text-white/85 text-xs leading-tight font-semibold flex-1">{getFeatureExpl(f, true)}</span>
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
                                      <span className="text-white/85 text-xs leading-tight font-semibold flex-1">{getFeatureExpl(f, false)}</span>
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
                  <span className="text-xs text-gray-500">Sin predicción disponible para esta jornada</span>
                )}
              </div>
              <div className="border-t border-border-dark pt-4">
                <Link
                  to={`/jugador/${modalDet.id}`}
                  className="w-full block text-center bg-primary hover:bg-primary-dark text-black px-4 py-2 rounded-lg font-bold text-sm transition-colors"
                >
                  Ver perfil completo
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}
      
    </div>
  )
}

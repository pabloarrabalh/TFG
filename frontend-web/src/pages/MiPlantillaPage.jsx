import { useState, useEffect, useRef } from 'react'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import HelpButton from '../components/ui/HelpButton'
import ConsejeroChat from '../components/ui/ConsejeroChat'
import apiClient from '../services/apiClient'

const BACKEND = 'http://localhost:8000'

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
  'Almería': 'almeria', 'Granada': 'granada', 'Valladolid': 'valladolid',
  'Cádiz': 'cadiz', 'Leganés': 'leganes', 'Levante': 'levante',
  'Real Oviedo': 'oviedo',
}
const obtenerEscudo = (nombre) => ESCUDO_MAP[nombre] || (nombre?.toLowerCase().replace(/\s+/g, '_')) || null

const POSICIONES = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']
const ALINEACION_VACIA = { Portero: [], Defensa: [], Centrocampista: [], Delantero: [], Suplentes: [] }

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

function getCsrfToken() {
  const match = document.cookie?.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='))
  return match ? match.split('=')[1] : ''
}

// ─── Notificaciones flotantes (cola) ───────────────────────────────────────────────
function NotificacionesStack({ items }) {
  if (!items || items.length === 0) return null
  return (
    <div className="fixed top-20 left-6 z-[999999] pointer-events-none flex flex-col gap-3 max-w-sm">
      {items.map(n => {
        const cls = n.tipo === 'success' ? 'bg-green-600' : n.tipo === 'error' ? 'bg-red-600' : n.tipo === 'warning' ? 'bg-yellow-600' : 'bg-blue-600'
        return (
          <div key={n.id} className={`px-4 py-3 rounded-xl text-white shadow-2xl font-semibold text-sm pointer-events-auto break-words ${cls}`}>
            {n.msg}
          </div>
        )
      })}
    </div>
  )
}

// ─── Escudo de equipo ───────────────────────────────────────────────────────
function EscudoImg({ nombre, size = 28 }) {
  const s = obtenerEscudo(nombre)
  if (!s) return <span className="text-gray-400 text-xs font-bold">{(nombre || '?')[0]}</span>
  return (
    <img
      src={`${BACKEND}/static/escudos/${s}.png`}
      alt={nombre}
      style={{ width: size, height: size }}
      className="object-contain rounded"
      onError={e => { e.target.style.display = 'none' }}
    />
  )
}

// ─── Tarjeta de jugador en el campo ────────────────────────────────────────
function PlayerCard({ jugador, posicion, indice, onOpen, onRemove, prediccion, onDragStart, onDragEnd, onDragOver, onDrop, isDropTarget }) {
  const badge = POS_BADGE[jugador.posicion || posicion] || POS_BADGE.Delantero
  const gradient = POS_COLOR[jugador.posicion || posicion] || POS_COLOR.Delantero

  return (
    <div
      className={`bg-gradient-to-br ${gradient} rounded-xl p-4 text-center shadow-lg cursor-grab w-[130px] h-[180px] hover:scale-105 transition-all relative select-none flex flex-col justify-between ring-2 ${isDropTarget ? 'ring-primary ring-offset-1' : 'ring-transparent'}`}
      draggable
      onDragStart={() => onDragStart({ posicion, indice, jugador })}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {/* Rival badge */}
      {jugador.proximo_rival_nombre && (
        <div className="absolute top-2 right-2 opacity-80">
          <EscudoImg nombre={jugador.proximo_rival_nombre} size={18} />
        </div>
      )}
      {/* Remove btn */}
      <button
        onMouseDown={e => { e.stopPropagation(); onRemove(jugador.id) }}
        className="absolute top-1 left-1 bg-black/40 hover:bg-red-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs z-10"
        title="Quitar"
      >×</button>
      <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center mx-auto text-white font-black text-sm">
        {`${jugador.nombre?.[0] || ''}${jugador.apellido?.[0] || ''}`.toUpperCase()}
      </div>
      <div className="flex-1 flex flex-col justify-center">
        <p className="font-bold text-white text-xs leading-tight truncate px-2">
          {jugador.nombre} {jugador.apellido || ''}
        </p>
        <span className={`inline-block px-1.5 py-0.5 rounded text-white text-xs font-bold mt-1 ${badge.bg}`}>
          {badge.text}
        </span>
      </div>
      <div className="mt-1">
        {prediccion != null ? (
          <div className="text-yellow-300 font-black text-sm">{Number(prediccion.value).toFixed(1)} pts</div>
        ) : (
          <div className="text-gray-300 font-black text-xs">—</div>
        )}
      </div>
      {jugador.pocos_minutos && (
        <div className="text-orange-300 text-xs font-bold flex items-center justify-center gap-0.5 leading-none">
          <span>⚠️</span><span>Pocos min</span>
        </div>
      )}
      <button
        onClick={e => { e.stopPropagation(); onOpen(jugador) }}
        className="text-white/60 hover:text-white text-xs font-semibold transition-colors"
      >
        Ver
      </button>
    </div>
  )
}

// ─── Slot vacío del campo ───────────────────────────────────────────────────
function EmptySlot({ posicion, indice, onAdd, isDropTarget, onDragOver, onDrop }) {
  return (
    <button
      onClick={() => onAdd(posicion, false, indice)}
      className={`w-[130px] h-[180px] rounded-xl border-2 border-dashed flex items-center justify-center text-gray-500 hover:border-primary/50 hover:text-primary/70 transition-all ${isDropTarget ? 'border-yellow-400 bg-yellow-400/10' : 'border-white/20'}`}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="flex flex-col items-center gap-1">
        <span className="material-symbols-outlined text-2xl">add</span>
      </div>
    </button>
  )
}

// ─── Tarjeta de suplente ────────────────────────────────────────────────────
function SuplenteCard({ jugador, indice, onOpen, onRemove, prediccion, onDragStart, onDragEnd, onDragOver, onDrop, isDropTarget }) {
  const badge = POS_BADGE[jugador.posicion] || POS_BADGE.Delantero
  const gradient = POS_COLOR[jugador.posicion] || POS_COLOR.Delantero
  return (
    <div
      className={`bg-gradient-to-br ${gradient} rounded-xl p-3 text-center shadow cursor-grab relative select-none hover:scale-105 transition-all ring-2 ${isDropTarget ? 'ring-primary' : 'ring-transparent'}`}
      draggable
      onDragStart={() => onDragStart({ posicion: 'Suplentes', indice, jugador })}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <button onMouseDown={e => { e.stopPropagation(); onRemove(jugador.id) }} className="absolute top-1 left-1 bg-black/40 hover:bg-red-600 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs z-10">×</button>
      <div className={`inline-block px-1.5 py-0.5 rounded text-white text-xs font-bold mb-1 ${badge.bg}`}>{badge.text}</div>
      <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center mx-auto text-white font-black text-xs mb-1">
        {`${jugador.nombre[0]}${jugador.apellido ? jugador.apellido[0] : ''}`.toUpperCase()}
      </div>
      <p className="font-bold text-white text-xs truncate leading-tight">{jugador.nombre} {jugador.apellido || ''}</p>
      {prediccion != null && <div className="text-yellow-300 font-black text-xs mt-0.5">{prediccion.type === 'media' ? 'Media' : 'Pred'}: {Number(prediccion.value).toFixed(1)}</div>}
      {jugador.pocos_minutos && (
        <div className="text-orange-300 text-xs font-bold flex items-center justify-center gap-0.5 mt-0.5 leading-none">
          <span>⚠️</span><span>Pocos min</span>
        </div>
      )}
      <button onMouseDown={e => { e.stopPropagation(); onOpen(jugador) }} className="mt-1 text-white/60 hover:text-white text-xs underline">Ver</button>
    </div>
  )
}

// ─── COMPONENTE PRINCIPAL ───────────────────────────────────────────────────
export default function MiPlantillaPage() {
  const [loading, setLoading] = useState(true)
  // Inicializa jornadaActual correctamente: jornada_global + 1
  const [jornadaActual, setJornadaActual] = useState(() => {
    const saved = parseInt(localStorage.getItem('jornada_global') || '6')
    return Math.min(saved + 1, 38)
  })
  const [jugadoresDisponibles, setJugadoresDisponibles] = useState(ALINEACION_VACIA)
  const [alineacion, setAlineacion] = useState(ALINEACION_VACIA)
  const [formacion, setFormacion] = useState('4-3-3')
  const [plantillaId, setPlantillaId] = useState(null)
  const [plantillaNombre, setPlantillaNombre] = useState('Mi Team')
  const [esPredeterminada, setEsPredeterminada] = useState(false)
  const [todasPlantillas, setTodasPlantillas] = useState([])
  const [equipos, setEquipos] = useState([])
  const [saving, setSaving] = useState(false)
  const [notifs, setNotifs] = useState([])
  const [predicciones, setPredicciones] = useState({})
  const [showFormDropdown, setShowFormDropdown] = useState(false)
  const [showPosFiltroDropdown, setShowPosFiltroDropdown] = useState(false)
  const [showEquipoFilterDropdown, setShowEquipoFilterDropdown] = useState(false)
  const [showJornadaDropdown, setShowJornadaDropdown] = useState(false)
  const [actualizandoPredicciones, setActualizandoPredicciones] = useState(false)

  // Selector de modelos por posición
  const [modelosPorPos, setModelosPorPos] = useState({
    Portero: 'Random Forest',          // Solo Random Forest
    Defensa: 'Random Forest',          // Solo Random Forest
    Centrocampista: 'Ridge', // Ridge o Baseline
    Delantero: 'Ridge',     // Ridge o ElasticNet
  })
  const [showModelDropdown, setShowModelDropdown] = useState(null) // null | posicion
  const [showModelPanel, setShowModelPanel] = useState(true) // Para expandir/contraer panel de modelos
  const [showConsejero, setShowConsejero] = useState(false) // Para mostrar/ocultar Consejero Chat

  // Modal de confirmación
  const [modalConfirm, setModalConfirm] = useState(null)  // { titulo, mensaje, onConfirm, onCancel }

  // Modales
  const [modalSel, setModalSel] = useState(null)   // { posicion, esSuplente, indice }
  const [modalRen, setModalRen] = useState(false)
  const [modalDet, setModalDet] = useState(null)   // jugador object
  const [nuevoNombre, setNuevoNombre] = useState('')

  // Filtros modal selección
  const [searchTerm, setSearchTerm] = useState('')
  const [equipoFiltro, setEquipoFiltro] = useState('')
  const [posFiltro, setPosFiltro] = useState('')
  const [jugadorPartidos, setJugadorPartidos] = useState({})  // { jugador_id: [partidos] }

  // Modal detalles: predicción
  const [detPrediccion, setDetPrediccion] = useState(null)
  const [detExplicacion, setDetExplicacion] = useState(null)
  const [detFeaturesImpacto, setDetFeaturesImpacto] = useState([])
  const [detLoadingPred, setDetLoadingPred] = useState(false)

  // Drag & drop
  const dragRef = useRef(null)
  const [dropTarget, setDropTarget] = useState(null)
  const modelosPrevRef = useRef(null)

  // ── Init ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    // Usar jornada_global + 1 para predecir la PRÓXIMA jornada, igual que el menú
    const savedJornada = parseInt(localStorage.getItem('jornada_global') || '6')
    const proximaJornada = Math.min(savedJornada + 1, 38)
    loadJornada(proximaJornada).then(() => loadPlantillas())
    modelosPrevRef.current = modelosPorPos
  }, [])

  // Cargar predicciones al cambiar alineación o jornada
  useEffect(() => {
    cargarPredicciones()
  }, [alineacion, jornadaActual, modelosPorPos])

  // Mostrar aviso cuando cambian los modelos
  useEffect(() => {
    if (modelosPrevRef.current && JSON.stringify(modelosPrevRef.current) !== JSON.stringify(modelosPorPos)) {
      setActualizandoPredicciones(true)
      setPredicciones({})
      fetchingRef.current.clear()
      predictedRef.current.clear()
      const timer = setTimeout(() => setActualizandoPredicciones(false), 3000)
      modelosPrevRef.current = modelosPorPos
      return () => clearTimeout(timer)
    }
  }, [modelosPorPos])

  // Cargar partidos cuando el modal de selección se abre
  useEffect(() => {
    if (modalSel && jugadoresModal.length > 0) {
      jugadoresModal.forEach(j => cargarPartidosJugador(j.id))
    }
  }, [modalSel])

  // Ref para evitar closure stale en el event listener
  const loadJornadaRef = useRef(null)
  loadJornadaRef.current = loadJornada

  // Escuchar cambios de jornada desde el sidebar
  useEffect(() => {
    const handleJornadaChange = (e) => {
      loadJornadaRef.current(Math.min(e.detail.jornada + 1, 38))
    }
    window.addEventListener('jornadaChanged', handleJornadaChange)
    return () => window.removeEventListener('jornadaChanged', handleJornadaChange)
  }, [])

  // ── API helpers ──────────────────────────────────────────────────────────
  async function loadJornada(jornada) {
    try {
      const res = await fetch(`${BACKEND}/api/cambiar-jornada/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        credentials: 'include',
        body: JSON.stringify({ jornada }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setJugadoresDisponibles(data.jugadores_por_posicion)
        setJornadaActual(jornada)
        setPredicciones({})
        fetchingRef.current.clear()
        predictedRef.current.clear()
        localStorage.setItem('jornadaActual', String(jornada))
        
        // Extraer equipos únicos
        const eqMap = new Map()
        Object.values(data.jugadores_por_posicion).flat().forEach(j => {
          if (j.equipo_id && !eqMap.has(j.equipo_id)) eqMap.set(j.equipo_id, j.equipo_nombre)
        })
        setEquipos([...eqMap.entries()].map(([id, nombre]) => ({ id, nombre })).sort((a, b) => a.nombre.localeCompare(b.nombre)))
        
        // Actualizar rivales de jugadores ya en alineación
        actualizarRivalesEnAlineacion(data.jugadores_por_posicion)
      } else {
        mostrarNotif(`Error al cambiar jornada: ${data.message || 'desconocido'}`, 'error')
      }
    } catch (e) {
      mostrarNotif(`Error cargando jornada: ${e.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  function actualizarRivalesEnAlineacion(jdp) {
    setAlineacion(prev => {
      const todosNuevos = Object.values(jdp).flat()
      const next = {}
      ;[...POSICIONES, 'Suplentes'].forEach(pos => {
        next[pos] = (prev[pos] || []).map(j => {
          if (!j) return null
          const fresco = todosNuevos.find(n => n.id === j.id)
          return fresco ? { ...j, proximo_rival_nombre: fresco.proximo_rival_nombre, pocos_minutos: fresco.pocos_minutos ?? j.pocos_minutos ?? false } : j
        })
      })
      return next
    })
  }

  async function loadPlantillas() {
    try {
      const res = await fetch(`${BACKEND}/mi-plantilla/listar/`, { credentials: 'include' })
      const data = await res.json()
      const ps = data.plantillas || []
      setTodasPlantillas(ps)
      if (ps.length > 0) {
        aplicarPlantilla(ps[0])
      }
    } catch (e) {
      // Error cargando plantillas
    }
  }

  function aplicarPlantilla(p) {
    setPlantillaId(p.id)
    setPlantillaNombre(p.nombre)
    setFormacion(p.formacion || '4-3-3')
    setAlineacion({ ...ALINEACION_VACIA, ...(p.alineacion || {}) })
    setEsPredeterminada(!!p.predeterminada)
  }

  function mostrarNotif(msg, tipo = 'success') {
    const id = Date.now() + Math.random()
    setNotifs(prev => [...prev, { id, msg, tipo }])
    setTimeout(() => setNotifs(prev => prev.filter(n => n.id !== id)), 4000)
  }

  // ── Jornada ──────────────────────────────────────────────────────────────
  function cambiarJornada(delta) {
    const nueva = jornadaActual + delta
    if (nueva < 1 || nueva > 38) return
    loadJornada(nueva)
  }



  // ── Alineación ───────────────────────────────────────────────────────────
  function removerJugador(jugadorId) {
    setAlineacion(prev => {
      const next = {}
      ;[...POSICIONES, 'Suplentes'].forEach(pos => {
        next[pos] = (prev[pos] || []).map(j => j?.id === jugadorId ? null : j)
      })
      return next
    })
  }

  function abrirModalSel(posicion, esSuplente, indice) {
    setSearchTerm(''); setEquipoFiltro(''); setPosFiltro('')
    setModalSel({ posicion, esSuplente, indice })
  }

  function seleccionarJugador(jugador) {
    if (!modalSel) return
    const { posicion, esSuplente, indice } = modalSel
    const targetPos = esSuplente ? 'Suplentes' : posicion
    setAlineacion(prev => {
      const arr = [...(prev[targetPos] || [])]
      while (arr.length <= indice) arr.push(null)
      arr[indice] = {
        id: jugador.id, nombre: jugador.nombre, apellido: jugador.apellido,
        posicion: jugador.posicion, equipo_id: jugador.equipo_id, equipo_nombre: jugador.equipo_nombre,
        puntos_fantasy_25_26: jugador.puntos_fantasy_25_26 || 0,
        proximo_rival_id: jugador.proximo_rival_id, proximo_rival_nombre: jugador.proximo_rival_nombre,
        pocos_minutos: jugador.pocos_minutos || false,
      }
      return { ...prev, [targetPos]: arr }
    })
    setModalSel(null)
    mostrarNotif(`${jugador.nombre} añadido`, 'success')
  }

  // ── Formación ────────────────────────────────────────────────────────────
  function cambiarFormacion(nf) {
    const cfg = FORMACIONES[nf]
    if (!cfg) return
    setFormacion(nf)
    setShowFormDropdown(false)
    setAlineacion(prev => {
      const next = { ...prev }
      const movidos = []
      ;['Defensa', 'Centrocampista', 'Delantero'].forEach(pos => {
        const arr = [...(prev[pos] || [])]
        if (arr.length > cfg[pos]) {
          movidos.push(...arr.splice(cfg[pos]).filter(Boolean))
          next[pos] = arr
        }
      })
      if (movidos.length) {
        const bench = [...(prev.Suplentes || [])]
        movidos.forEach(j => {
          const libre = bench.findIndex(s => !s)
          if (libre >= 0) bench[libre] = j
          else if (bench.length < 5) bench.push(j)
        })
        next.Suplentes = bench
        mostrarNotif(`${movidos.map(j => j.nombre).join(', ')} → banquillo`, 'info')
      }
      return next
    })
  }

  // ── Guardar / Renombrar / Eliminar ────────────────────────────────────────
  async function guardarPlantilla() {
    setSaving(true)
    try {
      const res = await fetch(`${BACKEND}/mi-plantilla/guardar/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        credentials: 'include',
        body: JSON.stringify({ plantilla_id: plantillaId, nombre: plantillaNombre, formacion, alineacion }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setPlantillaId(data.plantilla_id)
        setPlantillaNombre(data.plantilla_nombre)
        mostrarNotif(`✓ ${data.message}`, 'success')
        await loadPlantillas()
      } else {
        mostrarNotif('✗ Error guardando plantilla', 'error')
      }
    } catch {
      mostrarNotif('✗ Error de conexión', 'error')
    } finally {
      setSaving(false)
    }
  }

  async function renombrarPlantilla() {
    if (!nuevoNombre.trim()) { mostrarNotif('✗ Nombre vacío', 'error'); return }
    if (!plantillaId) {
      setPlantillaNombre(nuevoNombre.trim()); setModalRen(false)
      mostrarNotif('✓ Nombre actualizado (guarda para confirmar)', 'info')
      return
    }
    try {
      const res = await fetch(`${BACKEND}/mi-plantilla/${plantillaId}/renombrar/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        credentials: 'include',
        body: JSON.stringify({ nombre: nuevoNombre.trim() }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setPlantillaNombre(nuevoNombre.trim()); setModalRen(false)
        mostrarNotif('✓ Renombrada', 'success')
        await loadPlantillas()
      } else {
        mostrarNotif('✗ Error al renombrar', 'error')
      }
    } catch { mostrarNotif('✗ Error de conexión', 'error') }
  }

  async function eliminarPlantilla() {
    if (!plantillaId || !window.confirm(`¿Eliminar "${plantillaNombre}"?`)) return
    try {
      await fetch(`${BACKEND}/mi-plantilla/${plantillaId}/eliminar/`, {
        method: 'DELETE', headers: { 'X-CSRFToken': getCsrfToken() }, credentials: 'include',
      })
      setPlantillaId(null); setPlantillaNombre('Mi Team')
      setFormacion('4-3-3'); setAlineacion(ALINEACION_VACIA)
      mostrarNotif('✓ Plantilla eliminada', 'success')
      await loadPlantillas()
    } catch { mostrarNotif('✗ Error de conexión', 'error') }
  }

  function crearNueva() {
    setPlantillaId(null); setPlantillaNombre('Mi Team')
    setFormacion('4-3-3'); setAlineacion(ALINEACION_VACIA)
    mostrarNotif('✓ Nueva plantilla (aún no guardada)', 'info')
  }

  async function hacerPredeterminada() {
    if (!plantillaId) {
      mostrarNotif('✗ Guarda la plantilla primero', 'error')
      return
    }
    setSaving(true)
    try {
      const res = await fetch(`${BACKEND}/api/plantilla/${plantillaId}/predeterminada/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        credentials: 'include',
      })
      const data = await res.json()
      if (data.status === 'ok' || res.ok) {
        setEsPredeterminada(true)
        setTodasPlantillas(prev => prev.map(p => ({ ...p, predeterminada: p.id === plantillaId })))
        mostrarNotif('✓ Plantilla establecida como predeterminada', 'success')
      } else {
        mostrarNotif('✗ Error al establecer predeterminada', 'error')
      }
    } catch {
      mostrarNotif('✗ Error de conexión', 'error')
    } finally {
      setSaving(false)
    }
  }

  // Ref para rastrear qué jugadores ya tienen petición en vuelo
  const fetchingRef = useRef(new Set())
  const predictedRef = useRef(new Set())

  // ── Cargar partidos de jugador ───────────────────────────────────────────
  async function cargarPartidosJugador(jugadorId) {
    if (jugadorPartidos[jugadorId]) return  // Ya cargado
    try {
      const res = await fetch(`${BACKEND}/api/jugador-partidos/?jugador_id=${jugadorId}&jornada_actual=${jornadaActual}`)
      const data = await res.json()
      setJugadorPartidos(prev => ({
        ...prev,
        [jugadorId]: data.partidos || []
      }))
    } catch (e) {
      // Error cargando partidos
    }
  }

  // ── Predicciones ─────────────────────────────────────────────────────────
  async function cargarPredicciones() {
    const todos = [
      ...POSICIONES.flatMap(p => alineacion[p] || []),
      ...(alineacion.Suplentes || []),
    ].filter(Boolean)
    if (!todos.length) return
    
    // Mapeo de nombres mostrados a códigos de backend
    const mapModeloBackend = {
      'Random Forest': 'RF',
      'Ridge': 'Ridge',
      'ElasticNet': 'ElasticNet',
      'Baseline': 'Baseline',
    }
    
    for (const jug of todos) {
      if (fetchingRef.current.has(jug.id) || predictedRef.current.has(jug.id)) continue
      fetchingRef.current.add(jug.id)
      try {
        // Usar /api/explicar-prediccion/ (recalcula siempre, igual que el modal)
        // Con el modelo seleccionado para esa posición
        const modeloUI = modelosPorPos[jug.posicion] || 'Random Forest'
        const modeloBackend = mapModeloBackend[modeloUI] || 'RF'
        
        const payload = { 
          jugador_id: jug.id, 
          jornada: jornadaActual, 
          posicion: jug.posicion,
          modelo: modeloBackend
        }
        const res = await fetch(`${BACKEND}/api/explicar-prediccion/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          credentials: 'include',
          body: JSON.stringify(payload),
        })
        const data = await res.json()
        if (data.prediccion != null) {
          predictedRef.current.add(jug.id)
          setPredicciones(prev => ({ 
            ...prev, 
            [jug.id]: { value: data.prediccion, type: 'prediccion' } 
          }))
        }
      } catch (e) {
        // Error fetching prediction
      } finally {
        fetchingRef.current.delete(jug.id)
      }
    }
  }

  async function abrirDetalles(jugador) {
    setModalDet(jugador); setDetPrediccion(null); setDetExplicacion(null); setDetFeaturesImpacto([])
    setDetLoadingPred(true)
    try {
      // Mapeo de nombres mostrados a códigos de backend
      const mapModeloBackend = {
        'Random Forest': 'RF',
        'Ridge': 'Ridge',
        'ElasticNet': 'ElasticNet',
        'Baseline': 'Baseline',
      }
      // Endpoint unificado XAI para TODAS las posiciones (PT, DF, MC, DT)
      const modeloUI = modelosPorPos[jugador.posicion] || 'Random Forest'
      const modeloBackend = mapModeloBackend[modeloUI] || 'RF'
      const res = await fetch(`${BACKEND}/api/explicar-prediccion/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        credentials: 'include',
        body: JSON.stringify({ jugador_id: jugador.id, jornada: jornadaActual, posicion: jugador.posicion, modelo: modeloBackend }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setDetPrediccion({ value: data.prediccion, type: data.type || 'prediccion', modelo: data.modelo })
        setDetExplicacion(data.explicacion_texto || null)
        setDetFeaturesImpacto(Array.isArray(data.features_impacto) ? data.features_impacto : [])
      }
    } catch {}
    setDetLoadingPred(false)
  }

  // ── Drag & Drop ──────────────────────────────────────────────────────────
  function handleDragStart(info) { dragRef.current = info }
  function handleDragEnd() { setDropTarget(null); dragRef.current = null }

  function handleDragOver(e, pos, idx) {
    if (!dragRef.current) return
    e.preventDefault()
    setDropTarget({ posicion: pos, indice: idx })
  }

  function handleDrop(e, targetPos, targetIdx) {
    e.preventDefault()
    setDropTarget(null)
    const drag = dragRef.current
    dragRef.current = null
    if (!drag) return
    const { posicion: fromPos, indice: fromIdx, jugador } = drag
    if (fromPos === targetPos && fromIdx === targetIdx) return

    // Validación de movimiento
    if (fromPos === 'Suplentes' && targetPos !== jugador.posicion && targetPos !== 'Suplentes') {
      mostrarNotif(`Solo puedes mover ${jugador.nombre} a ${jugador.posicion}`, 'error'); return
    }
    if (fromPos !== 'Suplentes' && targetPos !== fromPos && targetPos !== 'Suplentes') {
      mostrarNotif('Solo puedes mover el jugador a su posición o al banquillo', 'error'); return
    }

    setAlineacion(prev => {
      const next = { ...prev }
      ;[...POSICIONES, 'Suplentes'].forEach(p => { next[p] = [...(prev[p] || [])] })
      while (next[targetPos].length <= targetIdx) next[targetPos].push(null)

      const origen = next[fromPos][fromIdx]
      const destino = next[targetPos][targetIdx]
      if (!origen) return prev

      if (destino) {
        // Swap – validar posición del jugador destino si va a una posición de campo (no al banquillo)
        if (targetPos !== 'Suplentes' && destino.posicion !== fromPos && fromPos !== 'Suplentes') {
          mostrarNotif(`${destino.nombre} no puede jugar de ${fromPos}`, 'error'); return prev
        }
        next[targetPos][targetIdx] = origen
        next[fromPos][fromIdx] = destino
        mostrarNotif(`${origen.nombre} ↔ ${destino.nombre}`, 'success')
      } else {
        next[targetPos][targetIdx] = origen
        next[fromPos][fromIdx] = null
        mostrarNotif(`${origen.nombre} movido`, 'success')
      }
      return next
    })
  }

  // ── Render línea campo ────────────────────────────────────────────────────
  const cfg = FORMACIONES[formacion]

  function renderLinea(pos) {
    const slots = cfg[pos] || 1
    return (
      <div className="flex items-center justify-center gap-3 py-1">
        {Array.from({ length: slots }, (_, i) => {
          const j = alineacion[pos]?.[i] || null
          const isDrop = dropTarget?.posicion === pos && dropTarget?.indice === i
          return j ? (
            <PlayerCard
              key={i}
              jugador={j} posicion={pos} indice={i}
              onOpen={abrirDetalles} onRemove={removerJugador}
              prediccion={predicciones[j.id]}
              onDragStart={handleDragStart} onDragEnd={handleDragEnd}
              onDragOver={e => handleDragOver(e, pos, i)}
              onDrop={e => handleDrop(e, pos, i)}
              isDropTarget={isDrop}
            />
          ) : (
            <EmptySlot
              key={i}
              posicion={pos} indice={i} onAdd={abrirModalSel}
              isDropTarget={isDrop}
              onDragOver={e => handleDragOver(e, pos, i)}
              onDrop={e => handleDrop(e, pos, i)}
            />
          )
        })}
      </div>
    )
  }

  // ── Jugadores filtrados para modal ────────────────────────────────────────
  const jugadoresModal = (() => {
    if (!modalSel) return []
    const { posicion, esSuplente } = modalSel
    const usados = new Set([...POSICIONES, 'Suplentes'].flatMap(p => alineacion[p] || []).filter(Boolean).map(j => j.id))
    const lista = esSuplente ? Object.values(jugadoresDisponibles).flat() : (jugadoresDisponibles[posicion] || [])
    return lista
      .filter(j => !usados.has(j.id))
      .filter(j => `${j.nombre} ${j.apellido}`.toLowerCase().includes(searchTerm.toLowerCase()))
      .filter(j => !equipoFiltro || j.equipo_id == equipoFiltro)
      .filter(j => !posFiltro || j.posicion === posFiltro)
      .sort((a, b) => (b.puntos_fantasy_25_26 || 0) - (a.puntos_fantasy_25_26 || 0))
  })()

  if (loading) return <div className="flex items-center justify-center min-h-screen"><LoadingSpinner size="lg" /></div>

  return (
    <div className="p-6 space-y-4 bg-background-dark min-h-full" onClick={() => setShowFormDropdown(false)}>
      <NotificacionesStack items={notifs} />

      {/* Aviso de actualización azul */}
      {actualizandoPredicciones && (
        <div className="fixed top-20 right-6 px-6 py-3 rounded-xl bg-blue-600 text-white shadow-2xl z-[999998] flex items-center gap-2 animate-pulse font-semibold">
          <span className="inline-block w-2 h-2 bg-white rounded-full animate-bounce"></span>
          <span className="text-sm">📊 Actualizando predicciones...</span>
        </div>
      )}

      {/* ── Cabecera ── */}
      <div className="glass-panel rounded-2xl p-5 relative z-[100]">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <h2 className="text-2xl font-black text-white truncate">{plantillaNombre}</h2>
            <button onClick={() => { setNuevoNombre(plantillaNombre); setModalRen(true) }} className="text-gray-400 hover:text-primary transition-colors flex-shrink-0">
              <span className="material-symbols-outlined text-lg">edit</span>
            </button>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Selector formación */}
            <div className="relative" onClick={e => e.stopPropagation()}>
              <button onClick={() => setShowFormDropdown(v => !v)} className="px-4 py-2 bg-surface-dark border border-border-dark text-white rounded-lg hover:bg-primary/10 hover:border-primary/50 transition-all text-sm font-bold flex items-center gap-2">
                <span className="material-symbols-outlined text-base text-primary">grid_view</span>
                {formacion}
                <span className="material-symbols-outlined text-xs">expand_more</span>
              </button>
              {showFormDropdown && (
                <div className="absolute top-full left-0 mt-1 bg-surface-dark border border-border-dark rounded-lg shadow-2xl z-50 min-w-28 py-1">
                  {Object.keys(FORMACIONES).map(f => (
                    <button key={f} onClick={() => cambiarFormacion(f)} className={`block w-full text-left px-4 py-2 text-sm hover:bg-primary/20 transition-colors ${f === formacion ? 'text-primary font-bold' : 'text-white'}`}>{f}</button>
                  ))}
                </div>
              )}
            </div>
            {/* Plantillas guardadas */}
            {todasPlantillas.length > 0 && (
              <select value={plantillaId || ''} onChange={e => { if (e.target.value) aplicarPlantilla(todasPlantillas.find(p => p.id === parseInt(e.target.value))) }} className="bg-surface-dark border border-border-dark text-white px-3 py-2 rounded-lg text-sm">
                {todasPlantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
            )}
            <button onClick={crearNueva} className="px-3 py-2 bg-surface-dark border border-border-dark text-white rounded-lg hover:bg-white/5 text-sm" title="Nueva plantilla">
              <span className="material-symbols-outlined text-base">add</span>
            </button>
            {plantillaId && (
              <button onClick={eliminarPlantilla} className="px-3 py-2 bg-red-600/20 border border-red-600/40 text-red-400 rounded-lg hover:bg-red-600/30 text-sm" title="Eliminar">
                <span className="material-symbols-outlined text-base">delete</span>
              </button>
            )}
            <button onClick={guardarPlantilla} disabled={saving} className="px-5 py-2 bg-primary hover:bg-primary-dark text-black rounded-lg font-bold text-sm flex items-center gap-2 transition-colors disabled:opacity-60">
              <span className="material-symbols-outlined text-base">save</span>
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
            {plantillaId && (
              <button
                onClick={hacerPredeterminada}
                disabled={saving}
                className="px-2 py-2 rounded-lg transition-colors disabled:opacity-60 hover:bg-yellow-500/10"
                title={esPredeterminada ? 'Plantilla predeterminada' : 'Hacer predeterminada'}
              >
                <span
                  className={`material-symbols-outlined text-xl transition-colors ${esPredeterminada ? 'text-yellow-400' : 'text-gray-500 hover:text-yellow-400'}`}
                  style={esPredeterminada ? { fontVariationSettings: "'FILL' 1" } : {}}
                >star</span>
              </button>
            )}

          </div>
        </div>
      </div>


      {/* ── Selector de modelos por posición ── */}
      <div className="glass-panel rounded-2xl p-4 relative z-50" onClick={e => e.stopPropagation()}>
        <button 
          onClick={() => setShowModelPanel(!showModelPanel)}
          className="w-full flex items-center justify-between mb-3 p-2 rounded-lg hover:bg-white/5 transition-colors"
        >
          <h3 className="text-sm font-black text-white flex items-center gap-2">
            <span className="material-symbols-outlined text-base text-primary">tune</span>
            Modelos por Posición
          </h3>
          <span className={`material-symbols-outlined text-primary transition-transform ${showModelPanel ? 'rotate-180' : ''}`}>expand_more</span>
        </button>
        {showModelPanel && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { pos: 'Portero', opciones: ['Random Forest'] },
            { pos: 'Defensa', opciones: ['Random Forest'] },
            { pos: 'Centrocampista', opciones: ['Ridge', 'Baseline'] },
            { pos: 'Delantero', opciones: ['Ridge', 'ElasticNet'] },
          ].map(({ pos, opciones }) => (
            <div key={pos} className="relative">
              <button 
                onClick={e => { e.stopPropagation(); setShowModelDropdown(showModelDropdown === pos ? null : pos) }}
                className={`w-full px-3 py-2 rounded-lg font-bold text-xs transition-all text-center border ${
                  showModelDropdown === pos 
                    ? 'bg-primary/20 border-primary text-primary' 
                    : 'bg-surface-dark border-border-dark text-white hover:bg-primary/10'
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="truncate">{pos}</span>
                  <span className="material-symbols-outlined text-sm">arrow_drop_down</span>
                </div>
                <div className="text-xs text-gray-300 mt-0.5">{modelosPorPos[pos]}</div>
              </button>
              {showModelDropdown === pos && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-background-dark border border-border-dark rounded-lg shadow-2xl z-[10001] py-1">
                  {opciones.map(opt => (
                    <button
                      key={opt}
                      onClick={() => {
                        // Lógica de confirmación según posición y modelo
                        if (pos === 'Centrocampista' && opt === 'Baseline') {
                          setModalConfirm({
                            titulo: 'Cambiar a Baseline',
                            mensaje: 'Se usará la media histórica de puntos del jugador en lugar de predicción con IA.',
                            onConfirm: () => {
                              setModelosPorPos(prev => ({ ...prev, [pos]: opt }))
                              setShowModelDropdown(null)
                              setModalConfirm(null)
                            },
                            onCancel: () => setModalConfirm(null)
                          })
                        } else if (pos === 'Delantero' && opt === 'ElasticNet' && modelosPorPos[pos] === 'Ridge') {
                          setModalConfirm({
                            titulo: 'Cambiar a ElasticNet',
                            mensaje: 'La predicción con ElasticNet es algo peor que Ridge (MAE más alto). ¿Aceptas el cambio?',
                            onConfirm: () => {
                              setModelosPorPos(prev => ({ ...prev, [pos]: opt }))
                              setShowModelDropdown(null)
                              setModalConfirm(null)
                            },
                            onCancel: () => setModalConfirm(null)
                          })
                        } else {
                          setModelosPorPos(prev => ({ ...prev, [pos]: opt }))
                          setShowModelDropdown(null)
                        }
                      }}
                      className={`block w-full text-left px-3 py-2 text-xs transition-colors whitespace-nowrap ${
                        modelosPorPos[pos] === opt 
                          ? 'bg-primary/30 text-primary font-bold border-l-2 border-primary' 
                          : 'text-white hover:bg-white/10'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          </div>
        )}
      </div>

      {/* ── Campo ── */}
      <div style={{ perspective: '1200px', overflow: 'visible' }}>
        <div
          className="relative rounded-3xl w-full overflow-visible py-6"
          style={{
            backgroundImage: 'radial-gradient(ellipse at center, #2d5a27 0%, #1a3d15 60%, #0f2a0c 100%)',
            minHeight: 680,
            transform: 'rotateX(8deg) scale(0.97)',
            transformStyle: 'preserve-3d',
            boxShadow: '0 40px 60px -15px rgba(0,0,0,0.7)',
          }}
        >
          {/* Líneas campo */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: 0.25 }}>
            <circle cx="50%" cy="50%" r="80" fill="none" stroke="white" strokeWidth="2" />
            <line x1="0" y1="50%" x2="100%" y2="50%" stroke="white" strokeWidth="2" />
            <rect x="20%" y="2%" width="60%" height="18%" rx="2" fill="none" stroke="white" strokeWidth="2" />
            <rect x="20%" y="80%" width="60%" height="18%" rx="2" fill="none" stroke="white" strokeWidth="2" />
            <rect x="35%" y="2%" width="30%" height="7%" fill="none" stroke="white" strokeWidth="1.5" />
            <rect x="35%" y="91%" width="30%" height="7%" fill="none" stroke="white" strokeWidth="1.5" />
          </svg>

          {/* Selector jornada - esquina superior derecha */}
          <div className="absolute top-4 right-4 z-20">
            <div className="bg-surface-dark border border-border-dark rounded-xl px-3 py-2 text-center relative">
              <p className="text-white/60 text-xs font-semibold uppercase tracking-wider mb-1">Jornada a predecir</p>
              <button
                onClick={() => setShowJornadaDropdown(!showJornadaDropdown)}
                className="text-lg font-black text-white bg-transparent border-none outline-none text-center cursor-pointer flex items-center gap-1"
              >
                <span>{jornadaActual}</span>
                <span className="material-symbols-outlined text-sm">arrow_drop_down</span>
              </button>
              {showJornadaDropdown && (
                <div className="absolute top-full right-0 mt-1 bg-blue-900 border border-blue-700 rounded-lg shadow-2xl z-30 py-1 max-h-48 overflow-y-auto w-20">
                  {Array.from({ length: 38 }, (_, i) => (
                    <button
                      key={i + 1}
                      onClick={() => { loadJornada(i + 1); setShowJornadaDropdown(false) }}
                      className={`w-full text-sm py-2 text-center transition-colors ${
                        jornadaActual === i + 1 
                          ? 'bg-blue-600 text-white font-bold' 
                          : 'text-white hover:bg-blue-700'
                      }`}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="relative z-10 flex flex-col justify-around" style={{ minHeight: 640 }}>
            {renderLinea('Delantero')}
            {renderLinea('Centrocampista')}
            {renderLinea('Defensa')}
            {renderLinea('Portero')}
          </div>

          {/* ── Total puntos previstos (top-left) ── */}
          {(() => {
            const total = POSICIONES.flatMap(p => alineacion[p] || []).filter(Boolean).reduce((sum, j) => sum + (predicciones[j.id]?.value ?? 0), 0)
            const count = POSICIONES.flatMap(p => alineacion[p] || []).filter(Boolean).length
            return (
              <div className="absolute top-4 left-4 space-y-3 z-20 pointer-events-auto">
                <div className="bg-black/50 backdrop-blur-sm border border-white/20 rounded-xl px-4 py-3 text-center">
                  <p className="text-white/60 text-xs font-semibold uppercase tracking-wider mb-0.5">Pts previstos</p>
                  <p className="text-yellow-300 font-black text-2xl leading-none">{total > 0 ? total.toFixed(1) : '—'}</p>
                  {count > 0 && <p className="text-white/40 text-xs mt-1">{count} jugadores</p>}
                </div>
                <button 
                  onClick={() => setShowConsejero(true)}
                  className="w-full px-4 py-2 bg-primary/20 hover:bg-primary/30 border border-primary/40 text-primary rounded-lg text-sm font-bold flex items-center justify-center gap-2 transition-colors"
                  title="Abrir Consejero de Plantilla"
                >
                  <span className="material-symbols-outlined text-base">lightbulb</span>
                  <span>Consejero</span>
                </button>
              </div>
            )
          })()}

          {/* ── Indicador posiciones (bottom-left) ── */}
          <div className="absolute bottom-4 left-4 bg-black/50 backdrop-blur-sm border border-white/20 rounded-xl px-4 py-3 space-y-1.5">
            {[...POSICIONES, 'Suplentes'].map(pos => {
              const slots = pos === 'Suplentes' ? 5 : (cfg[pos] || 1)
              const filled = (alineacion[pos] || []).filter(Boolean).length
              const badge = pos === 'Suplentes' ? { bg: 'bg-gray-600', text: 'SUP' } : POS_BADGE[pos]
              const dotFill = pos === 'Suplentes' ? 'bg-gray-400' : badge.bg
              return (
                <div key={pos} className="flex items-center gap-2">
                  <span className={`${badge.bg} text-white text-xs font-bold px-1.5 py-0.5 rounded w-9 text-center flex-shrink-0`}>{badge.text}</span>
                  <div className="flex gap-1">
                    {Array.from({ length: slots }, (_, i) => (
                      <div key={i} className={`w-2.5 h-2.5 rounded-full border transition-all ${ i < filled ? `${dotFill} border-transparent` : 'border-white/40 bg-transparent' }`} />
                    ))}
                  </div>
                  <span className={`text-xs font-bold ml-1 ${ filled === slots ? 'text-green-400' : filled > 0 ? 'text-yellow-400' : 'text-white/30' }`}>{filled}/{slots}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── Banquillo ── */}
      <div className="glass-panel rounded-2xl p-5">
        <h3 className="text-xl font-black text-white mb-4">Suplentes</h3>
        <div className="grid grid-cols-5 gap-3">
          {Array.from({ length: 5 }, (_, i) => {
            const j = alineacion.Suplentes?.[i] || null
            const isDrop = dropTarget?.posicion === 'Suplentes' && dropTarget?.indice === i
            return j ? (
              <SuplenteCard
                key={i} jugador={j} indice={i}
                onOpen={abrirDetalles} onRemove={removerJugador}
                prediccion={predicciones[j.id]}
                onDragStart={handleDragStart} onDragEnd={handleDragEnd}
                onDragOver={e => handleDragOver(e, 'Suplentes', i)}
                onDrop={e => handleDrop(e, 'Suplentes', i)}
                isDropTarget={isDrop}
              />
            ) : (
              <div
                key={i}
                onDragOver={e => handleDragOver(e, 'Suplentes', i)}
                onDrop={e => handleDrop(e, 'Suplentes', i)}
                className={`rounded-xl border-2 border-dashed flex flex-col items-center justify-center min-h-24 transition-all ${isDrop ? 'border-yellow-400 bg-yellow-400/10' : 'border-gray-500/50 hover:border-white/50'}`}
              >
                <button onClick={() => abrirModalSel('Suplentes', true, i)} className="w-full h-full flex flex-col items-center justify-center gap-1 p-3 text-white/40 hover:text-white transition-colors">
                  <span className="material-symbols-outlined text-2xl">person_add</span>
                  <span className="text-xs">Suplente</span>
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* ══ MODAL: Seleccionar jugador ══════════════════════════════════════ */}
      {modalSel && (
        <div className="fixed inset-0 bg-black/70 z-[999999] flex items-center justify-center p-4" onClick={() => setModalSel(null)}>
          <div className="bg-surface-dark border border-border-dark rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b border-border-dark flex-shrink-0">
              <h2 className="text-xl font-black text-white">
                {modalSel.esSuplente ? 'Seleccionar Suplente' : `Seleccionar ${modalSel.posicion}`}
              </h2>
              <button onClick={() => setModalSel(null)} className="text-gray-400 hover:text-white"><span className="material-symbols-outlined">close</span></button>
            </div>
            <div className="p-4 border-b border-border-dark space-y-2 flex-shrink-0">
              <input type="text" placeholder="Buscar jugador..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} autoFocus
                className="w-full px-4 py-2 bg-background-dark border border-border-dark rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-primary" />
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <button
                    onClick={() => setShowEquipoFilterDropdown(!showEquipoFilterDropdown)}
                    className="w-full bg-background-dark border border-border-dark text-white px-3 py-2 rounded-lg text-sm flex items-center justify-between hover:border-primary/50 transition-colors"
                  >
                    <span>{equipoFiltro ? equipos.find(e => e.id == equipoFiltro)?.nombre : 'Todos los equipos'}</span>
                    <span className="material-symbols-outlined text-sm">arrow_drop_down</span>
                  </button>
                  {showEquipoFilterDropdown && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-background-dark border border-border-dark rounded-lg shadow-2xl z-[999998] py-1 max-h-48 overflow-y-auto">
                      <button
                        onClick={() => { setEquipoFiltro(''); setShowEquipoFilterDropdown(false) }}
                        className="w-full text-left px-4 py-2 text-white text-sm hover:bg-primary/20 transition-colors"
                      >
                        Todos los equipos
                      </button>
                      {equipos.map(eq => (
                        <button
                          key={eq.id}
                          onClick={() => { setEquipoFiltro(eq.id); setShowEquipoFilterDropdown(false) }}
                          className={`w-full text-left px-4 py-2 text-sm transition-colors ${equipoFiltro == eq.id ? 'bg-primary/20 text-primary font-bold' : 'text-white hover:bg-primary/10'}`}
                        >
                          {eq.nombre}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {modalSel.esSuplente && (
                  <div className="flex-1 relative">
                    <button
                      onClick={() => setShowPosFiltroDropdown(!showPosFiltroDropdown)}
                      className="w-full bg-background-dark border border-border-dark text-white px-3 py-2 rounded-lg text-sm flex items-center justify-between hover:border-primary/50 transition-colors"
                    >
                      <span>{posFiltro || 'Todas las posiciones'}</span>
                      <span className="material-symbols-outlined text-sm">arrow_drop_down</span>
                    </button>
                    {showPosFiltroDropdown && (
                      <div className="absolute top-full left-0 right-0 mt-1 bg-background-dark border border-border-dark rounded-lg shadow-2xl z-[999998] py-1">
                        <button
                          onClick={() => { setPosFiltro(''); setShowPosFiltroDropdown(false) }}
                          className="w-full text-left px-4 py-2 text-white text-sm hover:bg-primary/20 transition-colors"
                        >
                          Todas las posiciones
                        </button>
                        {POSICIONES.map(p => (
                          <button
                            key={p}
                            onClick={() => { setPosFiltro(p); setShowPosFiltroDropdown(false) }}
                            className={`w-full text-left px-4 py-2 text-sm transition-colors ${posFiltro === p ? 'bg-primary/20 text-primary font-bold' : 'text-white hover:bg-primary/10'}`}
                          >
                            {p}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
            <div className="overflow-y-auto flex-1 p-4 space-y-2">
              {jugadoresModal.length === 0 ? (
                <p className="text-center text-gray-400 py-8">No hay jugadores disponibles</p>
              ) : jugadoresModal.map(j => {
                const partidos = jugadorPartidos[j.id] || []
                
                return (
                  <button key={j.id} onClick={() => { setShowEquipoFilterDropdown(false); setShowPosFiltroDropdown(false); seleccionarJugador(j) }}
                    className="w-full flex flex-col gap-2 px-4 py-3 bg-background-dark hover:bg-primary/10 border border-border-dark/50 hover:border-primary/50 rounded-xl transition-all text-left">
                    <div className="grid grid-cols-[minmax(0,1fr),auto,auto] items-center w-full gap-3">
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-1 rounded text-xs font-bold text-white ${(POS_BADGE[j.posicion] || POS_BADGE.Delantero).bg}`}>
                          {(POS_BADGE[j.posicion] || POS_BADGE.Delantero).text}
                        </span>
                        <div className="flex flex-col min-w-0">
                          <p className="font-bold text-white text-sm truncate">{j.nombre} {j.apellido}</p>
                          <p className="text-xs text-gray-400">{j.equipo_nombre}</p>
                        </div>
                      </div>

                      {/* Centro: círculos perfectamente centrados entre nombre y vs */}
                      <div className="justify-self-center flex gap-2 w-40 justify-center">
                        {partidos.length > 0 && partidos.map((p, idx) => {
                          const ptos = p.puntos;
                          let bgColor = 'bg-gray-500';
                          if (ptos !== null && ptos !== undefined) {
                            if (ptos > 10) bgColor = 'bg-blue-500';
                            else if (ptos >= 6) bgColor = 'bg-green-500';
                            else if (ptos >= 1) bgColor = 'bg-yellow-400';
                            else if (ptos < 0) bgColor = 'bg-red-500';
                          }
                          const puntosStr = (p.minutos > 0 && ptos !== null && ptos !== undefined) ? ptos.toFixed(0) : '—';
                          return (
                            <div
                              key={idx}
                              title={`vs ${p.rival}`}
                              className={`w-7 h-7 rounded-full flex items-center justify-center text-white text-sm font-bold ${bgColor} cursor-help`}>
                              {puntosStr}
                            </div>
                          )
                        })}
                      </div>

                      <div className="flex items-center gap-3 justify-end">
                        {j.proximo_rival_nombre && (
                          <div className="text-xs text-gray-400 flex items-center gap-1 flex-shrink-0">
                            <span>vs</span><EscudoImg nombre={j.proximo_rival_nombre} size={18} />
                          </div>
                        )}
                        <div className="text-yellow-400 font-black text-sm flex-shrink-0">{(j.puntos_fantasy_25_26 || 0).toFixed(0)} pts</div>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL: Renombrar ════════════════════════════════════════════════ */}
      {modalRen && (
        <div className="fixed inset-0 bg-black/70 z-[99999] flex items-center justify-center p-4" onClick={() => setModalRen(false)}>
          <div className="bg-surface-dark border border-border-dark rounded-2xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-xl font-black text-white mb-4">Renombrar Plantilla</h2>
            <input type="text" value={nuevoNombre} onChange={e => setNuevoNombre(e.target.value)} onKeyDown={e => e.key === 'Enter' && renombrarPlantilla()} autoFocus
              className="w-full px-4 py-2 bg-background-dark border border-border-dark rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-primary mb-4" />
            <div className="flex gap-3">
              <button onClick={() => setModalRen(false)} className="flex-1 px-4 py-2.5 bg-surface-dark border border-border-dark text-white rounded-xl text-sm hover:bg-white/5">Cancelar</button>
              <button onClick={renombrarPlantilla} className="flex-1 px-4 py-2.5 bg-primary text-black rounded-xl font-bold text-sm hover:bg-primary-dark">Confirmar</button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL: Detalles jugador ═════════════════════════════════════════ */}
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
                <div className="flex items-center gap-2"><EscudoImg nombre={modalDet.equipo_nombre} size={24} /><span className="text-white text-sm font-bold">{modalDet.equipo_nombre || '-'}</span></div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Próximo rival</span>
                <div className="flex items-center gap-2">
                  {modalDet.proximo_rival_nombre && <EscudoImg nombre={modalDet.proximo_rival_nombre} size={24} />}
                  <span className="text-white text-sm font-bold">{modalDet.proximo_rival_nombre || 'TBD'}</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Puntos temp. actual</span>
                <span className="text-yellow-400 font-black">{(modalDet.puntos_fantasy_25_26 || 0).toFixed(0)}</span>
              </div>
              <div className="border-t border-border-dark pt-3">
                <p className="text-sm font-bold text-white mb-2">Predicción jornada {jornadaActual}</p>
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
                ) : predicciones[modalDet.id] != null ? (
                  <div className="text-2xl font-black text-yellow-400">
                    {predicciones[modalDet.id].type === 'media' ? 'Media histórica' : 'Predicción'}: {Number(predicciones[modalDet.id].value).toFixed(2)} pts
                  </div>
                ) : (
                  <span className="text-xs text-gray-500">Sin predicción disponible para esta jornada</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Modal de confirmación */}
      {modalConfirm && (
        <div className="fixed inset-0 bg-black/70 z-[99999] flex items-center justify-center p-4" onClick={() => setModalConfirm(null)}>
          <div className="bg-surface-dark border border-border-dark rounded-2xl w-full max-w-sm p-6" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-black text-white mb-3">{modalConfirm.titulo}</h2>
            <p className="text-gray-300 text-sm mb-6 leading-relaxed">{modalConfirm.mensaje}</p>
            <div className="flex gap-3">
              <button 
                onClick={modalConfirm.onCancel}
                className="flex-1 px-4 py-2.5 bg-surface-dark border border-border-dark text-white rounded-lg text-sm hover:bg-white/5 transition-colors"
              >
                Cancelar
              </button>
              <button 
                onClick={modalConfirm.onConfirm}
                className="flex-1 px-4 py-2.5 bg-primary text-black rounded-lg font-bold text-sm hover:bg-primary-dark transition-colors"
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}

      <HelpButton title="Guía de Mi Plantilla" sections={[
        { title: 'Plantilla Fantasy', fields: [
          { label: 'Formación', description: 'Esquema táctico que determina cuántos jugadores van en cada línea (ej: 4-3-3).' },
          { label: 'PTS Fantasy', description: 'Puntos acumulados por el jugador en la temporada según el sistema de puntuación fantasy.' },
          { label: 'Posición', description: 'Posición habitual del jugador: Portero (PT), Defensa (DF), Centrocampista (MC) o Delantero (DL).' },
          { label: 'Predicción', description: 'Puntuación estimada para el próximo partido basada en el modelo de IA.' },
        ]},
        { title: 'XAI – Explicabilidad', fields: [
          { label: 'Importancia', description: 'Factores que más influyen en la predicción de este jugador (positivos o negativos).' },
          { label: 'xG', description: 'Expected Goals: probabilidad estadística de marcar gol según las ocasiones generadas.' },
          { label: 'xAG', description: 'Expected Assisted Goals: probabilidad de dar una asistencia de gol según las acciones realizadas.' },
        ]},
      ]} />

      {/* Consejero Chat */}
      {showConsejero && (
        <ConsejeroChat 
          jugadores11={POSICIONES.flatMap(pos => alineacion[pos] || []).filter(Boolean)}
          plantillaId={plantillaId}
          onClose={() => setShowConsejero(false)}
        />
      )}
    </div>
  )
}

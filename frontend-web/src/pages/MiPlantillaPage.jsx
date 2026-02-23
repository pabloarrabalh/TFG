import { useState, useEffect, useRef } from 'react'
import LoadingSpinner from '../components/ui/LoadingSpinner'

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
}
const obtenerEscudo = (nombre) => ESCUDO_MAP[nombre] || (nombre?.toLowerCase().replace(/\s+/g, '_')) || null

const POSICIONES = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']
const ALINEACION_VACIA = { Portero: [], Defensa: [], Centrocampista: [], Delantero: [], Suplentes: [] }

function getCsrfToken() {
  const match = document.cookie?.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='))
  return match ? match.split('=')[1] : ''
}

// ─── Notificación flotante ──────────────────────────────────────────────────
function Notificacion({ notif, onDone }) {
  useEffect(() => {
    if (!notif) return
    const t = setTimeout(onDone, 3000)
    return () => clearTimeout(t)
  }, [notif])
  if (!notif) return null
  const cls = notif.tipo === 'success' ? 'bg-green-600' : notif.tipo === 'error' ? 'bg-red-600' : 'bg-blue-600'
  return (
    <div className={`fixed top-6 left-6 px-6 py-4 rounded-lg text-white shadow-lg z-[100000] transition-all ${cls}`}>
      {notif.msg}
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
      className={`bg-gradient-to-br ${gradient} rounded-xl p-3 text-center shadow-lg cursor-grab min-w-[130px] max-w-[150px] hover:scale-105 transition-all relative select-none ring-2 ${isDropTarget ? 'ring-primary ring-offset-1' : 'ring-transparent'}`}
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
      {/* Initials avatar */}
      <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center mx-auto mb-1 text-white font-black text-sm">
        {`${jugador.nombre[0]}${jugador.apellido ? jugador.apellido[0] : ''}`.toUpperCase()}
      </div>
      <p className="font-bold text-white text-xs leading-tight truncate px-4">
        {jugador.nombre} {jugador.apellido || ''}
      </p>
      <span className={`inline-block px-1.5 py-0.5 rounded text-white text-xs font-bold mt-1 ${badge.bg}`}>
        {badge.text}
      </span>
      {prediccion != null && (
        <div className="mt-1 text-yellow-300 font-black text-sm">{Number(prediccion).toFixed(1)} pts</div>
      )}
      <button
        onMouseDown={e => { e.stopPropagation(); onOpen(jugador) }}
        className="mt-1 text-white/60 hover:text-white text-xs underline block w-full"
      >
        Ver
      </button>
    </div>
  )
}

// ─── Slot vacío del campo ───────────────────────────────────────────────────
function EmptySlot({ posicion, indice, onAdd, isDropTarget, onDragOver, onDrop }) {
  return (
    <div
      className={`rounded-xl border-2 border-dashed flex flex-col items-center justify-center min-w-[120px] min-h-[100px] transition-all ${isDropTarget ? 'border-yellow-400 bg-yellow-400/10' : 'border-white/30 hover:border-white/60'}`}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <button
        onClick={() => onAdd(posicion, false, indice)}
        className="w-full h-full flex flex-col items-center justify-center gap-1 p-3 text-white/50 hover:text-white transition-colors"
      >
        <span className="material-symbols-outlined text-2xl">add_circle</span>
        <span className="text-xs font-semibold">{posicion[0]}</span>
      </button>
    </div>
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
      {prediccion != null && <div className="text-yellow-300 font-black text-xs mt-0.5">{Number(prediccion).toFixed(1)}</div>}
      <button onMouseDown={e => { e.stopPropagation(); onOpen(jugador) }} className="mt-1 text-white/60 hover:text-white text-xs underline">Ver</button>
    </div>
  )
}

// ─── COMPONENTE PRINCIPAL ───────────────────────────────────────────────────
export default function MiPlantillaPage() {
  const [loading, setLoading] = useState(true)
  const [jornadaActual, setJornadaActual] = useState(18)
  const [jugadoresDisponibles, setJugadoresDisponibles] = useState(ALINEACION_VACIA)
  const [alineacion, setAlineacion] = useState(ALINEACION_VACIA)
  const [formacion, setFormacion] = useState('4-3-3')
  const [plantillaId, setPlantillaId] = useState(null)
  const [plantillaNombre, setPlantillaNombre] = useState('Mi Team')
  const [todasPlantillas, setTodasPlantillas] = useState([])
  const [equipos, setEquipos] = useState([])
  const [saving, setSaving] = useState(false)
  const [notif, setNotif] = useState(null)
  const [predicciones, setPredicciones] = useState({})
  const [showFormDropdown, setShowFormDropdown] = useState(false)

  // Modales
  const [modalSel, setModalSel] = useState(null)   // { posicion, esSuplente, indice }
  const [modalRen, setModalRen] = useState(false)
  const [modalDet, setModalDet] = useState(null)   // jugador object
  const [nuevoNombre, setNuevoNombre] = useState('')

  // Filtros modal selección
  const [searchTerm, setSearchTerm] = useState('')
  const [equipoFiltro, setEquipoFiltro] = useState('')
  const [posFiltro, setPosFiltro] = useState('')

  // Modal detalles: predicción
  const [detPrediccion, setDetPrediccion] = useState(null)
  const [detExplicacion, setDetExplicacion] = useState(null)
  const [detFeaturesImpacto, setDetFeaturesImpacto] = useState([])
  const [detLoadingPred, setDetLoadingPred] = useState(false)

  // Drag & drop
  const dragRef = useRef(null)
  const [dropTarget, setDropTarget] = useState(null)

  // ── Init ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    loadJornada(18).then(() => loadPlantillas())
  }, [])

  // Cargar predicciones al cambiar alineación
  useEffect(() => {
    cargarPredicciones()
  }, [alineacion, jornadaActual])

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
        localStorage.setItem('jornadaActual', String(jornada))
        // Extraer equipos únicos
        const eqMap = new Map()
        Object.values(data.jugadores_por_posicion).flat().forEach(j => {
          if (j.equipo_id && !eqMap.has(j.equipo_id)) eqMap.set(j.equipo_id, j.equipo_nombre)
        })
        setEquipos([...eqMap.entries()].map(([id, nombre]) => ({ id, nombre })).sort((a, b) => a.nombre.localeCompare(b.nombre)))
        // Actualizar rivales de jugadores ya en alineación
        actualizarRivalesEnAlineacion(data.jugadores_por_posicion)
      }
    } catch (e) {
      console.error('Error cargando jornada:', e)
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
          return fresco ? { ...j, proximo_rival_nombre: fresco.proximo_rival_nombre } : j
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
      console.error('Error cargando plantillas:', e)
    }
  }

  function aplicarPlantilla(p) {
    setPlantillaId(p.id)
    setPlantillaNombre(p.nombre)
    setFormacion(p.formacion || '4-3-3')
    setAlineacion({ ...ALINEACION_VACIA, ...(p.alineacion || {}) })
  }

  function mostrarNotif(msg, tipo = 'success') {
    setNotif({ msg, tipo })
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

  // ── Predicciones ─────────────────────────────────────────────────────────
  async function cargarPredicciones() {
    const todos = [...POSICIONES.flatMap(p => alineacion[p] || []), ...(alineacion.Suplentes || [])].filter(Boolean)
    if (!todos.length) return
    for (const jug of todos) {
      if (predicciones[jug.id] !== undefined) continue
      try {
        const payload = { jugador_id: jug.id, jornada: jornadaActual, posicion: jug.posicion }
        console.log('[PRED] Enviando:', payload)
        const res = await fetch(`${BACKEND}/api/predecir-jugador/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          credentials: 'include',
          body: JSON.stringify(payload),
        })
        const data = await res.json()
        console.log('[PRED] Respuesta:', data)
        if (data.prediccion != null) setPredicciones(prev => ({ ...prev, [jug.id]: data.prediccion }))
        else if (data.error) console.error('[PRED] Error:', data.error)
      } catch (e) {
        console.error('[PRED] Excepción:', e)
      }
    }
  }

  async function abrirDetalles(jugador) {
    setModalDet(jugador); setDetPrediccion(null); setDetExplicacion(null); setDetFeaturesImpacto([])
    setDetLoadingPred(true)
    try {
      let url, body
      if (jugador.posicion === 'Portero') {
        url = `${BACKEND}/api/explicar-prediccion/`
        body = JSON.stringify({ jugador_id: jugador.id, jornada: jornadaActual, modelo: 'RF' })
      } else {
        url = `${BACKEND}/api/predecir-jugador/`
        body = JSON.stringify({ jugador_id: jugador.id, jornada: jornadaActual })
      }
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        credentials: 'include',
        body,
      })
      const data = await res.json()
      if (data.status === 'success') {
        setDetPrediccion(data.prediccion)
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
        // Swap – validar posición del jugador destino
        if (targetPos !== 'Suplentes' && destino.posicion !== fromPos) {
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
      <Notificacion notif={notif} onDone={() => setNotif(null)} />

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
          </div>
        </div>
      </div>

      {/* ── Selector jornada ── */}
      <div className="glass-panel rounded-2xl p-3 flex items-center justify-center gap-4">
        <button onClick={() => cambiarJornada(-1)} disabled={jornadaActual <= 1} className="px-3 py-1.5 bg-surface-dark border border-border-dark text-white rounded-lg hover:bg-primary/20 font-bold disabled:opacity-40">
          <span className="material-symbols-outlined text-lg">chevron_left</span>
        </button>
        <div className="flex items-center gap-2">
          <p className="text-gray-400 text-sm">Jornada</p>
          <select value={jornadaActual} onChange={e => loadJornada(parseInt(e.target.value))} className="text-2xl font-black text-white bg-transparent border-none outline-none text-center cursor-pointer">
            {Array.from({ length: 38 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}
          </select>
        </div>
        <button onClick={() => cambiarJornada(1)} disabled={jornadaActual >= 38} className="px-3 py-1.5 bg-surface-dark border border-border-dark text-white rounded-lg hover:bg-primary/20 font-bold disabled:opacity-40">
          <span className="material-symbols-outlined text-lg">chevron_right</span>
        </button>
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

          <div className="relative z-10 flex flex-col justify-around" style={{ minHeight: 640 }}>
            {renderLinea('Delantero')}
            {renderLinea('Centrocampista')}
            {renderLinea('Defensa')}
            {renderLinea('Portero')}
          </div>

          {/* ── Total puntos previstos (top-left) ── */}
          {(() => {
            const total = POSICIONES.flatMap(p => alineacion[p] || []).filter(Boolean).reduce((sum, j) => sum + (predicciones[j.id] ?? 0), 0)
            const count = POSICIONES.flatMap(p => alineacion[p] || []).filter(Boolean).length
            return (
              <div className="absolute top-4 left-4 bg-black/50 backdrop-blur-sm border border-white/20 rounded-xl px-4 py-3 text-center">
                <p className="text-white/60 text-xs font-semibold uppercase tracking-wider mb-0.5">Pts previstos</p>
                <p className="text-yellow-300 font-black text-2xl leading-none">{total > 0 ? total.toFixed(1) : '—'}</p>
                {count > 0 && <p className="text-white/40 text-xs mt-1">{count} jugadores</p>}
              </div>
            )
          })()}

          {/* ── Indicador posiciones (bottom-right) ── */}
          <div className="absolute bottom-4 right-4 bg-black/50 backdrop-blur-sm border border-white/20 rounded-xl px-4 py-3 space-y-1.5">
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
        <div className="fixed inset-0 bg-black/70 z-[9998] flex items-center justify-center p-4" onClick={() => setModalSel(null)}>
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
                <select value={equipoFiltro} onChange={e => setEquipoFiltro(e.target.value)} className="flex-1 bg-background-dark border border-border-dark text-white px-3 py-2 rounded-lg text-sm">
                  <option value="">Todos los equipos</option>
                  {equipos.map(eq => <option key={eq.id} value={eq.id}>{eq.nombre}</option>)}
                </select>
                {modalSel.esSuplente && (
                  <select value={posFiltro} onChange={e => setPosFiltro(e.target.value)} className="flex-1 bg-background-dark border border-border-dark text-white px-3 py-2 rounded-lg text-sm">
                    <option value="">Todas las posiciones</option>
                    {POSICIONES.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                )}
              </div>
            </div>
            <div className="overflow-y-auto flex-1 p-4 space-y-2">
              {jugadoresModal.length === 0 ? (
                <p className="text-center text-gray-400 py-8">No hay jugadores disponibles</p>
              ) : jugadoresModal.map(j => (
                <button key={j.id} onClick={() => seleccionarJugador(j)}
                  className="w-full flex items-center gap-3 px-4 py-3 bg-background-dark hover:bg-primary/10 border border-border-dark/50 hover:border-primary/50 rounded-xl transition-all text-left">
                  <span className={`px-2 py-1 rounded text-xs font-bold text-white ${(POS_BADGE[j.posicion] || POS_BADGE.Delantero).bg}`}>
                    {(POS_BADGE[j.posicion] || POS_BADGE.Delantero).text}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="font-bold text-white text-sm truncate">{j.nombre} {j.apellido}</p>
                    <p className="text-xs text-gray-400">{j.equipo_nombre}</p>
                  </div>
                  {j.proximo_rival_nombre && (
                    <div className="text-xs text-gray-400 flex items-center gap-1 flex-shrink-0">
                      <span>vs</span><EscudoImg nombre={j.proximo_rival_nombre} size={18} />
                    </div>
                  )}
                  <div className="text-yellow-400 font-black text-sm flex-shrink-0">{(j.puntos_fantasy_25_26 || 0).toFixed(0)} pts</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL: Renombrar ════════════════════════════════════════════════ */}
      {modalRen && (
        <div className="fixed inset-0 bg-black/70 z-[9998] flex items-center justify-center p-4" onClick={() => setModalRen(false)}>
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
        <div className="fixed inset-0 bg-black/70 z-[9998] flex items-center justify-center p-4" onClick={() => setModalDet(null)}>
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
                    <div className="text-2xl font-black text-yellow-400 mb-3">{Number(detPrediccion).toFixed(2)} pts</div>
                    {detFeaturesImpacto.length > 0 && (
                      <div>
                        <p className="text-xs font-bold text-blue-300 mb-2 uppercase tracking-wider">Factores clave</p>
                        <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                          {detFeaturesImpacto.map((f, i) => {
                            const signedImpact = f.direccion === 'negativo' ? -Math.abs(f.impacto) : Math.abs(f.impacto)
                            const isPos = signedImpact >= 0
                            return (
                              <div key={i} className={`flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 ${isPos ? 'bg-green-500/10 border border-green-500/20' : 'bg-red-500/10 border border-red-500/20'}`}>
                                <span className="text-white/85 text-xs leading-tight flex-1">{f.explicacion || f.feature}</span>
                                <span className={`text-xs font-black whitespace-nowrap ${isPos ? 'text-green-400' : 'text-red-400'}`}>
                                  {isPos ? '+' : ''}{signedImpact.toFixed(2)} pts
                                </span>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                ) : predicciones[modalDet.id] != null ? (
                  <div className="text-2xl font-black text-yellow-400">{Number(predicciones[modalDet.id]).toFixed(2)} pts</div>
                ) : (
                  <span className="text-xs text-gray-500">Sin predicción disponible para esta jornada</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const POSICIONES_CAMPO = ['Portero', 'Defensa', 'Centrocampista', 'Delantero']

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

function EscudoImg({ nombre, size = 24, BACKEND }) {
  const escudoMap = {
    'Real Madrid': 'madrid',
    'Barcelona': 'barcelona',
    'Atletico Madrid': 'atletico_madrid',
    'Real Sociedad': 'sociedad',
    'Villarreal': 'villarreal',
    'Athletic Club': 'athletic_club',
    'Real Betis': 'betis',
    'Girona': 'girona',
    'Rayo Vallecano': 'rayo_vallecano',
    'Osasuna': 'osasuna',
    'Valencia': 'valencia',
    'Celta Vigo': 'celta_vigo',
    'Real Mallorca': 'mallorca',
    'Getafe': 'getafe',
    'Sevilla': 'sevilla',
    'Alaves': 'alaves',
    'RCD Espanyol': 'espanyol',
    'Las Palmas': 'las_palmas',
    'Almeria': 'almeria',
    'Valladolid': 'valladolid',
    'Leganes': 'leganes',
  }
  const s = escudoMap[nombre] || (nombre?.toLowerCase().replace(/\s+/g, '_')) || null
  if (!s) return <span className="text-gray-400 text-xs font-bold">{(nombre || '?')[0]}</span>
  return (
    <img
      src={`/static/escudos/${s}.png`}
      alt={nombre}
      style={{ width: size, height: size }}
      className="object-contain rounded"
      onError={(e) => { e.target.style.display = 'none' }}
    />
  )
}

export default function CampoPlantilla({ alineacion, formaciones, predicciones, onCardClick, BACKEND }) {
  const formacion = Object.keys(formaciones).find(f => JSON.stringify(formaciones[f]) === JSON.stringify(formaciones[Object.keys(formaciones)[0]])) || '4-3-3'
  const cfg = formaciones[formacion]

  const todosLosJugadores = [
    ...(alineacion.Portero || []),
    ...(alineacion.Defensa || []),
    ...(alineacion.Centrocampista || []),
    ...(alineacion.Delantero || []),
  ].filter(Boolean)

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
              onClick={() => onCardClick && onCardClick(j)}
            >
              {j.proximo_rival_nombre && (
                <div className="absolute top-2 right-2 opacity-90">
                  <EscudoImg nombre={j.proximo_rival_nombre} size={20} BACKEND={BACKEND} />
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
              <button
                onClick={e => { e.stopPropagation(); onCardClick && onCardClick(j) }}
                className="text-white/60 hover:text-white text-xs font-semibold transition-colors"
              >
                Ver
              </button>
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

        {/* Total puntos previstos */}
        {(() => {
          const total = todosLosJugadores.reduce((sum, j) => sum + (predicciones[j.id] ?? 0), 0)
          const count = todosLosJugadores.length
          return (
            <div className="absolute top-4 left-4 bg-black/50 backdrop-blur-sm border border-white/20 rounded-xl px-4 py-3 text-center">
              <p className="text-white/60 text-xs font-semibold uppercase tracking-wider mb-0.5">Pts previstos</p>
              <p className="text-yellow-300 font-black text-2xl leading-none">{total > 0 ? total.toFixed(1) : '—'}</p>
              {count > 0 && <p className="text-white/40 text-xs mt-1">{count} jugadores</p>}
            </div>
          )
        })()}

        {/* Indicador posiciones */}
        <div className="absolute bottom-4 left-4 bg-black/50 backdrop-blur-sm border border-white/20 rounded-xl px-4 py-3 space-y-1.5">
          {POSICIONES_CAMPO.map((pos) => {
            const slots = cfg[pos] || 1
            const filled = (alineacion[pos] || []).filter(Boolean).length
            const badge = POS_BADGE[pos]
            return (
              <div key={pos} className="flex items-center gap-2">
                <span className={`${badge.bg} text-white text-xs font-bold px-1.5 py-0.5 rounded w-9 text-center flex-shrink-0`}>{badge.text}</span>
                <div className="flex gap-1">
                  {Array.from({ length: slots }, (_, i) => (
                    <div
                      key={i}
                      className={`w-2.5 h-2.5 rounded-full border transition-all ${
                        i < filled ? `${badge.bg} border-transparent` : 'border-white/40 bg-transparent'
                      }`}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

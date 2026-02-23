// Racha visual (VVEDP) para clasificación
export function RachaDisplay({ racha = '' }) {
  if (!racha) return null
  
  const colorMap = {
    'V': 'bg-green-500',  // Victoria
    'E': 'bg-yellow-500', // Empa
    'D': 'bg-red-500',    // Derrota - antes P ahora D
    'P': 'bg-red-500',    // Por si acaso compatibilidad atrás
  }
  
  return (
    <div className="flex gap-0.5">
      {racha.split('').map((r, i) => (
        <div
          key={i}
          className={`size-6 rounded-full ${colorMap[r] || 'bg-gray-600'} flex items-center justify-center text-white text-xs font-bold cursor-help group relative transition-all hover:scale-110`}
          title={r === 'V' ? 'Victoria' : r === 'E' ? 'Empate' : 'Derrota'}
        >
          {r}
          <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-black/80 text-white text-xs px-2 py-1 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
            {r === 'V' ? '✓ Victoria' : r === 'E' ? '= Empate' : '✗ Derrota'}
          </div>
        </div>
      ))}
    </div>
  )
}

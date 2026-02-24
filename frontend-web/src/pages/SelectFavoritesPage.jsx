import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'

export default function SelectFavoritesPage() {
  const navigate = useNavigate()

  const [equipos, setEquipos] = useState([])
  const [favoritos, setFavoritos] = useState(new Set()) // Set of equipo IDs
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [eqRes, favRes] = await Promise.all([
        api.get('/api/equipos/'),
        api.get('/api/favoritos/'),
      ])
      console.log('Equipos response:', eqRes.data)
      setEquipos(eqRes.data.equipos || [])
      const favIds = new Set((favRes.data.favoritos || []).map(f => f.equipo_id))
      setFavoritos(favIds)
    } catch (err) {
      console.error('Error loading data:', err)
    } finally {
      setLoading(false)
    }
  }

  async function toggle(equipoId) {
    const wasFav = favoritos.has(equipoId)
    // Optimistic update
    setFavoritos(prev => {
      const next = new Set(prev)
      if (wasFav) next.delete(equipoId)
      else next.add(equipoId)
      return next
    })
    try {
      await api.post('/api/favoritos/toggle-v2/', { equipo_id: equipoId })
    } catch {
      // Revert
      setFavoritos(prev => {
        const next = new Set(prev)
        if (wasFav) next.add(equipoId)
        else next.delete(equipoId)
        return next
      })
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen">
      <LoadingSpinner size="lg" />
    </div>
  )

  return (
    <div className="p-6 space-y-6 min-h-screen">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-4xl font-black text-white mb-2">Selecciona tus equipos favoritos</h1>
        <p className="text-gray-400 text-lg">Elige los equipos que quieras seguir de cerca</p>
        {favoritos.size > 0 && (
          <p className="text-primary text-sm mt-2 font-semibold">
            {favoritos.size} equipo{favoritos.size !== 1 ? 's' : ''} seleccionado{favoritos.size !== 1 ? 's' : ''}
          </p>
        )}
      </div>

      {/* Teams grid */}
      <GlassPanel className="p-8">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {equipos.map(equipo => {
            const isFav = favoritos.has(equipo.id)
            return (
              <button
                key={equipo.id}
                onClick={() => toggle(equipo.id)}
                className="group cursor-pointer text-left transition-all"
              >
                <div
                  className={`aspect-square rounded-xl border-2 transition-all flex items-center justify-center overflow-hidden ${
                    isFav
                      ? 'border-primary bg-primary/10 shadow-[0_0_15px_rgba(57,255,20,0.2)]'
                      : 'border-border-dark bg-surface-dark group-hover:border-primary/50'
                  }`}
                >
                  <TeamShield escudo={equipo.escudo} nombre={equipo.nombre} size={64} className="w-3/4 h-3/4 object-contain" />
                  {isFav && (
                    <div className="absolute top-2 right-2">
                      <span className="material-symbols-outlined text-primary text-lg">check_circle</span>
                    </div>
                  )}
                </div>
                <p className={`mt-2 text-center text-sm font-semibold truncate transition-colors ${isFav ? 'text-primary' : 'text-white group-hover:text-primary'}`}>
                  {equipo.nombre}
                </p>
              </button>
            )
          })}
        </div>
      </GlassPanel>

      {/* Action buttons */}
      <div className="flex gap-4 justify-center mt-6">
        <button
          onClick={() => navigate('/menu')}
          className="bg-primary hover:bg-primary-dark text-black font-bold px-8 py-3 rounded-xl transition-all"
        >
          Continuar
        </button>
      </div>
    </div>
  )
}

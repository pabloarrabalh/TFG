import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import apiClient from '../services/apiClient'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'
import { useAuth } from '../context/AuthContext'

export default function EquiposPage() {
  const { user } = useAuth()
  const [equipos, setEquipos] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    apiClient.get('/api/equipos/')
      .then(({ data }) => setEquipos(data.equipos || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const toggleFavorito = async (equipoId) => {
    if (!user) return
    try {
      await apiClient.post('/api/favoritos/toggle-v2/', { equipo_id: equipoId })
      setEquipos((prev) => prev.map((e) => e.id === equipoId ? { ...e, es_favorito: !e.es_favorito } : e))
    } catch (err) { console.error(err) }
  }

  const filtered = equipos.filter((e) => e.nombre.toLowerCase().includes(search.toLowerCase()))

  if (loading) return <LoadingSpinner />

  return (
    <div className="p-6 bg-background-dark min-h-full">
      <div className="mb-8">
        <h2 className="text-3xl font-black text-white mb-2">Equipos</h2>
        <p className="text-gray-400 text-lg">LaLiga EA Sports</p>
      </div>

      {/* Search */}
      <div className="mb-6">
        <div className="relative w-full max-w-md">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">search</span>
          <input
            type="text"
            placeholder="Buscar equipo..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-surface-dark-lighter border border-border-dark rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary/50 transition-colors"
          />
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtered.map((eq) => (
          <GlassPanel key={eq.id} className="p-5 hover:border-primary/30 transition-all group">
            <div className="flex items-start justify-between mb-4">
              <Link to={`/equipo/${encodeURIComponent(eq.nombre)}`} className="flex items-center gap-3 flex-1 min-w-0 group-hover:text-primary transition-colors">
                <TeamShield escudo={eq.escudo} nombre={eq.nombre} className="size-14 object-contain flex-shrink-0" />
                <div className="min-w-0">
                  <h3 className="font-black text-white text-sm truncate group-hover:text-primary transition-colors">{eq.nombre}</h3>
                  {eq.estadio && <p className="text-xs text-gray-500 truncate mt-1">{eq.estadio}</p>}
                </div>
              </Link>
              {user && (
                <button
                  onClick={() => toggleFavorito(eq.id)}
                  className={`flex-shrink-0 ml-2 p-2 rounded-lg transition-all ${eq.es_favorito ? 'text-red-500 hover:text-red-400 bg-red-500/10' : 'text-gray-500 hover:text-red-400 hover:bg-red-500/10'}`}
                  title={eq.es_favorito ? 'Quitar de favoritos' : 'Añadir a favoritos'}
                >
                  <span className="material-symbols-outlined text-lg">{eq.es_favorito ? 'favorite' : 'favorite_border'}</span>
                </button>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500 font-medium">{eq.jugadores_count} jugadores</span>
              <Link
                to={`/equipo/${encodeURIComponent(eq.nombre)}`}
                className="text-xs text-primary font-bold hover:text-primary-dark transition-colors flex items-center gap-1"
              >
                Ver equipo <span className="material-symbols-outlined text-sm">arrow_forward</span>
              </Link>
            </div>
          </GlassPanel>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full text-center text-gray-400 py-16">
            <span className="material-symbols-outlined text-4xl mb-2 block">search_off</span>
            <p>No se encontraron equipos</p>
          </div>
        )}
      </div>
    </div>
  )
}

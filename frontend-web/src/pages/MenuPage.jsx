import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import apiClient from '../services/apiClient'
import { useAuth } from '../context/AuthContext'
import GlassPanel from '../components/ui/GlassPanel'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TeamShield from '../components/ui/TeamShield'

const BACKEND = 'http://localhost:8000'

function formatTime(hora) {
  if (!hora) return 'Por definir'
  return hora.slice(0, 5)
}
function formatDate(fecha) {
  if (!fecha) return ''
  const [y, m, d] = fecha.split('-')
  return `${d}/${m}`
}

export default function MenuPage() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient.get('/api/menu/')
      .then(({ data }) => setData(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner />

  const { clasificacion_top = [], jornada_actual, proxima_jornada, partidos_proxima_jornada = [], partidos_favoritos = [] } = data || {}

  return (
    <div className="p-6 space-y-6 bg-background-dark min-h-full">
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-black text-white mb-2">¡Bienvenido de vuelta!</h2>
        <p className="text-gray-400 text-lg">Gestiona tu equipo y sigue la liga</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 max-w-screen-2xl mx-auto">
        {/* Left column */}
        <div className="xl:col-span-4 space-y-6">

          {/* Clasificación top 5 */}
          <GlassPanel className="overflow-hidden">
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
          <GlassPanel className="p-6">
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
                    <div className="flex items-center justify-between gap-2">
                      <Link to={`/equipo/${encodeURIComponent(p.equipo_local)}`} className="flex items-center gap-2 min-w-0 hover:text-primary transition-colors">
                        <TeamShield escudo={p.equipo_local_escudo} nombre={p.equipo_local} className="size-10 object-contain flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="font-bold text-white text-xs truncate">{p.equipo_local}</p>
                          <p className="text-xs text-gray-400">Local</p>
                        </div>
                      </Link>
                      <div className="text-center flex-shrink-0">
                        <p className="text-xs text-gray-400 font-bold">VS</p>
                        <p className="text-xs text-primary font-bold">{formatTime(p.hora)}</p>
                        <p className="text-xs text-gray-500 font-bold">{formatDate(p.fecha)}</p>
                      </div>
                      <Link to={`/equipo/${encodeURIComponent(p.equipo_visitante)}`} className="flex items-center gap-2 min-w-0 flex-row-reverse hover:text-primary transition-colors">
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
              <GlassPanel className="p-6">
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
                      <div className="flex items-center justify-between">
                        <Link to={`/equipo/${encodeURIComponent(p.equipo_local)}`} className="flex items-center gap-3 hover:text-primary transition-colors">
                          <TeamShield escudo={p.equipo_local_escudo} nombre={p.equipo_local} className="size-10 object-contain" />
                          <div>
                            <p className="font-bold text-white text-sm">{p.equipo_local}</p>
                            <p className="text-xs text-gray-400">Local</p>
                          </div>
                        </Link>
                        <div className="text-center">
                          <p className="text-xs text-gray-400 font-bold">VS</p>
                          <p className="text-xs text-primary font-bold">{formatTime(p.hora)}</p>
                          <p className="text-xs text-gray-500">{formatDate(p.fecha)}</p>
                        </div>
                        <Link to={`/equipo/${encodeURIComponent(p.equipo_visitante)}`} className="flex items-center gap-3 hover:text-primary transition-colors flex-row-reverse">
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

          {/* Jugadores destacados placeholder */}
          <GlassPanel className="p-6">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-r from-yellow-500 to-orange-500 rounded-xl p-3">
                <span className="material-symbols-outlined text-white text-xl font-bold">trending_up</span>
              </div>
              <div>
                <h3 className="text-xl font-black text-white">Jugadores Destacados</h3>
                <p className="text-xs text-gray-500 font-bold uppercase tracking-widest">
                  {proxima_jornada ? `Próxima Jornada - J${proxima_jornada.numero}` : 'Próxima jornada'}
                </p>
              </div>
            </div>
            <div className="mt-6 text-center text-gray-500 py-6">
              <span className="material-symbols-outlined text-3xl mb-2 block">trending_up</span>
              <p className="text-sm">Estadísticas disponibles al inicio de la jornada</p>
            </div>
          </GlassPanel>
        </div>
      </div>
    </div>
  )
}

import { Link } from 'react-router-dom'
import { buildSignedFeatureRows } from '../../utils/featureExplanations'

function normalizePrediction(prediction) {
  if (prediction == null) {
    return null
  }

  if (typeof prediction === 'number') {
    return { value: prediction, type: 'prediccion' }
  }

  if (typeof prediction === 'object' && prediction.value != null) {
    return prediction
  }

  return null
}

function ImpactSection({ title, titleClass, rowClass, valueClass, rows, isPositive }) {
  return (
    <div>
      <p className={`text-xs font-bold mb-1 uppercase tracking-wider ${titleClass}`}>{title}</p>
      <div className="space-y-1">
        {rows.map((row, index) => (
          <div key={`${title}-${index}`} className={`rounded-lg px-2.5 py-2 ${rowClass}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-white/85 text-xs leading-tight font-semibold flex-1">
                {row.label}
              </span>
              {row.isPlaceholder ? (
                <span className="text-xs font-black whitespace-nowrap text-gray-500">-</span>
              ) : (
                <span className={`text-xs font-black whitespace-nowrap ${valueClass}`}>
                  {isPositive ? '+' : '-'}{Math.abs(row.impact).toFixed(2)} pts
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function PlayerPredictionModal({
  player,
  onClose,
  loading,
  prediction,
  fallbackPrediction,
  featureImpacts,
  predictionTitle = 'Prediccion',
  renderShield,
  showSeasonPoints = false,
  seasonPoints,
  showProfileLink = false,
  profileUrl,
}) {
  if (!player) {
    return null
  }

  const activePrediction = normalizePrediction(prediction) || normalizePrediction(fallbackPrediction)
  const teamName = player.equipo_nombre || player.equipo || '-'
  const rivalName = player.proximo_rival_nombre || player.proximo_rival || null

  const hasSeasonPoints = showSeasonPoints && seasonPoints != null
  const positiveRows = buildSignedFeatureRows(featureImpacts, true, 3)
  const negativeRows = buildSignedFeatureRows(featureImpacts, false, 3)
  const showImpactSections = activePrediction && activePrediction.type !== 'media'

  return (
    <div className="fixed inset-0 bg-black/70 z-[99999] flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface-dark border border-border-dark rounded-2xl w-full max-w-md p-6" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-black text-white truncate">{player.nombre} {player.apellido}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white flex-shrink-0">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">Equipo</span>
            <div className="flex items-center gap-2">
              {typeof renderShield === 'function' ? renderShield(teamName, 24) : null}
              <span className="text-white text-sm font-bold">{teamName}</span>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-gray-400 text-sm">Proximo rival</span>
            <div className="flex items-center gap-2">
              {rivalName && typeof renderShield === 'function' ? renderShield(rivalName, 24) : null}
              <span className="text-white text-sm font-bold">{rivalName || 'TBD'}</span>
            </div>
          </div>

          {hasSeasonPoints && (
            <div className="flex items-center justify-between">
              <span className="text-gray-400 text-sm">Puntos temp. actual</span>
              <span className="text-yellow-400 font-black">{Number(seasonPoints).toFixed(0)}</span>
            </div>
          )}

          <div className="border-t border-border-dark pt-3">
            <p className="text-sm font-bold text-white mb-2">{predictionTitle}</p>

            {loading ? (
              <div className="flex items-center gap-2 text-xs text-gray-400 italic">
                <span className="animate-spin inline-block w-3 h-3 border-2 border-yellow-400 border-t-transparent rounded-full" />
                Analizando al jugador...
              </div>
            ) : activePrediction ? (
              <div>
                {activePrediction.type === 'media' ? (
                  <div className="bg-blue-500/20 border border-blue-500/40 rounded-lg p-3 mb-3">
                    <p className="text-xs font-bold text-blue-300 mb-1">MEDIA HISTORICA</p>
                    <div className="text-2xl font-black text-blue-400">{Number(activePrediction.value).toFixed(2)} pts</div>
                    <p className="text-xs text-blue-200/70 mt-1">Promedio de puntos en partidos anteriores sin IA</p>
                  </div>
                ) : (
                  <div className="bg-yellow-500/20 border border-yellow-500/40 rounded-lg p-3 mb-3">
                    <p className="text-xs font-bold text-yellow-300 mb-1">PREDICCION CON IA</p>
                    <div className="text-2xl font-black text-yellow-400">{Number(activePrediction.value).toFixed(2)} pts</div>
                    <p className="text-xs text-yellow-200/70 mt-1">Estimacion basada en modelo de machine learning</p>
                  </div>
                )}

                {activePrediction.modelo && (
                  <p className="text-xs text-gray-400 mb-3">
                    Modelo: <span className="text-primary font-bold">{activePrediction.modelo}</span>
                  </p>
                )}

                {showImpactSections && (
                  <div className="space-y-2">
                    <ImpactSection
                      title="A favor"
                      titleClass="text-green-400"
                      rowClass="bg-green-500/10 border border-green-500/20"
                      valueClass="text-green-400"
                      rows={positiveRows}
                      isPositive
                    />
                    <ImpactSection
                      title="En contra"
                      titleClass="text-red-400"
                      rowClass="bg-red-500/10 border border-red-500/20"
                      valueClass="text-red-400"
                      rows={negativeRows}
                      isPositive={false}
                    />
                  </div>
                )}
              </div>
            ) : (
              <span className="text-xs text-gray-500">Sin prediccion disponible para esta jornada</span>
            )}
          </div>

          {showProfileLink && profileUrl && (
            <div className="border-t border-border-dark pt-4">
              <Link
                to={profileUrl}
                className="w-full block text-center bg-primary hover:bg-primary-dark text-black px-4 py-2 rounded-lg font-bold text-sm transition-colors"
              >
                Ver perfil completo
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

import { COMPARISON_FIELDS_BY_DOMAIN } from './comparisonConfig'

const toNumber = (value) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

const formatValue = (value) => {
  const numeric = toNumber(value)
  if (Number.isInteger(numeric)) return numeric.toString()
  return numeric.toFixed(2)
}

const getPer90Value = (value, minutes) => {
  const mins = toNumber(minutes)
  if (mins <= 0) return null
  return toNumber(value) / (mins / 90)
}

export default function ComparisonMetricsCards({
  entries = [],
  domain = 'general',
  fieldsByDomain = COMPARISON_FIELDS_BY_DOMAIN,
  emptyMessage = 'Selecciona datos para ver la comparacion',
}) {
  if (!entries.length) {
    return (
      <div className="text-center py-8 text-gray-400">
        <p>{emptyMessage}</p>
      </div>
    )
  }

  const fields = fieldsByDomain[domain] || fieldsByDomain.general || []
  const columnsStyle = {
    gridTemplateColumns: `repeat(${entries.length}, minmax(0, 1fr))`,
  }

  return (
    <div className="space-y-4">
      {fields.map((field) => {
        const values = entries.map((entry) => toNumber(entry?.stats?.[field.key]))
        const maxValue = Math.max(...values)
        const bestCount = values.filter((value) => value === maxValue).length
        const sortedDesc = [...values].sort((a, b) => b - a)
        const secondBest = sortedDesc.find((value) => value < maxValue)

        return (
          <div key={field.key} className="bg-surface-dark rounded-xl p-4 border border-border-dark/50">
            <p className="text-xs text-gray-400 font-bold mb-3 uppercase">{field.label}</p>

            <div className="grid gap-3" style={columnsStyle}>
              {entries.map((entry) => {
                  const entryValue = toNumber(entry?.stats?.[field.key])
                  const isBest = maxValue > 0 && entryValue === maxValue
                  const bestGain = isBest && bestCount === 1 && secondBest !== undefined
                    ? maxValue - secondBest
                    : null
                  const value = toNumber(entry?.stats?.[field.key])
                  const per90Value = field.per90 ? getPer90Value(value, entry?.minutes) : null

                  return (
                    <div
                      key={`${field.key}-${entry.id}`}
                      className={`space-y-0.5 rounded-lg border p-3 min-w-0 ${
                        isBest
                          ? 'border-green-400/40 bg-green-500/10'
                          : 'border-border-dark/40 bg-black/20'
                      }`}
                    >
                      <p className="text-sm text-gray-300 truncate">{entry.label}</p>
                      {entry.subLabel && <p className="text-xs text-gray-500 truncate">{entry.subLabel}</p>}
                      <p className={`font-bold ${field.valueClass || 'text-white'}`}>{formatValue(value)}</p>
                      {per90Value !== null && (
                        <p className="text-xs text-gray-400">{formatValue(per90Value)}/90min</p>
                      )}
                      {bestGain !== null && bestGain > 0 && (
                        <p className="text-xs font-semibold text-green-300">(+ {formatValue(bestGain)})</p>
                      )}
                    </div>
                  )
                })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

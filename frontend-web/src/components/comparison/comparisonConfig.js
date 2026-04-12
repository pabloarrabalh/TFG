export const COMPARISON_DOMAINS = [
  { key: 'general', label: 'General' },
  { key: 'ataque', label: 'Ataque' },
  { key: 'pase', label: 'Pase y Asistencias' },
  { key: 'regates', label: 'Regates' },
  { key: 'defensa', label: 'Defensa' },
]

export const COMPARISON_FIELDS_BY_DOMAIN = {
  general: [
    { key: 'puntos_por_partido', label: 'Puntos/PJ' },
    { key: 'partidos', label: 'Partidos' },
    { key: 'minutos', label: 'Minutos' },
    { key: 'goles', label: 'Goles', per90: true, valueClass: 'text-green-400' },
    { key: 'asistencias', label: 'Asistencias', per90: true, valueClass: 'text-blue-400' },
    { key: 'goles_vs_xg', label: 'Goles - xG', per90: true },
    { key: 'asistencias_vs_xag', label: 'Asistencias - xAG', per90: true },
  ],
  ataque: [
    { key: 'goles', label: 'Goles', per90: true, valueClass: 'text-green-400' },
    { key: 'xg', label: 'xG', per90: true },
    { key: 'goles_vs_xg', label: 'Goles - xG', per90: true },
    { key: 'tiros', label: 'Tiros', per90: true },
    { key: 'tiros_puerta', label: 'Tiros Puerta', per90: true },
  ],
  pase: [
    { key: 'asistencias', label: 'Asistencias', per90: true, valueClass: 'text-blue-400' },
    { key: 'xag', label: 'xAG', per90: true },
    { key: 'asistencias_vs_xag', label: 'Asistencias - xAG', per90: true },
    { key: 'pases', label: 'Pases', per90: true },
    { key: 'pases_accuracy', label: 'Precision %' },
  ],
  regates: [
    { key: 'regates_completados', label: 'Regates completados', per90: true, valueClass: 'text-purple-400' },
    { key: 'regates_fallidos', label: 'Regates fallados', per90: true, valueClass: 'text-red-400' },
    { key: 'conducciones', label: 'Conducciones', per90: true },
    { key: 'conducciones_progresivas', label: 'Conducciones progresivas', per90: true },
  ],
  defensa: [
    { key: 'entradas', label: 'Entradas', per90: true },
    { key: 'despejes', label: 'Despejes', per90: true },
    { key: 'duelos_totales', label: 'Duelos', per90: true },
    { key: 'duelos_ganados', label: 'Duelos ganados', per90: true, valueClass: 'text-green-400' },
    { key: 'duelos_perdidos', label: 'Duelos perdidos', per90: true, valueClass: 'text-red-400' },
    { key: 'duelos_aereos_totales', label: 'Duelos aereos', per90: true },
    { key: 'amarillas', label: 'Amarillas' },
    { key: 'rojas', label: 'Rojas', valueClass: 'text-red-500' },
  ],
}

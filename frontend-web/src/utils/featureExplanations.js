export const FEATURE_EXPLANATIONS = {
  num_roles: { positiva: 'Jugador versatil. Ha ocupado muchos roles distintos esta temporada.', negativa: 'Rol limitado. Juega casi siempre en la misma posicion sin variacion.' },
  num_roles_criticos: { positiva: 'Roles clave. Ocupa posiciones decisivas en el esquema del equipo.', negativa: 'Sin rol protagonista. No suele ocupar posiciones decisivas.' },
  pf_roll5: { positiva: 'Buena racha. Lleva 5 partidos puntuando por encima de su media.', negativa: 'Mala racha. Ha bajado el rendimiento en los ultimos 5 partidos.' },
  pf_ewma5: { positiva: 'Tendencia ascendente. Su puntuacion mejora semana a semana.', negativa: 'Tendencia bajista. Su puntuacion cae en las ultimas jornadas.' },

  psxg_ewma5: { positiva: 'Portero solido. Para mas de lo que se espera estadisticamente.', negativa: 'Portero con dificultades. Encaja mas de lo que el xG predice.' },
  psxg_roll5: { positiva: 'Racha de grandes paradas. Ha superado el xG en los ultimos 5 partidos.', negativa: 'Racha floja bajo palos. Ha encajado mas de lo esperado en los ultimos 5 partidos.' },
  save_advantage: { positiva: 'Por encima del xG. Realiza paradas que el modelo no predice.', negativa: 'Por debajo del xG. Encaja mas goles de los que el modelo esperaria.' },

  shots_ewma5: { positiva: 'Muy disparador. Genera muchos remates y pone en aprietos al rival.', negativa: 'Poco rematador. No genera suficientes disparos a puerta.' },
  xg_ewma5: { positiva: 'Muchas ocasiones claras. Recibe balones en posicion de gol con frecuencia.', negativa: 'Pocas oportunidades claras. No llega habitualmente al area con peligro.' },
  goals_ewma5: { positiva: 'Tendencia goleadora al alza. Esta marcando con mas frecuencia semana a semana.', negativa: 'Tendencia goleadora a la baja. Marca cada vez menos goles.' },
  shots_on_target_ewma5: { positiva: 'Tendencia de disparos a puerta al alza. Cada vez mas preciso y peligroso.', negativa: 'Tendencia de disparos a puerta a la baja. Pierde precision en el remate.' },

  succ_dribbles_roll5: { positiva: 'Regates completados. Ha superado con exito a rivales en los ultimos 5 partidos.', negativa: 'Pocos regates completados. No logra superar rivales en conduccion ultimamente.' },
  dribble_attempts_roll5: { positiva: 'Muy intentador en regate. Busca superar rivales con mucha frecuencia.', negativa: 'Pocos intentos de regate. No busca superar rivales ni avanzar con el balon.' },
  prog_dribbles_roll5: { positiva: 'Conducciones progresivas. Avanza con el balon haciendo dano hacia el area rival.', negativa: 'Pocas conducciones progresivas. No lleva el balon hacia zonas de peligro.' },
  progressive_pressure: { positiva: 'Gran avance con balon. Conduce y progresa metros con el esferico.', negativa: 'Poca conduccion en progresion. No avanza con el balon hacia la porteria.' },
  prog_dist_ewma5: { positiva: 'Gran movilidad ofensiva. Recorre muchos metros en zona de progresion.', negativa: 'Poca movilidad progresiva. No avanza mucho en zona de creacion.' },
  distance_per_dribble: { positiva: 'Regateador efectivo. Avanza mucho terreno por regate completado.', negativa: 'Regates poco productivos. Avanza poco terreno por cada regate.' },

  pass_comp_pct_ewma5: { positiva: 'Pases precisos. Tiene una tasa de acierto alta en la distribucion reciente.', negativa: 'Impreciso en el pase. Ha fallado muchos pases en las ultimas jornadas.' },
  pass_comp_pct_roll5: { positiva: 'Solido en el juego de pase. Muy fiable con el balon en los ultimos 5 partidos.', negativa: 'Bajo porcentaje de pases completados en los ultimos 5 partidos.' },
  passes_ewma5: { positiva: 'Tendencia de pases al alza. Cada vez mas implicado en la circulacion del juego.', negativa: 'Tendencia de pases a la baja. Pierde protagonismo en la distribucion.' },
  pass_productivity: { positiva: 'Alta productividad en pases. Muchos pases completados con gran precision.', negativa: 'Baja productividad en pases. Poco volumen o poca precision de pase.' },

  def_actions_ewma5: { positiva: 'Muy activo defensivamente. Realiza entradas, despejes e intercepciones.', negativa: 'Poca accion defensiva. No registra acciones de recuperacion recientemente.' },
  tackles_ewma5: { positiva: 'Tendencia de entradas al alza. Cada vez mas activo en la recuperacion defensiva.', negativa: 'Tendencia de entradas a la baja. Menos actividad defensiva en las ultimas jornadas.' },
  intercepts_ewma5: { positiva: 'Tendencia de interceptaciones al alza. Mejora su lectura defensiva semana a semana.', negativa: 'Tendencia de interceptaciones a la baja. Pierde lecturas defensivas.' },
  defensive_intensity: { positiva: 'Alta intensidad defensiva. Mucha presion, duelos y recuperaciones de balon.', negativa: 'Baja intensidad defensiva. Poca presion ni acciones de recuperacion.' },

  opp_gc_ewma5: { positiva: 'Rival con fuga defensiva. El equipo contrario encaja muchos goles ultimamente.', negativa: 'Rival solido atras. El equipo contrario ha encajado poco recientemente.' },
  opp_form_ewma5: { positiva: 'Rival en mal momento. Ha perdido varios puntos en sus ultimas jornadas.', negativa: 'Rival en buena forma. Ha sumado muchos puntos ultimamente.' },
  odds_prob_loss: { positiva: 'Favorito segun las casas. Las apuestas le dan pocas opciones al rival.', negativa: 'Probable derrota. Las cuotas le dan posibilidades bajas de ganar.' },
  odds_expected_goals_against: { positiva: 'Pocas llegadas esperadas del rival. El equipo defendera bien segun las cuotas.', negativa: 'Muchas llegadas esperadas del rival. Se esperan oportunidades en contra.' },
  is_home: { positiva: 'Juega en casa. El factor local suele ayudar al rendimiento.', negativa: 'Juega fuera. Actuar de visitante penaliza estadisticamente.' },

  minutes_pct_ewma5: { positiva: 'Minutos elevados. Ha jugado muchos minutos en sus ultimos partidos.', negativa: 'Pocos minutos recientes. Ha tenido poco protagonismo en las ultimas jornadas.' },
  minutes_pct_roll5: { positiva: 'Continuidad de juego. Ha completado la mayoria de los ultimos 5 partidos.', negativa: 'Intermitente. No ha jugado completo con regularidad en los ultimos 5 partidos.' },
  starter_pct_roll3: { positiva: 'Titular asegurado. Ha salido de inicio en los ultimos 3 partidos.', negativa: 'Sin sitio en el once. Ha sido suplente en varios de los ultimos 3 partidos.' },
  availability_momentum: { positiva: 'Disponibilidad al alza. Ha estado apto y sin lesiones en las ultimas semanas.', negativa: 'Historial de ausencias. Ha perdido partidos por lesion o sancion recientemente.' },

  creativity_index: { positiva: 'Alto indice de creatividad. Combina pases precisos y regates para crear juego.', negativa: 'Bajo indice de creatividad. Escasa inventiva y poca generacion de ocasiones.' },
  availability_threat: { positiva: 'Disponible y peligroso. Sin lesiones y generando ocasiones de gol.', negativa: 'Dudas de disponibilidad o con poca peligrosidad ofensiva.' },
  goal_productivity: { positiva: 'Alta productividad goleadora. Combina tiros, xG y precision de forma eficiente.', negativa: 'Baja productividad goleadora. No convierte ni genera suficiente peligro de gol.' },
  es_mediocampista_elite: { positiva: 'Mediocampista de elite. Sus metricas de pase y control estan al maximo nivel.', negativa: 'Por debajo del nivel elite en el mediocampo. Metricas por debajo de la media.' },
  tiene_rol_mediocampista_core: { positiva: 'Mediocentro titular. Ocupa el rol central del mediocampo con continuidad.', negativa: 'Fuera del centro del juego. No ocupa el eje del mediocampo habitualmente.' },
}

export function getFeatureImpactValue(featureImpact) {
  const rawValue = featureImpact?.impacto_pts ?? featureImpact?.impacto ?? 0
  const parsed = Number(rawValue)
  return Number.isFinite(parsed) ? parsed : 0
}

function resolveMappedExplanation(featureName, isPositive) {
  const direct = FEATURE_EXPLANATIONS[featureName]
  if (direct) {
    return isPositive ? direct.positiva : direct.negativa
  }

  const baseFeature = String(featureName || '').replace(/_(roll|ewma)\d+$/, '')
  if (baseFeature && baseFeature !== featureName) {
    const alternativeKey = Object.keys(FEATURE_EXPLANATIONS).find((key) => {
      const normalizedKey = key.replace(/_(roll|ewma)\d+$/, '')
      return normalizedKey !== key && normalizedKey === baseFeature
    })

    if (alternativeKey) {
      const mapped = FEATURE_EXPLANATIONS[alternativeKey]
      return isPositive ? mapped.positiva : mapped.negativa
    }
  }

  return null
}

export function getFeatureExplanation(featureImpact, isPositive) {
  const mapped = resolveMappedExplanation(featureImpact?.feature, isPositive)
  if (mapped) {
    return mapped
  }

  const backendText = isPositive ? featureImpact?.explicacion_positiva : featureImpact?.explicacion_negativa
  if (typeof backendText === 'string' && backendText && !backendText.startsWith('Factor:')) {
    return backendText
  }

  if (typeof featureImpact?.explicacion === 'string' && featureImpact.explicacion && !featureImpact.explicacion.startsWith('Factor:')) {
    return featureImpact.explicacion
  }

  return featureImpact?.feature || 'Factor no disponible'
}

export function buildSignedFeatureRows(featureImpacts, isPositive, count = 3) {
  const impacts = Array.isArray(featureImpacts) ? featureImpacts : []
  const selected = impacts
    .filter((item) => {
      const value = getFeatureImpactValue(item)
      return isPositive ? value > 0 : value < 0
    })
    .sort((a, b) => Math.abs(getFeatureImpactValue(b)) - Math.abs(getFeatureImpactValue(a)))
    .slice(0, count)
    .map((item) => ({
      label: getFeatureExplanation(item, isPositive),
      impact: getFeatureImpactValue(item),
      isPlaceholder: false,
    }))

  const placeholderText = isPositive
    ? 'Sin senal positiva adicional del modelo'
    : 'Sin senal negativa adicional del modelo'

  while (selected.length < count) {
    selected.push({
      label: placeholderText,
      impact: 0,
      isPlaceholder: true,
    })
  }

  return selected
}

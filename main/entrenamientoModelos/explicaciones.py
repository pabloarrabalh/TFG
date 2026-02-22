"""
Módulo de Explicaciones XAI para todas las posiciones
=====================================================
Define explicaciones para Defensas, Mediocentros y Delanteros
"""

# ============================================================================
# DEFENSAS (DF)
# ============================================================================

EXPLICACIONES_DF = {
    'tackles_roll5': {
        'positivo': '📈 Hace muchas entradas defensivas',
        'negativo': '📉 Hace pocas entradas',
    },
    'tackles_ewma5': {
        'positivo': '📈 Entra con consistencia',
        'negativo': '📉 Sus entradas son inconsistentes',
    },
    'intercepts_roll5': {
        'positivo': '📈 Intercepta muchos balones',
        'negativo': '📉 Intercepta pocos balones',
    },
    'intercepts_ewma5': {
        'positivo': '📈 Está atento al juego',
        'negativo': '📉 Pierde concentración',
    },
    'clearances_roll5': {
        'positivo': '📈 Despeja bien el balón',
        'negativo': '📉 Falla en los despejes',
    },
    'clearances_ewma5': {
        'positivo': '📈 Tiene buen juego aéreo',
        'negativo': '📉 Débil en juego aéreo',
    },
    'duels_roll5': {
        'positivo': '📈 Disputa muchos duelos',
        'negativo': '📉 Evita los duelos',
    },
    'duels_ewma5': {
        'positivo': '📈 Gana duelos con frecuencia',
        'negativo': '📉 Pierde duelos',
    },
    'duels_won_roll5': {
        'positivo': '📈 Gana la mayoría de duelos',
        'negativo': '📉 Pierde duelos importantes',
    },
    'duels_won_ewma5': {
        'positivo': '📈 Es muy ganador aéreo',
        'negativo': '📉 Débil en los duelos',
    },
    'aerial_duels_roll5': {
        'positivo': '📈 Fuerte en el juego aéreo',
        'negativo': '📉 Débil en balones aéreos',
    },
    'aerial_won_roll5': {
        'positivo': '📈 Domina el área aérea',
        'negativo': '📉 Da ventaja aérea',
    },
    'pf_roll5': {
        'positivo': '📈 Ha tenido buenas actuaciones',
        'negativo': '📉 Ha tenido malas actuaciones',
    },
    'pf_ewma5': {
        'positivo': '📈 Está en buen momento defensivo',
        'negativo': '📉 Está en baja forma',
    },
    'minutes_pct_roll5': {
        'positivo': '📈 Es titular y juega siempre',
        'negativo': '📉 No juega mucho',
    },
    'minutes_pct_ewma5': {
        'positivo': '📈 Tiene continuidad en el equipo',
        'negativo': '📉 Pierde minutos',
    },
    'cs_probability': {
        'positivo': '📈 Probable que no encaje goles',
        'negativo': '📉 Su portería puede ser vulnerable',
    },
    'availability_threat': {
        'positivo': '📈 Participa activamente en defensa',
        'negativo': '📉 No está siendo determinante',
    },
    'is_home': {
        'positivo': '📈 Juega en casa',
        'negativo': '📉 Juega fuera de casa',
    },
    'num_roles': {
        'positivo': '📈 Tiene múltiples roles catalogados',
        'negativo': '📉 No tiene roles destacables',
    },
}

# ============================================================================
# MEDIOCENTROS (MC)
# ============================================================================

EXPLICACIONES_MC = {
    'pass_efficiency': {
        'positivo': '📈 Pasa muy bien el balón',
        'negativo': '📉 Falla en sus pases',
    },
    'passes_roll5': {
        'positivo': '📈 Da muchos pases por partido',
        'negativo': '📉 Participa poco en el juego',
    },
    'pass_pct_roll5': {
        'positivo': '📈 Completa la mayoría de pases',
        'negativo': '📉 Falla muchos pases',
    },
    'regates_roll5': {
        'positivo': '📈 Intenta regates frecuentemente',
        'negativo': '📉 Juega más directo',
    },
    'succ_dribbles_roll5': {
        'positivo': '📈 Regatea con éxito',
        'negativo': '📉 Falla en sus regates',
    },
    'prog_dribbles_roll5': {
        'positivo': '📈 Avanza el balón con regates',
        'negativo': '📉 No genera peligro progresista',
    },
    'conducciones_roll5': {
        'positivo': '📈 Controla bien el balón',
        'negativo': '📉 Pierde el balón fácilmente',
    },
    'pf_roll5': {
        'positivo': '📈 Está jugando con consistencia',
        'negativo': '📉 Ha rendido poco',
    },
    'pf_ewma5': {
        'positivo': '📈 Es en buen momento ofensivamente',
        'negativo': '📉 Está con baja forma',
    },
    'minutes_pct_roll5': {
        'positivo': '📈 Es siempre titular',
        'negativo': '📉 Pierde minutos',
    },
    'minutes_pct_ewma5': {
        'positivo': '📈 Tiene continuidad',
        'negativo': '📉 No tiene regularidad',
    },
    'tackles_roll5': {
        'positivo': '📈 Ayuda en defensa',
        'negativo': '📉 No recupera balones',
    },
    'intercepts_roll5': {
        'positivo': '📈 Lee bien el juego defensivo',
        'negativo': '📉 Pierde posición defensiva',
    },
    'dribble_success_rate': {
        'positivo': '📈 Supera rivales frecuentemente',
        'negativo': '📉 No desactiva defensas',
    },
    'defensive_participation': {
        'positivo': '📈 Equilibra juego ofensivo-defensivo',
        'negativo': '📉 No ayuda en defensa',
    },
    'availability_form': {
        'positivo': '📈 Juega mucho con buena forma',
        'negativo': '📉 Tiene baja actividad o forma',
    },
    'is_home': {
        'positivo': '📈 Juega en su estadio',
        'negativo': '📉 Juega fuera de casa',
    },
    'num_roles': {
        'positivo': '📈 Tiene múltiples contribuciones',
        'negativo': '📉 Tiene rol limitado',
    },
}

# ============================================================================
# DELANTEROS (DT)
# ============================================================================

EXPLICACIONES_DT = {
    'goals_roll5': {
        'positivo': '📈 Está metiendo goles',
        'negativo': '📉 No marca goles',
    },
    'goals_ewma5': {
        'positivo': '📈 Mantiene consistencia goleadora',
        'negativo': '📉 Falta en efectividad',
    },
    'xg_roll5': {
        'positivo': '📈 Genera oportunidades claras',
        'negativo': '📉 No crea peligro',
    },
    'xg_ewma5': {
        'positivo': '📈 Está en zona de peligro',
        'negativo': '📉 Se aleja de área de gol',
    },
    'shots_roll5': {
        'positivo': '📈 Intenta mucho a puerta',
        'negativo': '📉 Poco peligroso',
    },
    'shots_on_target_roll5': {
        'positivo': '📈 Tira bien a puerta',
        'negativo': '📉 Desperdicia chances',
    },
    'dribbles_roll5': {
        'positivo': '📈 Regatea mucho a defensas',
        'negativo': '📉 Juega más directo',
    },
    'succ_dribbles_roll5': {
        'positivo': '📈 Supera defensas con éxito',
        'negativo': '📉 Pierde balones',
    },
    'prog_dribbles_roll5': {
        'positivo': '📈 Avanza hacia portería',
        'negativo': '📉 No genera progresión',
    },
    'prog_dist_roll5': {
        'positivo': '📈 Gana metros hacia meta',
        'negativo': '📉 Juega lejos del área',
    },
    'key_passes_roll5': {
        'positivo': '📈 Asiste a compañeros',
        'negativo': '📉 No crea para otros',
    },
    'pf_roll5': {
        'positivo': '📈 Tiene buenas actuaciones',
        'negativo': '📉 Ha rendido poco',
    },
    'pf_ewma5': {
        'positivo': '📈 Está en excelente forma',
        'negativo': '📉 Está en baja forma',
    },
    'minutes_pct_roll5': {
        'positivo': '📈 Juega todos los minutos',
        'negativo': '📉 Entra desde el banquillo',
    },
    'minutes_pct_ewma5': {
        'positivo': '📈 Tiene continuidad en el once',
        'negativo': '📉 Pierde protagonismo',
    },
    'shot_efficiency': {
        'positivo': '📈 Aprovecha sus chances',
        'negativo': '📉 Desperdicia oportunidades',
    },
    'shot_accuracy': {
        'positivo': '📈 Tira con precisión',
        'negativo': '📉 Falla en puntería',
    },
    'offensive_threat': {
        'positivo': '📈 Es muy peligroso en ataque',
        'negativo': '📉 No genera peligro',
    },
    'creative_index': {
        'positivo': '📈 Crea peligro para equipo',
        'negativo': '📉 Juega poco creativo',
    },
    'goal_productivity': {
        'positivo': '📈 Eficiente en goles',
        'negativo': '📉 Poco productivo',
    },
    'availability_threat': {
        'positivo': '📈 Activo y peligroso',
        'negativo': '📉 No es determinante',
    },
    'is_home': {
        'positivo': '📈 Juega en casa',
        'negativo': '📉 Juega fuera',
    },
    'num_roles': {
        'positivo': '📈 Versátil ofensivamente',
        'negativo': '📉 Rol muy específico',
    },
}


def obtener_explicacion_posicion(feature_name, es_positivo, posicion):
    """
    Retorna explicación para cualquier posición
    
    Args:
        feature_name: Nombre del feature
        es_positivo: Si el impacto SHAP es positivo
        posicion: 'PT', 'DF', 'MC', 'DT'
    
    Returns:
        str: Explicación del feature
    """
    posicion = posicion.upper() if posicion else 'DT'
    
    if posicion == 'PT':
        from explicaciones_gk import EXPLICACIONES_FEATURES
        explicaciones_dict = EXPLICACIONES_FEATURES
    elif posicion == 'DF':
        explicaciones_dict = EXPLICACIONES_DF
    elif posicion == 'MC':
        explicaciones_dict = EXPLICACIONES_MC
    else:  # DT o default
        explicaciones_dict = EXPLICACIONES_DT
    
    if not isinstance(feature_name, str):
        feature_name = str(feature_name)
    
    if feature_name not in explicaciones_dict:
        return f"Factor: {feature_name}"
    
    explicaciones = explicaciones_dict[feature_name]
    
    if not isinstance(explicaciones, dict):
        return f"Factor: {feature_name}"
    
    clave = 'positivo' if es_positivo else 'negativo'
    return explicaciones.get(clave, f"Factor: {feature_name}")

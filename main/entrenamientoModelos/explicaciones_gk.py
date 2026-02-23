"""
Módulo de Explicaciones XAI para Porteros
==========================================
Define las frases de explicación para cada feature según su impacto (positivo/negativo)
"""

EXPLICACIONES_FEATURES = {
    'pass_comp_pct_ewma5': {
        'positivo': '✅ Excelente con los pies! Completa casi todos sus pases de salida',
        'negativo': '❌ Impreciso en la salida, sus pases generan peligro',
    },
    'total_strength': {
        'positivo': '🛡️ Defensa del equipo muy fuerte! Sus defensores lo protegen bien',
        'negativo': '⚠️ Defensa débil, el rival genera muchas ocasiones',
    },
    'pf_ewma5': {
        'positivo': '⭐ Performance excelente! Ha tenido defensas brillantes recientemente',
        'negativo': '📉 Performance baja, defensas mediocres en los últimos partidos',
    },
    'psxg_ewma5': {
        'positivo': '🎯 Rivales poco peligrosos! No genera muchas ocasiones esperadas',
        'negativo': '💥 Rivales muy peligrosos, generan muchas ocasiones de gol',
    },
    'availability_form': {
        'positivo': '💪 Disponible y en forma! Sin lesiones y al 100% de su capacidad',
        'negativo': '🤕 Tiene molestias o viene con baja forma',
    },
    'pass_comp_pct_roll5': {
        'positivo': '🎮 Últimamente pasa muy bien! Alta precisión en sus últimos partidos',
        'negativo': '😟 Sus pases han fallado últimamente, imprecisión en salida',
    },
    'weak_opponent': {
        'positivo': '🎁 Rival débil en ataque! Poca peligrosidad en ataque',
        'negativo': '🔥 Rival muy ofensivo! Ataca frecuentemente y con peligro',
    },
    'defensive_combo': {
        'positivo': '🛡️ Defensa en buen momento! Equipo defensivamente sólido',
        'negativo': '⚡ Defensa vulnerable! Equipo defendiendo con dificultad',
    },
    'save_advantage': {
        'positivo': '🧤 Salvadas en alza! Está parando más de lo normal',
        'negativo': '😔 Menos salvadas, se le escapan más balones',
    },
    'momentum_factor': {
        'positivo': '🚀 Equipo con buena racha! Victorias recientes dan confianza',
        'negativo': '📉 Equipo en mala racha! Derrotas recientes bajan la moral',
    },
    'minutes_form_combo': {
        'positivo': '⛹️ Regula bastante y está en forma! Minutos importantes con buen nivel',
        'negativo': '⏸️ Poco tiempo o baja forma, no está al 100%',
    },
    'psxg_roll5': {
        'positivo': '💪 Rivales imprecisos! No tiran bien contra él, poco peligro',
        'negativo': '🎯 Rivales potentes! Tiran con precisión y peligro',
    },
    'score_roles_normalizado': {
        'positivo': '⭐ Sus actuaciones son reconocidas! Bonificaciones y bien valorado',
        'negativo': '😞 Sus actuaciones no son reconocidas, sin bonificaciones',
    },
    'pf_roll5': {
        'positivo': '🌟 Defensas excelentes! Últimos partidos han sido Outstanding',
        'negativo': '😰 Defensas pobres! Ha cometido errores en los últimos partidos',
    },
    'odds_expected_goals_against': {
        'positivo': '📊 Mercado: pocos goles! Apostadores creen que encajará pocos',
        'negativo': '⚠️ Mercado: muchos goles! Alto xGA según los pronósticos',
    },
    'odds_market_confidence': {
        'positivo': '📈 Mercado confiado! Pronósticos claros, poca variancia',
        'negativo': '❓ Mercado dubitativo! Cuotas altas, incertidumbre',
    },
    'goles_contra_roll5': {
        'positivo': '🎉 Poco encajador! Ha permitido pocos goles últimamente',
        'negativo': '💔 Encajando mucho! Ha recibido muchos goles recientemente',
    },
    'num_roles_criticos': {
        'positivo': '🏆 Muchas actuaciones clave! Ha sido decisivo en 3-4 partidos',
        'negativo': '👿 Sin actuaciones clave! Ha estado invisible en los últimos matches',
    },
    'minutes_pct_ewma5': {
        'positivo': '👑 Portero titular! Siempre juega, no tiene competencia',
        'negativo': '🔄 Poco tiempo o suplente! Comparte titularidad',
    },
    'ratio_roles_positivos': {
        'positivo': '✨ La mayoría de sus actuaciones son positivas! Consistencia',
        'negativo': '❌ Pocas actuaciones positivas, muchos errores',
    },
    'num_roles_positivos': {
        'positivo': '🎯 Muchas actuaciones buenas! Está siendo productivo',
        'negativo': '😟 Pocas actuaciones positivas, poco aporte en los buenos',
    },
    'is_home': {
        'positivo': '🏠 En su estadio! Ventaja clara, conoce el terreno',
        'negativo': '🚌 Fuera de estadio! Ambiente hostil y viaje cansador',
    },
    'minutes_pct_roll5': {
        'positivo': '⏰ Jugando todos los minutos! Incontestable',
        'negativo': '⏸️ Poco tiempo de juego! Rotación o lesión',
    },
    'starter_pct_roll5': {
        'positivo': '👑 Claramente el titular! Confianza del entrenador',
        'negativo': '⚠️ Podría perder la titularidad! Competen por el puesto',
    },
    'cs_probability': {
        'positivo': '🎪 Porcentaje de no encajar! Muy probable la portería a cero',
        'negativo': '❌ Acabará encajando! Pocas opciones de no encajar',
    },
    'expected_gk_core_points': {
        'positivo': '📊 Valoración esperada alta! Debería tener buen partido',
        'negativo': '📈 Valoración baja esperada! Difícilmente los puntos',
    },
    'cs_expected_points': {
        'positivo': '🛡️ Gran chance de portería a cero! Defensa sólida',
        'negativo': '💥 Rival peligroso! Difícil evitar encajar',
    },
}


def es_valor_alto(feature_name, valor):
    """
    Determina si un valor de feature es considerado "alto".
    
    Args:
        feature_name: Nombre del feature
        valor: Valor numérico del feature
    
    Returns:
        bool: True si es alto, False si es bajo
    """
    if feature_name == 'num_roles_criticos':
        # 0-4 roles: >= 3 es alto, <= 1 es bajo
        return valor >= 3
    elif feature_name == 'num_roles_positivos':
        # Cualquier cantidad > 0 es bueno
        return valor >= 1
    elif feature_name == 'ratio_roles_positivos':
        # Proporción: >= 0.5 es alto
        return valor >= 0.5
    elif feature_name == 'is_home':
        # Jugador en casa: 1 es alto, 0 es bajo
        return valor > 0.5
    elif feature_name in ['goles_contra_roll5']:
        # A menos goles, mejor (bajo es bueno)
        return valor > 0.5
    else:
        # Para features normalizadas (0-1) o similares
        return valor > 0.6


def obtener_explicacion(feature_name, es_positivo):
    """
    Retorna la frase de explicación para un feature según su impacto (positivo/negativo).
    
    Args:
        feature_name: Nombre del feature (ej: 'pass_comp_pct_ewma5')
        es_positivo: Boolean indicando si el IMPACTO SHAP es positivo
    
    Returns:
        str: Frase de explicación o feature_name si no existe
    """
    # Manejar casos donde feature_name podría no ser un string
    if not isinstance(feature_name, str):
        feature_name = str(feature_name)
    
    if feature_name not in EXPLICACIONES_FEATURES:
        return f"Factor: {feature_name}"
    
    explicaciones_dict = EXPLICACIONES_FEATURES[feature_name]
    
    # Asegurar que explicaciones_dict es realmente un diccionario
    if not isinstance(explicaciones_dict, dict):
        return f"Factor: {feature_name}"
    
    clave = 'positivo' if es_positivo else 'negativo'
    return explicaciones_dict.get(clave, f"Factor: {feature_name}")

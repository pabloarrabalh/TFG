"""
Módulo de Explicaciones XAI para Porteros
==========================================
Define las frases de explicación para cada feature según su impacto (positivo/negativo)
"""

EXPLICACIONES_FEATURES = {
    'pass_comp_pct_ewma5': {
        'positivo': '📈 Pasa bien el balón con precisión',
        'negativo': '📉 Falla en sus pases',
    },
    'total_strength': {
        'positivo': '📈 El equipo defiende muy bien',
        'negativo': '📉 La defensa del equipo es débil',
    },
    'pf_ewma5': {
        'positivo': '📈 Ha actuado muy bien en defensa recientemente',
        'negativo': '📉 Sus defensas no han sido buenas últimamente',
    },
    'psxg_ewma5': {
        'positivo': '📈 Enfrenta rivales que no tiran bien',
        'negativo': '📉 Enfrenta rivales que tiran mucho',
    },
    'availability_form': {
        'positivo': '📈 Está disponible y en buen momento',
        'negativo': '📉 Tiene molestias o está con baja forma',
    },
    'pass_comp_pct_roll5': {
        'positivo': '📈 Últimamente pasa bien el balón',
        'negativo': '📉 Últimamente sus pases fallan',
    },
    'weak_opponent': {
        'positivo': '📈 El rival es débil en ataque',
        'negativo': '📉 El rival ataca muy fuerte',
    },
    'defensive_combo': {
        'positivo': '📈 La defensa está en buen momento',
        'negativo': '📉 La defensa está frágil',
    },
    'save_advantage': {
        'positivo': '📈 Está salvando más paradas de lo normal',
        'negativo': '📉 Está salvando menos paradas de lo normal',
    },
    'momentum_factor': {
        'positivo': '📈 Su equipo está con buena racha',
        'negativo': '📉 Su equipo está en mala racha',
    },
    'minutes_form_combo': {
        'positivo': '📈 Juega bastante y está en forma',
        'negativo': '📉 Juega poco o está con baja forma',
    },
    'psxg_roll5': {
        'positivo': '📈 Los rivales no tiran bien contra él',
        'negativo': '📉 Los rivales están tirando bien contra él',
    },
    'score_roles_normalizado': {
        'positivo': '📈 Sus buenas actuaciones están siendo reconocidas',
        'negativo': '📉 Sus actuaciones no están siendo reconocidas',
    },
    'pf_roll5': {
        'positivo': '📈 Ha tenido partidos defensivos excelentes',
        'negativo': '📉 Ha tenido partidos defendiendo mal',
    },
    'odds_expected_goals_against': {
        'positivo': '📈 Los apostadores creen que encajará pocos goles',
        'negativo': '📉 Los apostadores creen que encajará muchos goles',
    },
    'odds_market_confidence': {
        'positivo': '📈 El mercado tiene claro cómo saldrá el partido',
        'negativo': '📉 El mercado duda del resultado',
    },
    'goles_contra_roll5': {
        'positivo': '📈 Ha encajado pocos goles últimamente',
        'negativo': '📉 Ha encajado muchos goles últimamente',
    },
    'num_roles_criticos': {
        'positivo': '📈 Tiene muchas actuaciones clave destacables (3-4)',
        'negativo': '📉 No tiene actuaciones clave destacables (0-1)',
    },
    'minutes_pct_ewma5': {
        'positivo': '📈 Es el portero titular y siempre juega',
        'negativo': '📉 No juega mucho o es suplente',
    },
    'ratio_roles_positivos': {
        'positivo': '📈 La mayoría de sus actuaciones clave son positivas',
        'negativo': '📉 Sus actuaciones clave no son positivas',
    },
    'num_roles_positivos': {
        'positivo': '📈 Tiene muchas actuaciones clave buenas',
        'negativo': '📉 No tiene actuaciones clave buenas',
    },
    'is_home': {
        'positivo': '📈 Juega en su estadio (ventaja)',
        'negativo': '📉 Juega fuera de casa',
    },
    'minutes_pct_roll5': {
        'positivo': '📈 Juega todos los minutos',
        'negativo': '📉 Juega poco tiempo',
    },
    'starter_pct_roll5': {
        'positivo': '📈 Es el portero titular',
        'negativo': '📉 Podría perder la titularidad',
    },
    'cs_probability': {
        'positivo': '📈 Muy probable que no encaje goles',
        'negativo': '📉 Probable que encaje goles',
    },
    'expected_gk_core_points': {
        'positivo': '📈 Se espera que tenga un buen partido',
        'negativo': '📉 Se espera que no tenga un buen partido',
    },
    'cs_expected_points': {
        'positivo': '📈 Buenas opciones de no encajar goles',
        'negativo': '📉 El rival ataca muy fuerte',
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

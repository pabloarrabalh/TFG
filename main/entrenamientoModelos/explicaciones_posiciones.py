"""
Módulo de Explicaciones Genéricas para Defensas, Mediocampistas y Delanteros
==============================================================================
Define frases de explicación para features según su impacto
"""

# Explicaciones genéricas para diferentes positions
EXPLICACIONES_FEATURES_DF = {
    'tackles_roll5': {'alto': '📈 Ha hecho muchas entradas', 'bajo': '📉 Pocas entradas recientes'},
    'intercepts_roll5': {'alto': '📈 Muchas intercepciones', 'bajo': '📉 Pocas intercepciones'},
    'duels_roll5': {'alto': '📈 Muy participativo en duelos', 'bajo': '📉 Poco participativo'},
    'clearances_roll5': {'alto': '📈 Muchos despejes defensivos', 'bajo': '📉 Pocos despejes'},
    'defensive_actions_total': {'alto': '📈 Muchas acciones defensivas', 'bajo': '📉 Pocas acciones defensivas'},
    'is_home': {'alto': '📈 Juega en su estadio', 'bajo': '📉 Juega fuera de casa'},
    'minutes_pct_roll5': {'alto': '📈 Juega muchos minutos', 'bajo': '📉 Juega poco tiempo'},
}

EXPLICACIONES_FEATURES_MC = {
    'passes_roll5': {'alto': '📈 Muchos pases completados', 'bajo': '📉 Pocos pases'},
    'pass_comp_pct_roll5': {'alto': '📈 Muy buena precisión de pases', 'bajo': '📉 Baja precisión de pases'},
    'dribbles_roll5': {'alto': '📈 Muchos regates completados', 'bajo': '📉 Pocos regates'},
    'tackles_roll5': {'alto': '📈 Contribuye en defensa', 'bajo': '📉 Poco aporte defensivo'},
    'key_passes_roll5': {'alto': '📈 Muchos pases clave', 'bajo': '📉 Pocos pases clave'},
    'is_home': {'alto': '📈 Juega en su estadio', 'bajo': '📉 Juega fuera de casa'},
    'minutes_pct_roll5': {'alto': '📈 Juega muchos minutos', 'bajo': '📉 Juega poco tiempo'},
}

EXPLICACIONES_FEATURES_DT = {
    'goals_roll5': {'alto': '📈 Goles recientes', 'bajo': '📉 Sin goles recientes'},
    'xg_roll5': {'alto': '📈 Espera buenos disparos', 'bajo': '📉 Pocas oportunidades esperadas'},
    'shots_roll5': {'alto': '📈 Muchos disparos', 'bajo': '📉 Pocos disparos'},
    'shots_on_target_roll5': {'alto': '📈 Precisión en disparo', 'bajo': '📉 Baja precisión'},
    'dribbles_roll5': {'alto': '📈 Muchos regates', 'bajo': '📉 Pocos regates'},
    'key_passes_roll5': {'alto': '📈 Contribuye con asistencias', 'bajo': '📉 Pocas asistencias'},
    'is_home': {'alto': '📈 Juega en su estadio', 'bajo': '📉 Juega fuera de casa'},
    'minutes_pct_roll5': {'alto': '📈 Juega todos los minutos', 'bajo': '📉 Juega poco tiempo'},
}


def obtener_explicacion_simple(feature_name, es_alto, pos_dict):
    """
    Obtiene explicación simple para un feature.
    
    Args:
        feature_name: Nombre del feature
        es_alto: True si el valor es "alto", False si es bajo
        pos_dict: Diccionario de explicaciones para la posición
    
    Returns:
        str: Explicación del feature
    """
    if feature_name not in pos_dict:
        return f"Factor: {feature_name}"
    
    clave = 'alto' if es_alto else 'bajo'
    return pos_dict[feature_name].get(clave, f"Factor: {feature_name}")


def generar_explicaciones_features(features_dict, feature_names, posicion='DF', modelo=None, prediccion_base=5.0):
    """
    Genera explicaciones con impacto numérico en puntos fantasy.
    
    Args:
        features_dict: Diccionario con valores de features
        feature_names: Lista de nombres de features en orden
        posicion: Posición del jugador ('DF', 'MC', 'DT')
        modelo: Modelo RF para extraer feature importances (opcional)
        prediccion_base: Predicción base para calcular impactos
    
    Returns:
        dict: {'features_impacto': [...], 'explicacion_texto': str}
    """
    if posicion == 'DF':
        pos_dict = EXPLICACIONES_FEATURES_DF
    elif posicion == 'MC':
        pos_dict = EXPLICACIONES_FEATURES_MC
    elif posicion == 'DT':
        pos_dict = EXPLICACIONES_FEATURES_DT
    else:
        pos_dict = {}
    
    features_impacto = []
    explicacion_lines = []
    
    # Calcular impactos para cada feature
    feature_impacts = []
    for fname in feature_names:
        if fname in features_dict:
            valor = float(features_dict[fname])
            
            # Impacto: usar absoluto del valor (más alto = más impacto)
            # Normalizar según el tipo de feature
            if 'pct' in fname or 'ratio' in fname:
                # Porcentaje: 0-1 o 0-100
                # Si es 0-1, usar tal cual; si es 0-100, dividir entre 10
                if valor <= 1:
                    impacto_pts = abs(valor) * 2.0  # 0-1 -> 0-2
                else:
                    impacto_pts = abs(valor) / 50.0  # 0-100 -> 0-2
            else:
                # Para conteos, valor / 10 pero más conservador
                impacto_pts = min(abs(valor) / 15.0, 2.0)  # Máximo 2pts
            
            # Determinar si es positivo o negativo basado en el valor
            threshold = 0.5 if ('pct' in fname or 'ratio' in fname) else 1.0
            es_alto = valor > threshold
            
            # El signo del impacto depende de si es "alto" o "bajo"
            signo_impacto = 1 if es_alto else -1
            impacto_pts_signed = impacto_pts * signo_impacto
            
            feature_impacts.append({
                'feature': fname,
                'valor': valor,
                'impacto_pts': impacto_pts_signed,
                'es_alto': es_alto
            })
    
    # Top 7 features por impacto absoluto
    feature_impacts.sort(key=lambda x: abs(x['impacto_pts']), reverse=True)
    top_features = feature_impacts[:7]
    
    explicacion_lines.append("Factores principales:")
    explicacion_lines.append("")
    
    for idx, feat in enumerate(top_features, 1):
        fname = feat['feature']
        valor = feat['valor']
        impacto_pts = feat['impacto_pts']
        es_alto = feat['es_alto']
        
        explicacion_texto = obtener_explicacion_simple(fname, es_alto, pos_dict)
        
        # Generar línea con SOLO impacto (sin valor)
        signo = '+' if impacto_pts > 0 else '-' if impacto_pts < 0 else ''
        impacto_abs = abs(impacto_pts)
        linea = f"{idx}. {explicacion_texto} (impacto: {signo}{impacto_abs:.2f}pts)"
        explicacion_lines.append(linea)
        
        features_impacto.append({
            'feature': fname,
            'impacto': impacto_pts,
            'impacto_pts': impacto_pts,
            'direccion': 'positivo' if impacto_pts > 0 else 'negativo' if impacto_pts < 0 else 'neutro',
            'explicacion': explicacion_texto
        })
    
    explicacion_texto = "\n".join(explicacion_lines)
    
    return {
        'features_impacto': features_impacto,
        'explicacion_texto': explicacion_texto
    }

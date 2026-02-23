"""
Módulo de Explicaciones Genéricas para Defensas, Mediocampistas y Delanteros
==============================================================================
Define frases de explicación para features según su impacto
"""

# Explicaciones detalladas para defensas
EXPLICACIONES_FEATURES_DF = {
    'tackles_roll5': {
        'alto': '💪 Está muy activo defensivamente! Ha hecho muchas entradas y recuperaciones en los últimos partidos',
        'bajo': '⚠️ Ha estado poco activo en las recuperaciones defensivas recientemente'
    },
    'intercepts_roll5': {
        'alto': '🎯 Excelente lectura defensiva! Anticipa bien los pases del rival y roba balones',
        'bajo': '👀 No está leyendo bien el juego defensivo, se le escapan muchos balones'
    },
    'duels_roll5': {
        'alto': '🥊 Es muy competitivo! Gana la mayoría de sus duelos aéreos y terrestres',
        'bajo': '😟 Le cuesta ganar los duelos, está perdiendo muchas disputas de balón'
    },
    'clearances_roll5': {
        'alto': '🚀 Despejes seguros! Es efectivo sacando el balón del área de peligro',
        'bajo': '❌ Sus despejes no son efectivos, deja el balón cerca del área'
    },
    'defensive_actions_total': {
        'alto': '🛡️ Defensivamente es un roca! Realiza muchas acciones defensivas por partido',
        'bajo': '😴 Poco activo defensivamente, hace pocas acciones de recuperación'
    },
    'is_home': {
        'alto': '🏠 Juega en su estadio! Ventaja clara, mejor ambiente y conocimiento del terreno',
        'bajo': '🚌 Juega fuera de casa, terreno desconocido y menos apoyo'
    },
    'minutes_pct_roll5': {
        'alto': '⏱️ Es indiscutible! Juega prácticamente todos los minutos disponibles',
        'bajo': '🔄 Está compartiendo titularidad o viene con poca participación'
    },
}

# Explicaciones detalladas para mediocampistas
EXPLICACIONES_FEATURES_MC = {
    'passes_roll5': {
        'alto': '🎮 Es un controlador del juego! Da muchos pases y domina la posesión',
        'bajo': '🤐 Poco toque de balón, no está implicado mucho en la construcción del juego'
    },
    'pass_comp_pct_roll5': {
        'alto': '✅ Muy preciso en sus pases! Completa un altísimo porcentaje de sus intentos',
        'bajo': '❌ Baja precisión en pases, completa menos del 75% de intentos'
    },
    'dribbles_roll5': {
        'alto': '🏃 Es ágil y dinámico! Completa muchos regates y progresa con el balón',
        'bajo': '🐌 Poco regateador, opta por pasar antes que driblar'
    },
    'tackles_roll5': {
        'alto': '⚔️ Contribuye mucho en defensa! Es un mediocentro completo y equilibrado',
        'bajo': '🚫 No ayuda mucho en defensa, más ofensivo que defensivo'
    },
    'key_passes_roll5': {
        'alto': '👟 Genial pasador! Crea muchas ocasiones claras para sus compañeros',
        'bajo': '😶 Pocas asistencias, no está generando juego ofensivo'
    },
    'is_home': {
        'alto': '🏠 Juega en su estadio! Mayor confianza y ambiente favorable',
        'bajo': '🚌 Juega fuera, ambiente hostil y terreno menos conocido'
    },
    'minutes_pct_roll5': {
        'alto': '⛹️ Es titular indiscutible! Juega casi todos los partidos y minutos',
        'bajo': '⏸️ Poco tiempo de juego, comparte titularidad o está en rotación'
    },
}

# Explicaciones detalladas para delanteros
EXPLICACIONES_FEATURES_DT = {
    'goals_roll5': {
        'alto': '⚡ Está en racha goleadora! Ha marcado recientemente y está muy en forma',
        'bajo': '😞 Sequía de goles, hace tiempo que no marca'
    },
    'xg_roll5': {
        'alto': '🎯 Recibe muchas oportunidades claras! El equipo le genera ocasiones de calidad',
        'bajo': '❌ Pocas oportunidades, no está recibiendo balones en zona de remate'
    },
    'shots_roll5': {
        'alto': '💥 Muy intento en ataque! Tira mucho a puerta e intenta crear oportunidades',
        'bajo': '🚫 Poco intento, no está generando suficientes remates'
    },
    'shots_on_target_roll5': {
        'alto': '🎪 Puntería excelente! Sus disparos van directos a puerta',
        'bajo': '🎲 Poca precisión, muchos disparos fuera u obstruidos'
    },
    'dribbles_roll5': {
        'alto': '🌪️ Es un extremo muy diferencial! Regate y crea espacios con facilidad',
        'bajo': '🚶 No está driblan mucho, prefiere juego más directo'
    },
    'key_passes_roll5': {
        'alto': '🤝 Excelente equipo player! Genera asistencias además de goles',
        'bajo': '🤐 Poco generador, se enfoca solo en el gol personal'
    },
    'is_home': {
        'alto': '🏠 Juega en su estadio! Confianza y apoyo del público',
        'bajo': '🚌 Juega fuera, ambiente más complicado'
    },
    'minutes_pct_roll5': {
        'alto': '🔥 Titularidad asegurada! Juega prácticamente todos los minutos',
        'bajo': '⏱️ Poco tiempo de juego, suplente o en rotación'
    },
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

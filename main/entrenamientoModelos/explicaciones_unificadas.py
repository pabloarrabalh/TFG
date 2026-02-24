EXPLICACIONES_FEATURES = {
    # ============ FEATURES COMUNES ============
    
    'is_home': {
        'positivo': 'Jugador en su estadio.',
        'negativo': 'Jugador fuera de su estadio.'
    },
    
    'minutes_pct_roll5': {
        'positivo': 'Alto porcentaje de minutos jugados en los últimos 5 partidos.',
        'negativo': 'Bajo porcentaje de minutos jugados en los últimos 5 partidos.'
    },
    
    'tackles_roll5': {
        'positivo': 'Muchas entradas y recuperaciones defensivas en los últimos 5 partidos.',
        'negativo': 'Pocas entradas y recuperaciones defensivas en los últimos 5 partidos.'
    },
    
    'dribbles_roll5': {
        'positivo': 'Muchos regates exitosos en los últimos 5 partidos.',
        'negativo': 'Pocos regates o baja tasa de éxito en regates.'
    },
    
    'key_passes_roll5': {
        'positivo': 'Muchos pases decisivos que generan ocasiones de gol en los últimos 5 partidos.',
        'negativo': 'Pocos pases decisivos en los últimos 5 partidos.'
    },
    
    'availability_form': {
        'positivo': 'Jugador disponible y en buena forma física.',
        'negativo': 'Jugador con molestias o en baja forma.'
    },
    
    # ============ FEATURES ESPECÍFICOS DE PORTEROS ============
    
    'pass_comp_pct_ewma5': {
        'positivo': 'Alta precisión en pases últimamente.',
        'negativo': 'Baja precisión en pases (muchos intentos fallidos).'
    },
    
    'total_strength': {
        'positivo': 'Equipo defensivamente fuerte con buen rendimiento colectivo.',
        'negativo': 'Equipo defensivamente débil, vulnerable en defensa.'
    },
    
    'pf_ewma5': {
        'positivo': 'Últimamente está puntuando bien.',
        'negativo': 'No puntúa muy bien últimamente.'
    },
    
    'psxg_ewma5': {
        'positivo': 'Rivales generan pocas ocasiones de gol.',
        'negativo': 'Rivales generan muchas ocasiones de gol.'
    },
    
    'pass_comp_pct_roll5': {
        'positivo': 'Alta precisión en pases en los últimos 5 partidos.',
        'negativo': 'Baja precisión en pases en los últimos 5 partidos.'
    },
    
    'weak_opponent': {
        'positivo': 'Rival débil defensivamente, vulnerable en ataque.',
        'negativo': 'Rival fuerte defensivamente, difícil de atacar.'
    },
    
    'defensive_combo': {
        'positivo': 'Defensa del equipo en buen momento, sólida.',
        'negativo': 'Defensa del equipo vulnerable, inestable.'
    },
    
    'save_advantage': {
        'positivo': 'Ventaja en paradas: portero para más de lo esperado.',
        'negativo': 'Desventaja en paradas: portero para menos de lo esperado.'
    },
    
    'momentum_factor': {
        'positivo': 'Equipo en buena racha reciente.',
        'negativo': 'Equipo en mala racha reciente.'
    },
    
    'minutes_form_combo': {
        'positivo': 'Jugador con minutos de juego y forma física buena.',
        'negativo': 'Jugador con poco tiempo de juego o baja forma.'
    },
    
    'psxg_roll5': {
        'positivo': 'Su rival no ha generado mucho peligro en los últimos 5 partidos.',
        'negativo': 'Su rival viene generando peligro los últimos 5 partido.'
    },
    
    'score_roles_normalizado': {
        'positivo': 'Jugador con top en alguna estadística.',
        'negativo': 'No destaca excepcionalmente en nada.'
    },
    
    'pf_roll5': {
        'positivo': 'Últimamente está puntuando bien.',
        'negativo': 'No puntúa muy bien últimamente.'
    },
    
    'odds_expected_goals_against': {
        'positivo': 'Mercado espera pocos goles en contra.',
        'negativo': 'Mercado espera muchos goles en contra.'
    },
    
    'odds_market_confidence': {
        'positivo': 'Mercado confiado en el resultado (cuotas claras).',
        'negativo': 'Mercado incierto en el resultado (cuotas altas variancia).'
    },
    
    'goles_contra_roll5': {
        'positivo': 'Pocos goles encajados en los últimos 5 partidos.',
        'negativo': 'Muchos goles encajados en los últimos 5 partidos.'
    },
    
    'num_roles_criticos': {
        'positivo': 'Jugador con top en varias estadísticas.',
        'negativo': 'No destaca excepcionalmente en nada o en pocas estadísticas.'
    },
    
    'minutes_pct_ewma5': {
        'positivo': 'Jugador titular con regularidad y continuidad.',
        'negativo': 'Jugador de rotación o suplente.'
    },
    
    'ratio_roles_positivos': {
        'positivo': 'Destaca más por aspectos positvos que negativos.(ratio)',
        'negativo': 'Destaca más por aspectos negativos que positivos.(ratio)'
    },
    
    'num_roles_positivos': {
        'positivo': 'Destaca más por aspectos positvos que negativos.',
        'negativo': 'Destaca más por aspectos negativos que positivos.'
    },
    
    'starter_pct_roll5': {
        'positivo': 'Altos porcentaje de partidos como titular en los últimos 5.',
        'negativo': 'Bajo porcentaje de partidos como titular en los últimos 5.'
    },
    
    'cs_probability': {
        'positivo': 'Alta probabilidad de portería a cero.',
        'negativo': 'Baja probabilidad de portería a cero.'
    },
    
    'expected_gk_core_points': {
        'positivo': 'Valoración esperada alta para el próximo partido.',
        'negativo': 'Valoración esperada baja para el próximo partido.'
    },
    
    'cs_expected_points': {
        'positivo': 'Puntos esperados altos gracias a portería a cero probable.',
        'negativo': 'Pocos puntos esperados por baja probabilidad de CS.'
    },
    
    # ============ FEATURES ESPECÍFICOS DE DEFENSAS ============
    
    'intercepts_roll5': {
        'positivo': 'Muchas interceptaciones en los últimos 5 partidos.',
        'negativo': 'Pocas interceptaciones, mala lectura defensiva.'
    },
    
    'duels_roll5': {
        'positivo': 'Alto porcentaje de duelos ganados.',
        'negativo': 'Bajo porcentaje de duelos ganados.'
    },
    
    'clearances_roll5': {
        'positivo': 'Muchos despejes seguros sacando balón del área de peligro.',
        'negativo': 'Despejes inefectivos o peligrosos, poco seguro.'
    },
    
    'defensive_actions_total': {
        'positivo': 'Muchas acciones defensivas por partido.',
        'negativo': 'Pocas acciones defensivas, pasivo en defensa.'
    },
    
    # ============ FEATURES ESPECÍFICOS DE MEDIOCAMPISTAS ============
    
    'passes_roll5': {
        'positivo': 'Muchos pases completados, alto volumen de toque en los últimos 5.',
        'negativo': 'Pocos pases, bajo volumen de toque, poco implicado.'
    },
    
    # ============ FEATURES ESPECÍFICOS DE DELANTEROS ============
    
    'goals_roll5': {
        'positivo': 'Muchos goles anotados en los últimos 5 partidos.',
        'negativo': 'Pocos goles, sequía ofensiva en los últimos 5 partidos.'
    },
    
    'xg_roll5': {
        'positivo': 'Alto xG esperado, muchas ocasiones claras en los últimos 5.',
        'negativo': 'Bajo xG esperado, pocas ocasiones de gol en los últimos 5.'
    },
    
    'shots_roll5': {
        'positivo': 'Muchos disparos realizados en los últimos 5 partidos.',
        'negativo': 'Pocos disparos, bajo intento ofensivo.'
    },
    
    'shots_on_target_roll5': {
        'positivo': 'Muchos disparos a puerta.',
        'negativo': 'Pocos disparos a puerta, disparos imprecisos.'
    },
}


# ============ FUNCIONES DE UTILIDAD ============

def obtener_explicacion(feature_name, es_positivo):
    if not isinstance(feature_name, str):
        feature_name = str(feature_name)
    
    feature_name = feature_name.strip()
    
    # Verificar que el feature existe en el diccionario
    if feature_name not in EXPLICACIONES_FEATURES:
        return f"Factor: {feature_name}"
    
    feature_dict = EXPLICACIONES_FEATURES[feature_name]
    
    # Seleccionar la clave según interpretación
    clave = 'positivo' if es_positivo else 'negativo'
    
    # Retornar explicación o fallback
    return feature_dict.get(clave, f"Factor: {feature_name}")


def es_valor_alto(feature_name, valor):
    """
    Determina si un valor de feature es considerado "alto" (positivo).
    
    Args:
        feature_name: Nombre del feature
        valor: Valor numérico del feature
    
    Returns:
        bool: True si es alto/positivo, False si es bajo/negativo
    """
    # Lógica simple: si es porcentaje (0-1), threshold es 0.5. Si es contador, threshold es 1.0
    if feature_name == 'num_roles_criticos':
        return valor >= 3
    elif 'pct' in feature_name.lower() or 'ratio' in feature_name.lower():
        return valor > 0.5
    else:
        return valor > 1.0


def preparar_features_para_explicaciones(data):
    if isinstance(data, dict):
        features_list = []
        for feature, valor in data.items():
            if valor is None:
                continue
            try:
                valor_num = float(valor)
            except (ValueError, TypeError):
                continue
            features_list.append({'feature': feature, 'valor': valor_num, 'es_alto': es_valor_alto(feature, valor_num)})
        return features_list
    if isinstance(data, list):
        return data
    return []


def generar_explicaciones_features(features_data):
    """Genera explicaciones para los features de un predictor.

    Args:
        features_data: Lista de dicts con keys: feature, valor, impacto_pts, es_alto

    Returns:
        dict: {
            'features_impacto': [list of dicts with feature, impacto, explicacion],
            'explicacion_texto': str con explicaciones formato texto
        }
    """
    features_impacto = []
    explicacion_lines = []
    
    if not features_data:
        return {
            'features_impacto': [],
            'explicacion_texto': 'Sin datos disponibles'
        }
    
    # Procesar features
    feature_impacts = []
    for feat in features_data:
        if isinstance(feat, dict) and 'feature' in feat:
            fname = feat['feature']
            valor = feat.get('valor', 0)
            impacto_pts = feat.get('impacto_pts', 0)
            es_alto = feat.get('es_alto', valor > 1.0)
            
            # Calcular impacto si no viene
            if impacto_pts == 0 and valor != 0:
                if 'pct' in fname.lower() or 'ratio' in fname.lower():
                    if 0 <= valor <= 1:
                        impacto_pts = abs(valor) * 2.0
                    else:
                        impacto_pts = min(abs(valor) / 50.0, 2.0)
                else:
                    impacto_pts = min(abs(valor) / 15.0, 2.0)
            
            # Signo del impacto
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
        
        # Obtener explicación
        explicacion_texto = obtener_explicacion(fname, es_alto)
        
        # Signo del impacto
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


# Backward compatibility: crear alias de los old dicts
EXPLICACIONES_PORTERO = {feat: data for feat, data in EXPLICACIONES_FEATURES.items()}
EXPLICACIONES_DEFENSA = {feat: data for feat, data in EXPLICACIONES_FEATURES.items()}
EXPLICACIONES_MEDIOCAMPISTA = {feat: data for feat, data in EXPLICACIONES_FEATURES.items()}
EXPLICACIONES_DELANTERO = {feat: data for feat, data in EXPLICACIONES_FEATURES.items()}

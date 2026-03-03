"""
Módulo ÚNICO de Explicaciones XAI para todas las posiciones
============================================================
Contiene todas las explicaciones de features y funciones de utilidad.
Reemplaza: explicaciones_unificadas.py, explicaciones_gk.py, explicaciones_posiciones.py

Uso:
    from explicaciones import obtener_explicacion, generar_explicaciones_features
"""

import numpy as np
import pandas as pd

try:
    import shap as shap_lib
except ImportError:
    shap_lib = None

# =============================================================================
# DICCIONARIO UNIFICADO DE EXPLICACIONES (todas las posiciones)
# Formato: { feature_name: { 'positivo': str, 'negativo': str } }
# =============================================================================

EXPLICACIONES_FEATURES = {

    # ── COMUNES ──────────────────────────────────────────────────────────────

    'is_home': {
        'positivo': 'Juega en su estadio. Ventaja de localía, mejor ambiente y apoyo del público.',
        'negativo': 'Juega fuera de casa. Terreno desconocido y menos apoyo del público.'
    },
    'minutes_pct_roll5': {
        'positivo': 'Titular indiscutible. Está jugando casi todos los minutos disponibles.',
        'negativo': 'Comparte titularidad o le falta continuidad en los últimos 5 partidos.'
    },
    'minutes_pct_ewma5': {
        'positivo': 'Regularidad alta. Titular con continuidad según tendencia reciente.',
        'negativo': 'Rotación frecuente. Tendencia a bajar minutos recientemente.'
    },
    'pf_roll5': {
        'positivo': 'Buena forma. Está puntuando bien en los últimos 5 partidos.',
        'negativo': 'Mala racha. No está puntuando bien en los últimos 5 partidos.'
    },
    'pf_ewma5': {
        'positivo': 'Tendencia ascendente. Su puntuación mejora en las últimas jornadas.',
        'negativo': 'Tendencia bajista. Su puntuación cae en las últimas jornadas.'
    },
    'availability_form': {
        'positivo': 'Disponible y en forma. Sin lesiones y rindiendo a buen nivel.',
        'negativo': 'Posibles molestias o baja forma. No está al 100%.'
    },
    'score_roles_normalizado': {
        'positivo': 'Destaca en alguna estadística. Tiene roles positivos valorados.',
        'negativo': 'No destaca excepcionalmente. Sin roles especiales reconocidos.'
    },
    'num_roles_criticos': {
        'positivo': 'Muchos roles destacados. Jugador muy completo y determinante.',
        'negativo': 'Pocos roles destacados. Sin hitos estadísticos relevantes.'
    },
    'num_roles_positivos': {
        'positivo': 'Muchos roles positivos. Destaca en aspectos beneficiosos.',
        'negativo': 'Pocos roles positivos. Predominan los aspectos negativos.'
    },
    'ratio_roles_positivos': {
        'positivo': 'Alta proporción de roles positivos vs negativos.',
        'negativo': 'Baja proporción de roles positivos, más negativos que positivos.'
    },
    'starter_pct_roll5': {
        'positivo': 'Titular habitual. Alto porcentaje de partidos de inicio en los últimos 5.',
        'negativo': 'Suplente frecuente. Bajo porcentaje como titular en los últimos 5.'
    },
    'tackles_roll5': {
        'positivo': 'Muy activo defensivamente. Muchas entradas y recuperaciones recientes.',
        'negativo': 'Escasa actividad defensiva. Pocas entradas y recuperaciones.'
    },
    'dribbles_roll5': {
        'positivo': 'Regates efectivos. Completa muchos driblins y progresa con el balón.',
        'negativo': 'Pocos regates o baja tasa de éxito. Poco peligro en conducción.'
    },
    'key_passes_roll5': {
        'positivo': 'Gran creador de juego. Muchos pases que generan ocasiones de gol.',
        'negativo': 'Poco generador. Escasos pases clave y poca creatividad.'
    },
    'opp_form_roll5': {
        'positivo': 'Rival en mala racha. El oponente viene con malos resultados recientes.',
        'negativo': 'Rival en buena racha. El oponente viene en gran forma reciente.'
    },
    'opp_form_ewma5': {
        'positivo': 'Rival en tendencia negativa. La forma del rival está bajando.',
        'negativo': 'Rival en tendencia positiva. La forma del rival está subiendo.'
    },
    'opp_gc_roll5': {
        'positivo': 'Rival poroso. El rival encaja muchos goles, facilita marcar y puntuar.',
        'negativo': 'Rival sólido. El rival encaja pocos goles, difícil de superar.'
    },
    'opp_gc_ewma5': {
        'positivo': 'Rival tendencia porosa. Últimamente encaja más goles.',
        'negativo': 'Rival mejorando defensivamente. Encaja cada vez menos.'
    },
    'opp_gf_roll5': {
        'positivo': 'Rival peligroso en ataque. El rival marca muchos goles.',
        'negativo': 'Rival sin gol. El rival anota pocos goles últimamente.'
    },
    'odds_prob_win': {
        'positivo': 'Alta probabilidad de victoria. El mercado favorece a su equipo.',
        'negativo': 'Baja probabilidad de victoria. El mercado favorece al rival.'
    },
    'odds_prob_loss': {
        'positivo': 'Alta probabilidad de derrota del rival.',
        'negativo': 'Alta probabilidad de derrota propia.'
    },
    'odds_expected_goals_against': {
        'positivo': 'Mercado espera pocos goles en contra.',
        'negativo': 'Mercado espera muchos goles en contra.'
    },
    'odds_market_confidence': {
        'positivo': 'Mercado confiado. Las cuotas son claras y favorables.',
        'negativo': 'Mercado incierto. Cuotas muy igualadas o desfavorables.'
    },
    'odds_is_favored': {
        'positivo': 'Su equipo es favorito según las apuestas.',
        'negativo': 'Su equipo no es favorito según las apuestas.'
    },

    # ── PORTERO (PT) ─────────────────────────────────────────────────────────

    'pass_comp_pct_ewma5': {
        'positivo': 'Excelente con los pies. Completa casi todos sus pases de salida.',
        'negativo': 'Impreciso en la salida. Sus pases generan peligro propio.'
    },
    'pass_comp_pct_roll5': {
        'positivo': 'Muy preciso en pases últimamente. Alta precisión en los últimos 5.',
        'negativo': 'Sus pases han fallado últimamente. Imprecisión en la salida.'
    },
    'total_strength': {
        'positivo': 'Equipo defensivamente fuerte. Sus defensores lo protegen bien.',
        'negativo': 'Defensa débil. El rival genera muchas ocasiones de peligro.'
    },
    'psxg_ewma5': {
        'positivo': 'Rivales poco peligrosos. Generan pocas ocasiones esperadas contra él.',
        'negativo': 'Rivales muy peligrosos. Generan muchas ocasiones de gol esperadas.'
    },
    'psxg_roll5': {
        'positivo': 'Rivales imprecisos. No tiran bien contra él, poco peligro reciente.',
        'negativo': 'Rivales potentes. Tiran con precisión y peligro en los últimos 5.'
    },
    'weak_opponent': {
        'positivo': 'Rival débil en ataque. Poca peligrosidad ofensiva del oponente.',
        'negativo': 'Rival muy ofensivo. Ataca frecuentemente y con mucho peligro.'
    },
    'defensive_combo': {
        'positivo': 'Defensa en buen momento. Equipo defensivamente sólido.',
        'negativo': 'Defensa vulnerable. El equipo defiende con muchas dificultades.'
    },
    'save_advantage': {
        'positivo': 'Salvadas en alza. Está parando más de lo que se espera.',
        'negativo': 'Menos salvadas de lo esperado. No detiene bien los tiros.'
    },
    'momentum_factor': {
        'positivo': 'Equipo en buena racha. Victorias recientes generan confianza.',
        'negativo': 'Equipo en mala racha. Derrotas recientes bajan la moral.'
    },
    'minutes_form_combo': {
        'positivo': 'Muchos minutos y en buena forma. Rendimiento alto con continuidad.',
        'negativo': 'Poco tiempo de juego o baja forma. No está al 100%.'
    },
    'cs_probability': {
        'positivo': 'Alta probabilidad de portería a cero. Rival con poco gol.',
        'negativo': 'Baja probabilidad de portería a cero. Rival con mucho gol.'
    },
    'expected_gk_core_points': {
        'positivo': 'Puntuación esperada alta para el próximo partido.',
        'negativo': 'Puntuación esperada baja para el próximo partido.'
    },
    'cs_expected_points': {
        'positivo': 'Puntos esperados altos gracias a portería a cero probable.',
        'negativo': 'Pocos puntos esperados. Baja probabilidad de portería a cero.'
    },
    'goles_contra_roll5': {
        'positivo': 'Pocos goles encajados en los últimos 5 partidos. Defensa sólida.',
        'negativo': 'Muchos goles encajados en los últimos 5 partidos. Defensa porosa.'
    },
    'save_pct_roll5': {
        'positivo': 'Alta tasa de paradas. Detiene muchos tiros en los últimos 5.',
        'negativo': 'Baja tasa de paradas. Deja pasar demasiados tiros al fondo.'
    },
    'save_pct_ewma5': {
        'positivo': 'Tendencia de paradas al alza. Cada vez para más.',
        'negativo': 'Tendencia de paradas a la baja. Cada vez para menos.'
    },

    # ── DEFENSA (DF) ─────────────────────────────────────────────────────────

    'intercepts_roll5': {
        'positivo': 'Gran lectura defensiva. Muchas interceptaciones en los últimos 5.',
        'negativo': 'Mala lectura del juego. Se le escapan muchos balones al rival.'
    },
    'duels_roll5': {
        'positivo': 'Muy competitivo. Gana la mayoría de duelos aéreos y terrestres.',
        'negativo': 'Le cuesta ganar duelos. Pierde muchas disputas de balón.'
    },
    'clearances_roll5': {
        'positivo': 'Despejes seguros. Efectivo sacando el balón del área de peligro.',
        'negativo': 'Despejes inefectivos. Deja el balón cerca del área o en peligro.'
    },
    'defensive_actions_total': {
        'positivo': 'Defensivamente es una roca. Muchas acciones defensivas por partido.',
        'negativo': 'Escasa actividad defensiva. Pocas acciones de recuperación.'
    },
    'cs_activity_alignment': {
        'positivo': 'Muy alineado defensivamente. Portería a cero es habitual.',
        'negativo': 'Poco alineado defensivamente. La portería a cero es rara.'
    },
    'def_contribution_roll5': {
        'positivo': 'Alta contribución defensiva total en los últimos 5 partidos.',
        'negativo': 'Baja contribución defensiva total en los últimos 5 partidos.'
    },

    # ── MEDIOCAMPISTA (MC) ────────────────────────────────────────────────────

    'passes_roll5': {
        'positivo': 'Controlador del juego. Muchos pases y alto dominio de la posesión.',
        'negativo': 'Poco implicado en el juego. Escaso toque de balón últimamente.'
    },
    'pass_comp_pct_roll5_mc': {
        'positivo': 'Muy preciso en pases. Completa alto porcentaje de sus intentos.',
        'negativo': 'Baja precisión. Completa menos del 75% de sus pases intentados.'
    },
    'pass_efficiency': {
        'positivo': 'Alta eficiencia en pases. Muchos pases completados con precisión.',
        'negativo': 'Baja eficiencia en pases. Poco volumen o poca precisión.'
    },
    'offensive_action': {
        'positivo': 'Muy dinámico. Muchos regates y conducciones progresivas realizadas.',
        'negativo': 'Poco dinámico. Escasos regates y conducciones progresivas.'
    },
    'defensive_participation': {
        'positivo': 'Contribuye mucho en defensa. Mediocampista muy completo.',
        'negativo': 'Escasa ayuda defensiva. Más ofensivo o poco activo atrás.'
    },
    'score_creativo': {
        'positivo': 'Alto score creativo. Genera mucho juego ofensivo para el equipo.',
        'negativo': 'Bajo score creativo. Poca generación de juego ofensivo.'
    },
    'tiene_rol_mediocampista_core': {
        'positivo': 'Tiene roles core de mediocampista (pases clave y asistencias).',
        'negativo': 'Sin roles core de mediocampista. No destaca en creación.'
    },

    # ── DELANTERO (DT) ────────────────────────────────────────────────────────

    'goals_roll5': {
        'positivo': 'En racha goleadora. Ha marcado en los últimos 5 partidos.',
        'negativo': 'Sequía de goles. Lleva tiempo sin marcar.'
    },
    'goals_roll3': {
        'positivo': 'En racha goleadora intensa. Marcando en los últimos 3 partidos.',
        'negativo': 'Sin goles en los últimos 3 partidos. Sequía reciente.'
    },
    'xg_roll5': {
        'positivo': 'Muchas oportunidades claras. El equipo le genera ocasiones de calidad.',
        'negativo': 'Pocas oportunidades. No recibe balones en zona de remate.'
    },
    'shots_roll5': {
        'positivo': 'Muy intentador. Tira mucho a puerta y genera peligro constantemente.',
        'negativo': 'Poco intentador. No genera suficientes remates recientes.'
    },
    'shots_on_target_roll5': {
        'positivo': 'Excelente puntería. Sus disparos van directos a puerta.',
        'negativo': 'Poca precisión. Muchos disparos fuera del marco.'
    },
    'shot_efficiency': {
        'positivo': 'Alta eficiencia de tiro. Convierte muchas oportunidades en gol.',
        'negativo': 'Baja eficiencia de tiro. Genera ocasiones pero no las convierte.'
    },
    'shot_accuracy': {
        'positivo': 'Muy preciso. Alta proporción de disparos entre los tres palos.',
        'negativo': 'Impreciso. Bajo porcentaje de disparos a puerta sobre total.'
    },
    'offensive_threat': {
        'positivo': 'Alto peligro ofensivo. Combina tiros y regates para presionar al rival.',
        'negativo': 'Poco peligro. Escasa presión ofensiva en los últimos partidos.'
    },
    'offensive_form': {
        'positivo': 'Excelente forma ofensiva. Goles + xG en niveles muy altos.',
        'negativo': 'Mala forma ofensiva. Goles + xG por debajo de lo esperado.'
    },
    'progressive_pressure': {
        'positivo': 'Alta presión progresiva. Conduce y avanza metros con el balón.',
        'negativo': 'Baja presión progresiva. Poco avance con el balón.'
    },
    'xg_overperformance': {
        'positivo': 'Supera su xG. Marca más goles de los que el modelo espera.',
        'negativo': 'Por debajo de su xG. Marca menos goles de los esperados.'
    },
    'shot_conversion_ewma5': {
        'positivo': 'Tasa de conversión alta. Muy eficiente transformando tiros en goles.',
        'negativo': 'Tasa de conversión baja. No convierte bien los tiros en goles.'
    },
    'offensive_pressure_score': {
        'positivo': 'Alto score de presión ofensiva. Combina tiros y xG de forma intensa.',
        'negativo': 'Bajo score de presión ofensiva. Escasa intensidad ofensiva.'
    },
    'scoring_stability': {
        'positivo': 'Marcador estable. Su puntuación ofensiva es consistente (roll5 ≈ ewma5).',
        'negativo': 'Marcador volátil. Alta variabilidad entre roll5 y ewma5.'
    },
    'scoring_momentum': {
        'positivo': 'Momentum goleador positivo. Puntuación ofensiva en alza.',
        'negativo': 'Momentum goleador negativo. Puntuación ofensiva en baja.'
    },
    'xg_momentum': {
        'positivo': 'Momentum xG positivo. Recibiendo cada vez más ocasiones de calidad.',
        'negativo': 'Momentum xG negativo. Recibiendo cada vez menos ocasiones.'
    },
    'xg_per_minute_ewma': {
        'positivo': 'Muy eficiente por minuto. Genera xG en muy poco tiempo de juego.',
        'negativo': 'Poco eficiente por minuto. Bajo xG en relación a sus minutos.'
    },
    'goals_per_minute_ewma': {
        'positivo': 'Muy goleador por minuto. Marca goles en muy poco tiempo de juego.',
        'negativo': 'Poco goleador por minuto. Baja ratio de goles por minuto jugado.'
    },
    'pf_volatility_fw': {
        'positivo': 'Alta volatilidad. Puede dar puntuaciones muy altas (o muy bajas).',
        'negativo': 'Baja volatilidad. Puntuaciones predecibles y estables.'
    },
    'pf_consistency_fw': {
        'positivo': 'Muy consistente. Puntuaciones estables y predecibles.',
        'negativo': 'Inconsistente. Alta variabilidad en puntuaciones de partido a partido.'
    },
    'score_goleador': {
        'positivo': 'Alto score goleador. Suma positiva de goles, penaltis y eficiencia.',
        'negativo': 'Bajo score goleador. Escasa contribución goleadora ponderada.'
    },
    'tiene_rol_delantero_core': {
        'positivo': 'Tiene roles core de delantero (goles y tiros a puerta).',
        'negativo': 'Sin roles core de delantero. No destaca en lo más importante.'
    },
}

# =============================================================================
# ALIASES BACKWARD COMPATIBILITY
# =============================================================================
EXPLICACIONES_PORTERO = EXPLICACIONES_FEATURES
EXPLICACIONES_DEFENSA = EXPLICACIONES_FEATURES
EXPLICACIONES_MEDIOCAMPISTA = EXPLICACIONES_FEATURES
EXPLICACIONES_DELANTERO = EXPLICACIONES_FEATURES
EXPLICACIONES_DF = EXPLICACIONES_FEATURES
EXPLICACIONES_MC = EXPLICACIONES_FEATURES
EXPLICACIONES_DT = EXPLICACIONES_FEATURES


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def obtener_explicacion(feature_name, es_positivo):
    """
    Retorna la explicación de un feature según su dirección de impacto.

    Args:
        feature_name: Nombre del feature
        es_positivo: True si el impacto SHAP es positivo

    Returns:
        str: Explicación en texto natural
    """
    if not isinstance(feature_name, str):
        feature_name = str(feature_name)
    feature_name = feature_name.strip()

    if feature_name not in EXPLICACIONES_FEATURES:
        # Try prefix match (e.g. goals_roll3 -> goals_roll5 pattern)
        for key in EXPLICACIONES_FEATURES:
            base = key.rsplit('_', 1)[0]
            feat_base = feature_name.rsplit('_', 1)[0]
            if base == feat_base:
                clave = 'positivo' if es_positivo else 'negativo'
                return EXPLICACIONES_FEATURES[key].get(clave, f"Factor: {feature_name}")
        return f"Factor: {feature_name}"

    clave = 'positivo' if es_positivo else 'negativo'
    return EXPLICACIONES_FEATURES[feature_name].get(clave, f"Factor: {feature_name}")


def obtener_ambas_explicaciones(feature_name):
    """
    Retorna AMBAS explicaciones (positiva y negativa) para un feature.

    Args:
        feature_name: Nombre del feature

    Returns:
        dict: { 'positivo': str, 'negativo': str }
    """
    if not isinstance(feature_name, str):
        feature_name = str(feature_name)
    feature_name = feature_name.strip()

    if feature_name not in EXPLICACIONES_FEATURES:
        # Try prefix match
        for key in EXPLICACIONES_FEATURES:
            base = key.rsplit('_', 1)[0]
            feat_base = feature_name.rsplit('_', 1)[0]
            if base == feat_base:
                explicaciones = EXPLICACIONES_FEATURES[key]
                return {
                    'positivo': explicaciones.get('positivo', f"Factor {feature_name} aumenta"),
                    'negativo': explicaciones.get('negativo', f"Factor {feature_name} disminuye")
                }
        return {
            'positivo': f"Factor: {feature_name} (impacto positivo)",
            'negativo': f"Factor: {feature_name} (impacto negativo)"
        }

    explicaciones = EXPLICACIONES_FEATURES[feature_name]
    return {
        'positivo': explicaciones.get('positivo', f"Factor {feature_name} aumenta"),
        'negativo': explicaciones.get('negativo', f"Factor {feature_name} disminuye")
    }


def es_valor_alto(feature_name, valor):
    """
    Determina si un valor de feature es considerado 'alto' (positivo).

    Args:
        feature_name: Nombre del feature
        valor: Valor numérico

    Returns:
        bool: True si el valor es alto/positivo
    """
    # Features donde valor alto = malo (invertidos)
    FEATURES_INVERTIDOS = {
        'opp_gf_roll5', 'opp_gf_ewma5',
        'opp_form_roll5', 'opp_form_ewma5',
        'odds_prob_loss',
        'pf_volatility_fw',
        'psxg_ewma5', 'psxg_roll5',
    }
    if feature_name in FEATURES_INVERTIDOS:
        return valor < 0.5

    if feature_name == 'num_roles_criticos':
        return valor >= 2
    elif 'pct' in feature_name.lower() or 'ratio' in feature_name.lower():
        return valor > 0.5
    else:
        return valor > 1.0


def preparar_features_para_explicaciones(data):
    """
    Convierte un dict de features a lista de dicts para explicaciones.

    Args:
        data: dict {feature: valor} o lista de dicts

    Returns:
        lista de dicts con keys: feature, valor, es_alto
    """
    if isinstance(data, dict):
        features_list = []
        for feature, valor in data.items():
            if valor is None:
                continue
            try:
                valor_num = float(valor)
            except (ValueError, TypeError):
                continue
            features_list.append({
                'feature': feature,
                'valor': valor_num,
                'es_alto': es_valor_alto(feature, valor_num)
            })
        return features_list
    if isinstance(data, list):
        return data
    return []


def generar_explicaciones_features(features_data):
    """
    Genera explicaciones de texto natural para los features de mayor impacto.

    Args:
        features_data: Lista de dicts con keys: feature, valor, impacto_pts, es_alto

    Returns:
        dict: {
            'features_impacto': [list of dicts],
            'explicacion_texto': str
        }
    """
    features_impacto = []
    explicacion_lines = []

    if not features_data:
        return {
            'features_impacto': [],
            'explicacion_texto': 'Sin datos disponibles'
        }

    feature_impacts = []
    for feat in features_data:
        if not isinstance(feat, dict) or 'feature' not in feat:
            continue
        fname = feat['feature']
        valor = feat.get('valor', 0)
        impacto_pts = feat.get('impacto_pts', 0)
        es_alto = feat.get('es_alto', valor > 1.0)

        # Calcular impacto aproximado si no viene
        if impacto_pts == 0 and valor != 0:
            if 'pct' in fname.lower() or 'ratio' in fname.lower():
                impacto_pts = abs(valor) * 2.0 if 0 <= valor <= 1 else min(abs(valor) / 50.0, 2.0)
            else:
                impacto_pts = min(abs(valor) / 15.0, 2.0)

        signo_impacto = 1 if es_alto else -1
        impacto_pts_signed = impacto_pts * signo_impacto

        feature_impacts.append({
            'feature': fname,
            'valor': valor,
            'impacto_pts': impacto_pts_signed,
            'es_alto': es_alto
        })

    # Top 7 por impacto absoluto
    feature_impacts.sort(key=lambda x: abs(x['impacto_pts']), reverse=True)
    top_features = feature_impacts[:7]

    explicacion_lines.append("Factores principales:")
    explicacion_lines.append("")

    for idx, feat in enumerate(top_features, 1):
        fname = feat['feature']
        impacto_pts = feat['impacto_pts']
        es_alto = feat['es_alto']

        explicacion_texto = obtener_explicacion(fname, es_alto)
        signo = '+' if impacto_pts > 0 else ('-' if impacto_pts < 0 else '')
        impacto_abs = abs(impacto_pts)
        linea = f"{idx}. {explicacion_texto} (impacto: {signo}{impacto_abs:.2f}pts)"
        explicacion_lines.append(linea)

        features_impacto.append({
            'feature': fname,
            'impacto': impacto_pts,
            'impacto_pts': impacto_pts,
            'direccion': 'positivo' if impacto_pts > 0 else ('negativo' if impacto_pts < 0 else 'neutro'),
            'explicacion': explicacion_texto
        })

    return {
        'features_impacto': features_impacto,
        'explicacion_texto': "\n".join(explicacion_lines)
    }


def _es_pipeline_lineal(modelo):
    """Detecta si el modelo es un Pipeline sklearn con un estimador lineal."""
    try:
        from sklearn.pipeline import Pipeline
        return isinstance(modelo, Pipeline)
    except ImportError:
        return False


def _shap_para_pipeline_lineal(modelo, X_pred_df, features_disponibles, verbose=False):
    """
    SHAP para Pipeline(StandardScaler + Ridge/ElasticNet).
    Usa LinearExplainer sobre el estimador final, con X escalado.
    """
    try:
        scaler  = modelo.named_steps.get('scaler', None)
        regresor = modelo.named_steps.get('regresor', None)
        if scaler is None or regresor is None:
            raise ValueError("Pipeline sin 'scaler' o 'regresor'")

        X_scaled = scaler.transform(X_pred_df)

        # Datos de fondo para el explainer (media de entrenamiento escalada = 0 por definición del scaler)
        background = np.zeros((1, X_scaled.shape[1]))

        explainer  = shap_lib.LinearExplainer(regresor, background, feature_perturbation='interventional')
        shap_values = explainer.shap_values(X_scaled)

        if isinstance(shap_values, (list, tuple)):
            shap_impacts = shap_values[0]
        else:
            shap_impacts = shap_values

        if hasattr(shap_impacts, 'shape') and len(shap_impacts.shape) > 1:
            shap_impacts = shap_impacts[0]

        feature_impacts = []
        for i, fname in enumerate(features_disponibles):
            if i >= len(shap_impacts):
                break
            impacto = float(shap_impacts[i])
            valor   = float(X_pred_df.iloc[0][fname]) if fname in X_pred_df.columns else 0.0
            es_alto = impacto > 0
            ambas_explicaciones = obtener_ambas_explicaciones(fname)
            feature_impacts.append({
                'feature': fname,
                'valor': valor,
                'impacto_pts': impacto,
                'es_alto': es_alto,
                'explicacion': obtener_explicacion(fname, es_alto),
                'explicacion_positiva': ambas_explicaciones['positivo'],
                'explicacion_negativa': ambas_explicaciones['negativo']
            })

        # Filtrar features redundantes de roles: mantener solo num_roles_criticos
        ROLES_REDUNDANTES = {
            'num_roles_positivos', 'num_roles_negativos',
            'score_roles_normalizado', 'ratio_roles_positivos'
        }
        feature_impacts = [f for f in feature_impacts if f['feature'] not in ROLES_REDUNDANTES]

        feature_impacts.sort(key=lambda x: abs(x['impacto_pts']), reverse=True)
        return feature_impacts[:10]

    except Exception as e:
        if verbose:
            print(f"[XAI] LinearExplainer falló ({e}), usando coeficientes")
        return _generar_explicaciones_feature_importance(modelo, X_pred_df, features_disponibles)


def generar_explicaciones_shap(modelo, X_pred_df, features_disponibles, verbose=False):
    """
    Genera explicaciones SHAP para una predicción.
    Soporta Random Forest, XGBoost y Pipeline(Scaler+Ridge/ElasticNet).

    Args:
        modelo: Modelo entrenado (RF, XGB, Pipeline con Ridge/ElasticNet)
        X_pred_df: DataFrame con una fila (features para predicción)
        features_disponibles: Lista de nombres de features
        verbose: Imprimir detalles

    Returns:
        list: Lista de dicts {feature, valor, impacto_pts, es_alto, explicacion, explicacion_positiva, explicacion_negativa}
    """
    if shap_lib is None:
        if verbose:
            print("[XAI] SHAP no disponible, usando feature importance")
        return _generar_explicaciones_feature_importance(modelo, X_pred_df, features_disponibles)

    # Pipeline lineal (Ridge, ElasticNet con StandardScaler)
    if _es_pipeline_lineal(modelo):
        return _shap_para_pipeline_lineal(modelo, X_pred_df, features_disponibles, verbose)

    # Árbol (Random Forest, XGBoost, GradientBoosting…)
    try:
        explainer   = shap_lib.TreeExplainer(modelo)
        shap_values = explainer.shap_values(X_pred_df)

        # Normalizar forma del array SHAP (regresión puede devolver lista)
        if isinstance(shap_values, (list, tuple)):
            shap_impacts = shap_values[0]
        else:
            shap_impacts = shap_values

        if hasattr(shap_impacts, 'shape') and len(shap_impacts.shape) > 1:
            shap_impacts = shap_impacts[0]

        feature_impacts = []
        for i, fname in enumerate(features_disponibles):
            if i >= len(shap_impacts):
                break
            impacto = float(shap_impacts[i])
            valor   = float(X_pred_df.iloc[0][fname]) if fname in X_pred_df.columns else 0.0
            es_alto = impacto > 0
            ambas_explicaciones = obtener_ambas_explicaciones(fname)
            feature_impacts.append({
                'feature': fname,
                'valor': valor,
                'impacto_pts': impacto,
                'es_alto': es_alto,
                'explicacion': obtener_explicacion(fname, es_alto),
                'explicacion_positiva': ambas_explicaciones['positivo'],
                'explicacion_negativa': ambas_explicaciones['negativo']
            })

        # Filtrar features redundantes de roles: mantener solo num_roles_criticos
        ROLES_REDUNDANTES = {
            'num_roles_positivos', 'num_roles_negativos',
            'score_roles_normalizado', 'ratio_roles_positivos'
        }
        feature_impacts = [f for f in feature_impacts if f['feature'] not in ROLES_REDUNDANTES]

        feature_impacts.sort(key=lambda x: abs(x['impacto_pts']), reverse=True)
        return feature_impacts[:10]

    except Exception as e:
        if verbose:
            print(f"[XAI] TreeExplainer falló ({e}), usando feature importance")
        return _generar_explicaciones_feature_importance(modelo, X_pred_df, features_disponibles)


def _generar_explicaciones_feature_importance(modelo, X_pred_df, features_disponibles):
    """
    Fallback: usa feature importance o coeficientes para explicar.
    Compatible con Random Forest, XGBoost, Pipeline(Scaler+Ridge/ElasticNet).
    """
    try:
        # Extraer el estimador interno si es un Pipeline
        estimador = modelo
        if _es_pipeline_lineal(modelo):
            estimador = modelo.named_steps.get('regresor', modelo)

        if hasattr(estimador, 'feature_importances_'):
            importances = estimador.feature_importances_
        elif hasattr(estimador, 'coef_'):
            importances = np.abs(estimador.coef_).flatten()
        else:
            importances = np.ones(len(features_disponibles))

        feature_impacts = []
        for i, fname in enumerate(features_disponibles):
            if i >= len(importances):
                break
            valor = float(X_pred_df.iloc[0][fname]) if fname in X_pred_df.columns else 0.0
            importance = float(importances[i]) if i < len(importances) else 0.0
            es_alto = es_valor_alto(fname, valor)
            impacto = importance * (1 if es_alto else -1)
            ambas_explicaciones = obtener_ambas_explicaciones(fname)
            feature_impacts.append({
                'feature': fname,
                'valor': valor,
                'impacto_pts': impacto,
                'es_alto': es_alto,
                'explicacion': obtener_explicacion(fname, es_alto),
                'explicacion_positiva': ambas_explicaciones['positivo'],
                'explicacion_negativa': ambas_explicaciones['negativo']
            })

        # Filtrar features redundantes de roles: mantener solo num_roles_criticos
        ROLES_REDUNDANTES = {
            'num_roles_positivos', 'num_roles_negativos',
            'score_roles_normalizado', 'ratio_roles_positivos'
        }
        feature_impacts = [f for f in feature_impacts if f['feature'] not in ROLES_REDUNDANTES]

        feature_impacts.sort(key=lambda x: abs(x['impacto_pts']), reverse=True)
        return feature_impacts[:10]
    except Exception:
        return []


def formatear_explicaciones_texto(feature_impacts, prediccion=None):
    """
    Genera texto legible a partir de lista de impactos.

    Args:
        feature_impacts: Lista de dicts de generar_explicaciones_shap
        prediccion: float (opcional)

    Returns:
        str: Texto formateado
    """
    lineas = []
    if prediccion is not None:
        lineas.append(f"Predicción: {prediccion:.1f} pts\n")
    lineas.append("Factores principales:\n")

    for idx, feat in enumerate(feature_impacts[:7], 1):
        impacto = feat.get('impacto_pts', 0)
        explicacion = feat.get('explicacion', f"Factor: {feat['feature']}")
        signo = '+' if impacto > 0 else ('-' if impacto < 0 else '')
        lineas.append(f"{idx}. {explicacion} (impacto: {signo}{abs(impacto):.2f}pts)")

    return "\n".join(lineas)


# =============================================================================
# COMPATIBILIDAD CON obtener_explicacion_posicion (explicaciones.py antiguo)
# =============================================================================

def obtener_explicacion_posicion(feature_name, es_positivo, posicion=None):
    """Alias para backward compatibility. posicion es ignorado."""
    return obtener_explicacion(feature_name, es_positivo)


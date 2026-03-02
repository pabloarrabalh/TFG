
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from typing import List, Tuple


# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

TAM_VENTANA = 5
TAM_VENTANA_RECIENTE = 3


# ============================================================================
# PARTE 1: ELIMINAR FEATURES RUIDO (COMÚN PARA TODAS LAS POSICIONES)
# ============================================================================

def eliminar_features_ruido(df: pd.DataFrame, position: str = 'ALL', verbose: bool = True) -> pd.DataFrame:

    # Features identificadas como 0.0000 en 2+ modelos en GridSearch results
    FEATURES_RUIDO_COMUN = [
        'duels_won_pct_ewma5',      # 0 en Random Forest
        'duels_won_roll5',           # 0 en Random Forest, XGBoost, Ridge
        'duels_won_ewma5',           # 0 en Random Forest, XGBoost, Ridge  
        'elite_entradas_interact',   # 0 en ElasticNet
        'ratio_roles_criticos',      # 0 en ElasticNet
    ]

    # ── PORTEROS: eliminar todo lo ofensivo de campo ──────────────────────
    FEATURES_RUIDO_GK = [
        'gol_partido', 'asist_partido', 'xg_partido', 'xag',
        'tiro_fallado_partido', 'tiro_puerta_partido', 'tiros',
        'regates', 'regates_completados', 'regates_fallidos',
        'conducciones', 'distancia_conduccion',
        'metros_avanzados_conduccion', 'conducciones_progresivas',
        'duelos', 'duelos_ganados', 'duelos_perdidos',
        'duelos_aereos_ganados', 'duelos_aereos_ganados_pct', 'duelos_aereos_perdidos',
        'bloqueo_pase', 'bloqueo_tiros', 'bloqueos', 'entradas',
    ]

    # ── DEFENSAS: eliminar features de portero y stats puramente ofensivos ─
    FEATURES_RUIDO_DF = [
        # GK-specific raw
        'porcentaje_paradas', 'psxg', 'goles_en_contra',
        # Rolling/ewma GK que no deben crearse para DF pero por si acaso
        'save_pct_roll3', 'save_pct_roll5', 'save_pct_ewma3', 'save_pct_ewma5',
        'psxg_roll3', 'psxg_roll5', 'psxg_ewma3', 'psxg_ewma5',
        # Ofensivos puros irrelevantes para défensa
        'xg_partido', 'xag', 'tiro_fallado_partido', 'tiro_puerta_partido',
        'gol_partido', 'asist_partido',
    ]

    # ── MEDIOCAMPISTAS: eliminar features exclusivos de portero ───────────
    FEATURES_RUIDO_MF = [
        'porcentaje_paradas', 'psxg', 'goles_en_contra',
        'save_pct_roll3', 'save_pct_roll5', 'save_pct_ewma3', 'save_pct_ewma5',
        'psxg_roll3', 'psxg_roll5', 'psxg_ewma3', 'psxg_ewma5',
        'save_per_90_ewma5', 'psxg_per_90_ewma5', 'expected_gk_core_points',
        'cs_expected_points',
    ]

    # ── DELANTEROS: eliminar features de portero y defensivos específicos ─
    FEATURES_RUIDO_FW = [
        # GK-specific
        'porcentaje_paradas', 'psxg', 'goles_en_contra',
        'save_pct_roll3', 'save_pct_roll5', 'save_pct_ewma3', 'save_pct_ewma5',
        'psxg_roll3', 'psxg_roll5', 'psxg_ewma3', 'psxg_ewma5',
        'save_per_90_ewma5', 'psxg_per_90_ewma5', 'expected_gk_core_points',
        'cs_expected_points',
        # Defensivos puros que no aportan al ST
        'despejes', 'bloqueos', 'bloqueo_pase', 'bloqueo_tiros',
        'duelos_aereos_ganados', 'duelos_aereos_ganados_pct', 'duelos_aereos_perdidos',
        # Rolls defensivos generados por error para FW
        'clearances_roll3', 'clearances_roll5', 'clearances_ewma3', 'clearances_ewma5',
        'def_actions_ewma5', 'cs_activity_alignment', 'cs_rate_recent',
    ]

    features_ruido = FEATURES_RUIDO_COMUN.copy()

    if position in ['GK', 'PT']:
        features_ruido.extend(FEATURES_RUIDO_GK)
    elif position == 'DF':
        features_ruido.extend(FEATURES_RUIDO_DF)
    elif position == 'MC':
        features_ruido.extend(FEATURES_RUIDO_MF)
    elif position == 'DT':
        features_ruido.extend(FEATURES_RUIDO_FW)
    # ALL: solo los comunes
    
    features_a_eliminar = [f for f in features_ruido if f in df.columns]
    
    if verbose:
        print("="*80)
        print(f"ELIMINACIÓN DE FEATURES RUIDO ({position})")
        print("="*80)
        if features_a_eliminar:
            print(f"\n{len(features_a_eliminar)} features a eliminar:\n")
            for f in features_a_eliminar:
                print(f"  [X] {f} (colinealidad/redundancia)")
            print()
        else:
            print(f"\n[OK] No hay features ruido a eliminar para {position}\n")
    
    df = df.drop(columns=features_a_eliminar, errors='ignore')
    
    if verbose:
        print(f"[OK] Eliminadas {len(features_a_eliminar)} features ruido\n")
    
    return df


# ============================================================================
# PARTE 2A: FEATURES ESPECÍFICOS PARA PORTEROS (GK) - SIN LEAKAGE
# ============================================================================

def crear_features_fantasy_gk(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Features específicos Fantasy para porteros (GK), sin leakage.

    Se refuerzan las señales que mejor han funcionado en los modelos:
    - Dificultad de fixture (home/away)
    - Probabilidades de goles (p_over25_ewma5)
    - Contexto ofensivo del rival (opp_shots_ewma5, opp_gc_ewma5)
    - PSxG y paradas por 90'

    Se crean:
    - cs_probability (mejorada)
    - cs_rate_recent (clean sheets recientes)
    - cs_expected_points (puntos esperados por CS)
    - expected_gk_core_points (resumen de puntos esperados GK)
    """

    if verbose:
        print("=" * 80)
        print("INGENIERÍA DE FEATURES PARA PORTEROS (GK) - SIN LEAKAGE")
        print("=" * 80)
        print()

    df = df.copy()

    # -----------------------------------------------------------------------
    # 0. Seguridad minutos
    # -----------------------------------------------------------------------
    if "min_partido" in df.columns:
        df["min_partido_safe"] = df["min_partido"].replace(0, 0.1)
    else:
        df["min_partido_safe"] = 1
    
    # -----------------------------------------------------------------------
    # 1. CLEAN SHEET PROBABILITY MEJORADA
    # -----------------------------------------------------------------------
    cs_components = []

    # A) Probabilidad implícita de pocos goles vía mercado (p_over25_ewma5)
    if "p_over25_ewma5" in df.columns:
        df['cs_prob_from_odds'] = 1.0 - df['p_over25_ewma5'].fillna(0.5)
        cs_components.append(df['cs_prob_from_odds'])

    # B) Rival que normalmente marca poco (opp_gc_ewma5 bajo)
    if "opp_gc_ewma5" in df.columns:
        df['cs_prob_from_gc'] = 1.0 / (1.0 + df['opp_gc_ewma5'].fillna(1))
        cs_components.append(df['cs_prob_from_gc'])

    # C) Rival que genera pocos tiros (opp_shots_ewma5 bajo)
    if "opp_shots_ewma5" in df.columns:
        df['cs_prob_from_shots'] = 1.0 / (1.0 + df['opp_shots_ewma5'].fillna(1))
        cs_components.append(df['cs_prob_from_shots'])

    # D) Efecto de la dificultad de fixture (home/away)
    if "fixture_difficulty_home" in df.columns and "fixture_difficulty_away" in df.columns and "is_home" in df.columns:
        df['cs_prob_from_fixture'] = df.apply(lambda x: x['fixture_difficulty_home'] if x['is_home'] else x['fixture_difficulty_away'], axis=1)
        cs_components.append(df['cs_prob_from_fixture'])

    if cs_components:
        df['cs_probability'] = pd.concat(cs_components, axis=1).mean(axis=1).fillna(0.5).clip(0, 1)
        df['cs_expected_points'] = df['cs_probability'] * 4  # 4 puntos por clean sheet
    else:
        df['cs_probability'] = 0.5
        df['cs_expected_points'] = 2

    # Clean sheet rate reciente (últimos 3 partidos, sin leakage)
    
    # -----------------------------------------------------------------------
    # 1. CLEAN SHEET PROBABILITY MEJORADA
    # -----------------------------------------------------------------------
    cs_components = []

    # A) Probabilidad implícita de pocos goles vía mercado (p_over25_ewma5)
    if "p_over25_ewma5" in df.columns:
        df["cs_prob_bets"] = (1 - df["p_over25_ewma5"].clip(0, 1)).fillna(0.5)
        cs_components.append("cs_prob_bets")

    # B) Rival que normalmente marca poco (opp_gc_ewma5 bajo)
    if "opp_gc_ewma5" in df.columns:
        df["cs_prob_opp_gc"] = (1 - (df["opp_gc_ewma5"] / 3.0).clip(0, 1)).fillna(0.5)
        cs_components.append("cs_prob_opp_gc")

    # C) Rival que genera pocos tiros (opp_shots_ewma5 bajo)
    if "opp_shots_ewma5" in df.columns:
        df["cs_prob_opp_shots"] = (1.0 / (1.0 + df["opp_shots_ewma5"].clip(lower=0))).fillna(0.5)
        cs_components.append("cs_prob_opp_shots")

    # D) Efecto de la dificultad de fixture (home/away)
    if "fixture_difficulty_home" in df.columns and "fixture_difficulty_away" in df.columns and "is_home" in df.columns:
        df["fixture_difficulty_effect"] = np.where(
            df["is_home"] == 1,
            1 - df["fixture_difficulty_home"].clip(0, 1),
            1 - df["fixture_difficulty_away"].clip(0, 1),
        )
        df["fixture_difficulty_effect"] = df["fixture_difficulty_effect"].fillna(0.5)
        cs_components.append("fixture_difficulty_effect")

    if cs_components:
        # Ponderación suave de todas las señales disponibles
        df["cs_probability"] = (
            0.4 * df.get("cs_prob_bets", 0.5)
            + 0.2 * df.get("cs_prob_opp_gc", 0.5)
            + 0.2 * df.get("cs_prob_opp_shots", 0.5)
            + 0.2 * df.get("fixture_difficulty_effect", 0.5)
        )
        df["cs_probability"] = df["cs_probability"].clip(0, 1)
        # Puntos esperados por CS (4 pts por puerta a cero)
        df["cs_expected_points"] = 4.0 * df["cs_probability"]
    else:
        df["cs_probability"] = 0.5
        df["cs_expected_points"] = 2.0

    # Clean sheet rate reciente (últimos 3 partidos, sin leakage)
    if "Goles_en_contra" in df.columns:
        cs_temp = (df.groupby("player")["Goles_en_contra"].shift() <= 0).astype(int)
        df["cs_rate_recent"] = cs_temp.groupby(df["player"]).transform(
            lambda x: x.rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
    else:
        df["cs_rate_recent"] = 0.0

    if verbose:
        print("[OK] Clean sheet probability & rate (mejoradas)")
        print("[OK] cs_expected_points")

    # -----------------------------------------------------------------------
    # 2. EFICIENCIA PER 90' (paradas y PSxG) - SIN LEAKAGE
    # -----------------------------------------------------------------------
    if "Porcentaje_paradas" in df.columns:
        df["save_per_90_temp"] = df["Porcentaje_paradas"] / (df["Min_partido_safe"] / 90.0)
        df["save_per_90"] = df.groupby("player")["save_per_90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df["save_per_90_ewma5"] = df.groupby("player")["save_per_90_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df = df.drop(columns=["save_per_90_temp"])

    if "PSxG" in df.columns:
        df["psxg_per_90_temp"] = df["PSxG"] / (df["Min_partido_safe"] / 90.0)
        df["psxg_per_90"] = df.groupby("player")["psxg_per_90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df["psxg_per_90_ewma5"] = df.groupby("player")["psxg_per_90_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df = df.drop(columns=["psxg_per_90_temp"])

    if verbose:
        print("[OK] Save per 90 (roll, ewma) - Sin leakage")
        print("[OK] PSxG per 90 (roll, ewma) - Sin leakage")

    # -----------------------------------------------------------------------
    # 3. RESUMEN CORE DE PUNTOS ESPERADOS GK
    # -----------------------------------------------------------------------
    df["expected_gk_core_points"] = (
        df.get("cs_expected_points", 0)
        + 0.4 * df.get("save_per_90_ewma5", 0)
        - 0.3 * df.get("psxg_per_90_ewma5", 0)
    )

    if verbose:
        print("[OK] expected_gk_core_points (CS + saves + PSxG)")

    return df


# ============================================================================
# PARTE 2B: FEATURES ESPECÍFICOS PARA DEFENSAS (DF) - SIN LEAKAGE
# ============================================================================

def crear_features_fantasy_defensivos(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Crea features específicos para Fantasy Football - Defensas.
    
    IMPORTANTE: Todos los features nuevos usan .shift() ANTES de rolling/ewma
    para evitar data leakage.
    
    Basado en la puntuación real de FPL:
    - Clean sheet: +4 pts
    - Entrada: +1 pt
    - Intercepción: +1 pt
    - Despeje: +0.5 pts
    - Falta: -0.5 pts
    - Amarilla: -1 pt
    
    Args:
        df: DataFrame con datos básicos
        verbose: Print de features creadas
        
    Returns:
        DataFrame enriquecido sin leakage
    """
    
    if verbose:
        print("="*80)
        print("INGENIERÍA DE FEATURES PARA DEFENSAS (DF) - SIN LEAKAGE")
        print("="*80)
        print()
    
    df = df.copy()
    
    # ========================================================================
    # 1. CLEAN SHEET PROBABILITY & RATE
    # ========================================================================
    
    if 'opp_shots_ewma5' in df.columns:
        # Probabilidad de clean sheet = inversamente proporcional a tiros recibidos
        df['cs_probability'] = 1.0 / (1.0 + df['opp_shots_ewma5'].fillna(0) + 0.1)
        
        # Rate de clean sheets en últimos 3 partidos
        if 'puntos_fantasy' in df.columns:
            df['cs_in_last_3'] = df.groupby('player')['puntos_fantasy'].transform(
                lambda x: ((x >= -10) & (x <= 10)).shift().rolling(3, min_periods=1).sum()
            ).fillna(0)
            
            df['cs_rate_recent'] = df['cs_in_last_3'] / 3.0
        
        if verbose:
            print("✅ cs_probability (tiros rival inverso) - Sin leakage")
            print("✅ cs_rate_recent (últimos 3 partidos) - Sin leakage")
    
    # ========================================================================
    # 2. EFFICIENCY METRICS (per 90 minutes - SIN LEAKAGE)
    # ========================================================================
    
    if 'entradas' in df.columns and 'min_partido' in df.columns:
        # Tackling per 90
        df['entradas'] = pd.to_numeric(df['entradas'], errors='coerce').fillna(0)
        df['min_partido'] = pd.to_numeric(df['min_partido'], errors='coerce').fillna(1)
        
        df['tackles_per_90'] = (
            df['entradas'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        # Media móvil exponencial de tackles per 90
        df['tackles_per_90_ewma5'] = df.groupby('player')['tackles_per_90'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print("✅ tackles_per_90 (normalizadas a 90 min) - Sin leakage")
            print("✅ tackles_per_90_ewma5 (media móvil) - Sin leakage")
    
    if 'intercepciones' in df.columns and 'min_partido' in df.columns:
        df['intercepciones'] = pd.to_numeric(df['intercepciones'], errors='coerce').fillna(0)
        
        df['int_per_90'] = (
            df['intercepciones'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        df['int_per_90_ewma5'] = df.groupby('player')['int_per_90'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print("✅ int_per_90 (normalizadas a 90 min) - Sin leakage")
            print("✅ int_per_90_ewma5 (media móvil) - Sin leakage")
    
    if 'despejes' in df.columns and 'min_partido' in df.columns:
        df['despejes'] = pd.to_numeric(df['despejes'], errors='coerce').fillna(0)
        
        df['clearances_per_90'] = (
            df['despejes'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        if verbose:
            print("✅ clearances_per_90 (normalizadas a 90 min) - Sin leakage")
    
    # ========================================================================
    # 3. COMBINED DEFENSIVE ACTION INDEX
    # ========================================================================
    
    df['defensive_actions_total'] = (
        df.get('entradas', 0) + 
        df.get('intercepciones', 0) + 
        df.get('despejes', 0) * 0.5  # Despejes menos valorados
    )
    
    df['def_actions_per_90'] = (
        df['defensive_actions_total'] / (df['min_partido'] / 90.0 + 0.1)
    ).fillna(0)
    
    df['def_actions_ewma5'] = df.groupby('player')['defensive_actions_total'].transform(
        lambda x: x.shift().ewm(span=5, adjust=False).mean()
    ).fillna(0)
    
    if verbose:
        print("✅ defensive_actions_total (tackles + int + clearances*0.5) - Sin leakage")
        print("✅ def_actions_per_90 (normalizadas) - Sin leakage")
        print("✅ def_actions_ewma5 (media móvil) - Sin leakage")
    
    # ========================================================================
    # 4. CONSISTENCY / VOLATILITY (SIN LEAKAGE)
    # ========================================================================
    
    if 'puntosFantasy' in df.columns:
        # Consistencia reciente: 1 / (1 + desviación)
        df['consistency_5games'] = df.groupby('player')['puntosFantasy'].transform(
            lambda x: 1.0 / (1.0 + x.shift().rolling(5, min_periods=2).std().fillna(0))
        ).fillna(0.5)
        
        # Desviación de acciones defensivas (¿muy variable?)
        df['def_actions_volatility'] = df.groupby('player')['defensive_actions_total'].transform(
            lambda x: x.shift().rolling(5, min_periods=2).std()
        ).fillna(0)
        
        if verbose:
            print("✅ consistency_5games (inversa a volatilidad) - Sin leakage")
            print("✅ def_actions_volatility (desviación acciones) - Sin leakage")
    
    # ========================================================================
    # 5. MOMENTUM / TREND DETECTION (SIN LEAKAGE)
    # ========================================================================
    
    if 'tackles_ewma3' in df.columns and 'tackles_ewma5' in df.columns:
        # Si ewma3 > ewma5, está mejorando
        df['tackles_momentum'] = (
            df['tackles_ewma3'] - df['tackles_ewma5']
        ).fillna(0)
        
        if verbose:
            print("✅ tackles_momentum (ewma3 - ewma5)")
    
    if 'Intercepciones' in df.columns:
        df['int_momentum'] = df.groupby('player')['Intercepciones'].transform(
            lambda x: (x.shift().ewm(3, adjust=False).mean() - 
                      x.shift().ewm(5, adjust=False).mean())
        ).fillna(0)
        
        if verbose:
            print("✅ int_momentum (trend de intercepciones) - Sin leakage")
    
    # ========================================================================
    # 6. CONTEXT INTERACTIONS (Críticas para XGBoost - SIN LEAKAGE)
    # ========================================================================
    
    if 'fixture_difficulty_home' in df.columns and 'is_home' in df.columns:
        # Si está en casa contra rival débil, probablemente:
        # - Ataque más, defiende menos
        # - Menos puntos defensivos esperados
        df['defensive_context'] = (
            df['is_home'].fillna(0) * df['fixture_difficulty_home'].fillna(0.5)
        )
        
        if verbose:
            print("✅ defensive_context (is_home × fixture_difficulty)")
    
    # Clean sheet esperado × actividad real
    if 'cs_probability' in df.columns and 'def_actions_per_90' in df.columns:
        df['cs_activity_alignment'] = (
            df['cs_probability'] * df['def_actions_per_90']
        ).fillna(0)
        
        if verbose:
            print("✅ cs_activity_alignment (CS prob × activity)")
    
    # ========================================================================
    # 7. USAGE & STATUS (SIN LEAKAGE)
    # ========================================================================
    
    if 'minutes_pct_roll5' in df.columns:
        # ¿Cambió recientemente el uso?
        df['usage_change_recent'] = df.groupby('player')['minutes_pct_roll5'].transform(
            lambda x: x.shift() - x.shift(2)
        ).fillna(0)
        
        if verbose:
            print("✅ usage_change_recent (cambio en minutos %) - Sin leakage")
    
    if verbose:
        print(f"\n✅ Fase 2 completada - Features DF creados\n")
    
    return df


# ============================================================================
# PARTE 2C: FEATURES ESPECÍFICOS PARA MEDIOCAMPISTAS (MF) - SIN LEAKAGE
# ============================================================================

def crear_features_fantasy_mediocampista(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Crea features específicos para Fantasy Football - Mediocampistas.
    
    IMPORTANTE: Todos los features nuevos usan .shift() ANTES de rolling/ewma
    para evitar data leakage.
    
    En FPL, mediocampista típicamente gana:
    - Gol: +5 pts (no marcamos esto, es muy raro)
    - Asistencia: +1 pt (no disponible en nuestro CSV)
    - Clean sheet: +1 pt (raro si hay goles)
    - Entrada: +1 pt
    - Intercepción: +1 pt
    - Crear juego: En pases clave
    - Falta: -0.5 pts
    - Amarilla: -1 pt
    
    Args:
        df: DataFrame con datos básicos
        verbose: Print de features creados
        
    Returns:
        DataFrame enriquecido sin leakage
    """
    
    if verbose:
        print("\n" + "=" * 80)
        print("FEATURES MEDIOCAMPISTA (FANTASY SPECIFIC)")
        print("=" * 80)
    
    df = df.copy()
    
    # ========================================================================
    # 1. EFICIENCIA DE PASES (Sin leakage - datos históricos)
    # ========================================================================
    
    if 'pases_totales' in df.columns and 'pases_completados_pct' in df.columns:
        df['pass_attempts_per_90'] = (
            df['pases_totales'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        df['pass_accuracy_consistency'] = df.groupby('player')['pases_completados_pct'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(50)
        
        if verbose:
            print("   ✅ Pass accuracy metrics")
    
    # ========================================================================
    # 2. ACTIVIDAD OFENSIVA (REGATES Y CONDUCCIONES)
    # ========================================================================
    
    if 'regates' in df.columns and 'min_partido' in df.columns:
        df['dribbles_per_90'] = (
            df['regates'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
    
    if 'conducciones' in df.columns and 'min_partido' in df.columns:
        df['dribble_intensity'] = df.groupby('player')['conducciones'].transform(
            lambda x: x.shift().rolling(5, min_periods=1).mean()
        ).fillna(0)
    
    if 'conducciones_progresivas' in df.columns and 'min_partido' in df.columns:
        df['progressive_action_rate'] = (
            df['conducciones_progresivas'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        if verbose:
            print("   ✅ Offensive activity metrics")
    
    # ========================================================================
    # 3. DEFENSA Y RECUPERACIÓN (EQUILIBRIO)
    # ========================================================================
    
    if 'entradas' in df.columns and 'intercepciones' in df.columns:
        df['defensive_actions_total'] = df['entradas'] + df['intercepciones']
        
        df['defensive_contribution'] = df.groupby('player')['defensive_actions_total'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print("   ✅ Defensive recovery metrics")
    
    # ========================================================================
    # 4. CREACIÓN DE JUEGO (IMPACTO OFENSIVO)
    # ========================================================================
    
    # Equilibrio entre pases completados y actividad defensiva
    if 'pases_totales' in df.columns and 'entradas' in df.columns:
        df['creative_vs_defensive'] = (
            df.groupby('player')['pases_totales'].transform(lambda x: x.shift().rolling(5, min_periods=1).mean())
            / (df.groupby('player')['entradas'].transform(lambda x: x.shift().rolling(5, min_periods=1).mean()) + 1)
        ).fillna(0)
        
        if verbose:
            print("   ✅ Creative impact index")
    
    # ========================================================================
    # 5. CONSISTENCIA (Volatility indicator - sin leakage)
    # ========================================================================
    
    if 'puntos_fantasy' in df.columns or 'puntos_fantasy' in df.columns:
        col_pf = 'puntos_fantasy'
        col_pf = col_pf if col_pf in df.columns else 'puntos_fantasy'
        
        if col_pf in df.columns:
            df['pf_volatility_5'] = df.groupby('player')[col_pf].transform(
                lambda x: x.shift().rolling(5, min_periods=2).std()
            ).fillna(0)
            
            df['pf_consistency'] = 1.0 / (1.0 + df['pf_volatility_5'])
            
            if verbose:
                print("   ✅ Consistency metrics")
    
    # ========================================================================
    # 6. REGATES SUCCESS RATE (Sin leakage)
    # ========================================================================
    
    if 'regates_completados' in df.columns and 'regates' in df.columns:
        total_dribbles = df['regates'] + 0.1
        df['dribble_success_pct'] = (df['regates_completados'] / total_dribbles * 100).fillna(0)
        
        df['dribble_confidence'] = df.groupby('player')['dribble_success_pct'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(50)
        
        if verbose:
            print("   ✅ Dribble success metrics")
    
    # ========================================================================
    # 7. OVERALL ACTIVITY INDEX (Actividad general)
    # ========================================================================
    
    activity_components = []
    
    if 'pases_totales' in df.columns:
        activity_components.append(df['pases_totales'])
    
    if 'entradas' in df.columns:
        activity_components.append(df['entradas'])
    
    if 'regates' in df.columns:
        activity_components.append(df['regates'])
    
    if 'conducciones' in df.columns:
        activity_components.append(df['conducciones'])
    
    if activity_components:
        df['overall_activity'] = pd.concat(activity_components, axis=1).sum(axis=1)
        
        if verbose:
            print("   ✅ Overall activity index")
    
    # ========================================================================
    # 8. FORM AND MINUTES (Disponibilidad x Forma)
    # ========================================================================
    
    if 'minutes_pct_ewma5' in df.columns and 'pf_ewma5' in df.columns:
        df['playing_time_form_combo'] = (
            df['minutes_pct_ewma5'] * df['pf_ewma5']
        ).fillna(0)
        
        if verbose:
            print("   ✅ Form adaptation metrics")
    
    # Rellenar NaNs con 0
    df = df.fillna(0).replace([np.inf, -np.inf], 0)
    
    if verbose:
        print(f"\n✅ Fase 2 completada - Features MC creados\n")
    
    return df


# ============================================================================
# PARTE 2D: FEATURES ESPECÍFICOS PARA DELANTEROS (FW/ST) - SIN LEAKAGE
# ============================================================================

def crear_features_fantasy_delantero(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Crea features específicos para Fantasy Football - Delanteros (ST/FW).

    En Fantasy, un delantero gana puntos principalmente por:
    - Goles (+4 pts o más)
    - Tiros a puerta (señal de implicación ofensiva)
    - xG acumulado (intención goleadora)
    - Regates y conducciones progresivas (creación)
    - Minutos jugados (disponibilidad)

    Todos los features usan .shift() para evitar data leakage.

    Args:
        df: DataFrame con datos básicos de delanteros
        verbose: Print de features creados

    Returns:
        DataFrame enriquecido sin leakage
    """

    if verbose:
        print("\n" + "=" * 80)
        print("FEATURES DELANTERO (FANTASY SPECIFIC - ST/FW)")
        print("=" * 80)

    df = df.copy()

    # ========================================================================
    # 1. EFICIENCIA GOLEADORA (xG vs Goles reales)
    # ========================================================================

    if 'xg_partido' in df.columns and 'gol_partido' in df.columns:
        df['xg_partido'] = pd.to_numeric(df['xg_partido'], errors='coerce').fillna(0)
        df['gol_partido'] = pd.to_numeric(df['gol_partido'], errors='coerce').fillna(0)

        # Over/under-performance vs xG en ventana reciente
        df['xg_overperformance'] = df.groupby('player').apply(
            lambda x: (x['gol_partido'] - x['xg_partido']).shift().rolling(5, min_periods=1).mean()
        ).reset_index(level=0, drop=True).fillna(0)

        if verbose:
            print("   ✅ xg_overperformance (goles - xG rolling5) - Sin leakage")

    # ========================================================================
    # 2. CONVERSIÓN DE TIROS (precisión finalizadora)
    # ========================================================================

    if 'tiros' in df.columns and 'gol_partido' in df.columns:
        df['tiros'] = pd.to_numeric(df['tiros'], errors='coerce').fillna(0)
        df['gol_partido'] = pd.to_numeric(df['gol_partido'], errors='coerce').fillna(0)

        # Ratio goles/tiro en los últimos 5 partidos
        df['shot_conversion_ewma5'] = df.groupby('player').apply(
            lambda g: (g['gol_partido'] / (g['tiros'] + 0.1)).shift().ewm(span=5, adjust=False).mean()
        ).reset_index(level=0, drop=True).fillna(0)

        if verbose:
            print("   ✅ shot_conversion_ewma5 (goles/tiro) - Sin leakage")

    # ========================================================================
    # 3. PRESIÓN OFENSIVA (tiros + xG combinados)
    # ========================================================================

    if 'shots_roll5' in df.columns and 'xg_roll5' in df.columns:
        df['offensive_pressure_score'] = (
            df['shots_roll5'] * 0.4 + df['xg_roll5'] * 0.6
        ).fillna(0)

        if verbose:
            print("   ✅ offensive_pressure_score (shots*0.4 + xg*0.6)")

    # ========================================================================
    # 4. CONSISTENCIA GOLEADORA
    # ========================================================================

    if 'goals_roll5' in df.columns and 'goals_ewma5' in df.columns:
        # Si roll5 y ewma5 son similares → racha estable, no un pico aislado
        df['scoring_stability'] = 1.0 / (
            1.0 + (df['goals_roll5'] - df['goals_ewma5']).abs().fillna(0)
        )

        if verbose:
            print("   ✅ scoring_stability (consistencia goleadora)")

    # ========================================================================
    # 5. EFICIENCIA POR MINUTO JUGADO
    # ========================================================================

    if 'xg_roll5' in df.columns and 'minutes_pct_ewma5' in df.columns:
        df['xg_per_minute_ewma'] = (
            df['xg_roll5'] / (df['minutes_pct_ewma5'] + 0.1)
        ).fillna(0)

        if verbose:
            print("   ✅ xg_per_minute_ewma (xG por minuto disponible)")

    if 'goals_roll5' in df.columns and 'minutes_pct_ewma5' in df.columns:
        df['goals_per_minute_ewma'] = (
            df['goals_roll5'] / (df['minutes_pct_ewma5'] + 0.1)
        ).fillna(0)

        if verbose:
            print("   ✅ goals_per_minute_ewma (goles por minuto disponible)")

    # ========================================================================
    # 6. AMENAZA PROGRESIVA (conducciones + regates hacia portería)
    # ========================================================================

    if 'prog_dribbles_roll5' in df.columns and 'prog_dist_roll5' in df.columns:
        df['progressive_threat'] = (
            df['prog_dribbles_roll5'] * 0.5 + df['prog_dist_roll5'] * 0.01
        ).fillna(0)

        if verbose:
            print("   ✅ progressive_threat (conducciones + distancia progresiva)")

    # ========================================================================
    # 7. MOMENTUM GOLEADOR (tendencia reciente vs media larga)
    # ========================================================================

    if 'goals_ewma3' in df.columns and 'goals_ewma5' in df.columns:
        # Positivo: está marcando más que su media
        df['scoring_momentum'] = (df['goals_ewma3'] - df['goals_ewma5']).fillna(0)

        if verbose:
            print("   ✅ scoring_momentum (ewma3 - ewma5, tendencia)")

    if 'xg_ewma3' in df.columns and 'xg_ewma5' in df.columns:
        df['xg_momentum'] = (df['xg_ewma3'] - df['xg_ewma5']).fillna(0)

        if verbose:
            print("   ✅ xg_momentum (tendencia xG reciente)")

    # ========================================================================
    # 8. VOLATILIDAD DE PUNTOS (riesgo/beneficio ST)
    # ========================================================================

    if 'puntos_fantasy' in df.columns:
        df['pf_volatility_fw'] = df.groupby('player')['puntos_fantasy'].transform(
            lambda x: x.shift().rolling(5, min_periods=2).std()
        ).fillna(0)

        df['pf_consistency_fw'] = 1.0 / (1.0 + df['pf_volatility_fw'])

        if verbose:
            print("   ✅ pf_volatility_fw / pf_consistency_fw (estabilidad ST)")

    # Rellenar NaNs con 0
    df = df.fillna(0).replace([np.inf, -np.inf], 0)

    if verbose:
        print(f"\n✅ Features delantero creados correctamente\n")

    return df


# ============================================================================
# PARTE 3: SELECCIÓN DE FEATURES POR CORRELACIÓN (COMÚN)
# ============================================================================

def seleccionar_features_por_correlacion(
    X: pd.DataFrame, 
    y: pd.Series,
    target_name: str = 'puntosFantasy',
    threshold: float = 0.03,
    verbose: bool = True
) -> Tuple[List[str], pd.DataFrame]:
    """
    Selecciona features con Spearman >= threshold con el target.
    Evita features con ruido puro (correlación = 0).
    
    Args:
        X: Features dataframe
        y: Target series
        target_name: Nombre del target para logs
        threshold: Correlación mínima |Spearman|
        verbose: Print detallado
        
    Returns:
        (lista_features_validas, dataframe_correlaciones)
    """
    
    if verbose:
        print("="*80)
        print(f"SELECCIÓN DE FEATURES POR CORRELACIÓN ({target_name})")
        print("="*80)
        print()
    
    correlaciones = []
    
    for col in X.columns:
        # Ignorar features con demasiados NaN
        mask = (~X[col].isna()) & (~y.isna())
        if mask.sum() < 10:
            correlaciones.append({
                'feature': col,
                'spearman': 0.0,
                'p_value': 1.0,
                'abs_spearman': 0.0
            })
            continue
        
        try:
            # Debug: show diagnostics for problematic opp_form columns
            if col in ('opp_form_roll5', 'opp_form_ewma5'):
                vals = X.loc[mask, col]
                try:
                    unique = vals.nunique()
                    std = vals.std()
                    mn = vals.min()
                    mx = vals.max()
                except Exception:
                    unique = None; std = None; mn = None; mx = None
                print(f"[DEBUG] Col={col} mask_sum={mask.sum()} unique={unique} std={std} min={mn} max={mx}")

            corr, pval = spearmanr(X.loc[mask, col], y[mask])
            abs_corr = abs(corr) if not np.isnan(corr) else 0.0
            
            correlaciones.append({
                'feature': col,
                'spearman': corr if not np.isnan(corr) else 0.0,
                'p_value': pval if not np.isnan(pval) else 1.0,
                'abs_spearman': abs_corr
            })
        except Exception as e:
            correlaciones.append({
                'feature': col,
                'spearman': 0.0,
                'p_value': 1.0,
                'abs_spearman': 0.0
            })
    
    # DataFrame de resultados
    df_corr = pd.DataFrame(correlaciones).sort_values('abs_spearman', ascending=False)
    
    # Features válidas
    features_validos = df_corr[
        df_corr['abs_spearman'] >= threshold
    ]['feature'].tolist()
    
    # Estadísticas
    features_muertos = (df_corr['spearman'] == 0.0).sum()
    features_bajo_threshold = ((df_corr['abs_spearman'] > 0) & (df_corr['abs_spearman'] < threshold)).sum()
    
    if verbose:
        print(f"\n[CHART] Analisis de correlacion:\n")
        print(f"  • Features muertos (r=0): {features_muertos}")
        print(f"  • Features bajo threshold (<{threshold}): {features_bajo_threshold}")
        print(f"  • Features validos (>={threshold}): {len(features_validos)}")
        print(f"  • Total: {len(df_corr)}")
        
        print(f"\n[TROPHY] TOP 20 Features por |Spearman|:\n")
        for idx, row in df_corr.head(20).iterrows():
            print(f"  {row['feature']:40s} r={row['spearman']:8.4f} (p={row['p_value']:.4f})")
    
    if verbose:
        print(f"\n[OK] Seleccionados {len(features_validos)} features validos\n")
    
    return features_validos, df_corr



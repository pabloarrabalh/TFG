
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from typing import List, Tuple


TAM_VENTANA = 5
TAM_VENTANA_RECIENTE = 3


def eliminar_features_ruido(df: pd.DataFrame, position: str = 'ALL', verbose: bool = True) -> pd.DataFrame:

    FEATURES_RUIDO_COMUN = [
        'duels_won_pct_ewma5',
        'duels_won_roll5',
        'duels_won_ewma5',
        'elite_entradas_interact',
        'ratio_roles_criticos',
    ]

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

    FEATURES_RUIDO_DF = [
        'porcentaje_paradas', 'psxg', 'goles_en_contra',
        'save_pct_roll3', 'save_pct_roll5', 'save_pct_ewma3', 'save_pct_ewma5',
        'psxg_roll3', 'psxg_roll5', 'psxg_ewma3', 'psxg_ewma5',
        'xg_partido', 'xag', 'tiro_fallado_partido', 'tiro_puerta_partido',
        'gol_partido', 'asist_partido',
    ]

    FEATURES_RUIDO_MF = [
        'porcentaje_paradas', 'psxg', 'goles_en_contra',
        'save_pct_roll3', 'save_pct_roll5', 'save_pct_ewma3', 'save_pct_ewma5',
        'psxg_roll3', 'psxg_roll5', 'psxg_ewma3', 'psxg_ewma5',
        'save_per_90_ewma5', 'psxg_per_90_ewma5', 'expected_gk_core_points',
        'cs_expected_points',
    ]

    FEATURES_RUIDO_FW = [
        'porcentaje_paradas', 'psxg', 'goles_en_contra',
        'save_pct_roll3', 'save_pct_roll5', 'save_pct_ewma3', 'save_pct_ewma5',
        'psxg_roll3', 'psxg_roll5', 'psxg_ewma3', 'psxg_ewma5',
        'save_per_90_ewma5', 'psxg_per_90_ewma5', 'expected_gk_core_points',
        'cs_expected_points',
        'despejes', 'bloqueos', 'bloqueo_pase', 'bloqueo_tiros',
        'duelos_aereos_ganados', 'duelos_aereos_ganados_pct', 'duelos_aereos_perdidos',
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
    
    features_a_eliminar = [f for f in features_ruido if f in df.columns]
    
    if verbose:
        print("="*80)
        print(f"ELIMINACIÃ“N DE FEATURES RUIDO ({position})")
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


def crear_features_fantasy_gk(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    if verbose:
        print("=" * 80)
        print("INGENIERÃA DE FEATURES PARA PORTEROS (GK) - SIN LEAKAGE")
        print("=" * 80)
        print()

    df = df.copy()
    if "min_partido" in df.columns:
        df["min_partido_safe"] = df["min_partido"].replace(0, 0.1)
    else:
        df["min_partido_safe"] = 1
   
    cs_components = []

    if "p_over25_ewma5" in df.columns:
        df['cs_prob_from_odds'] = 1.0 - df['p_over25_ewma5'].fillna(0.5)
        cs_components.append(df['cs_prob_from_odds'])

    if "opp_gc_ewma5" in df.columns:
        df['cs_prob_from_gc'] = 1.0 / (1.0 + df['opp_gc_ewma5'].fillna(1))
        cs_components.append(df['cs_prob_from_gc'])

    if "opp_shots_ewma5" in df.columns:
        df['cs_prob_from_shots'] = 1.0 / (1.0 + df['opp_shots_ewma5'].fillna(1))
        cs_components.append(df['cs_prob_from_shots'])

    if "fixture_difficulty_home" in df.columns and "fixture_difficulty_away" in df.columns and "is_home" in df.columns:
        df['cs_prob_from_fixture'] = df.apply(lambda x: x['fixture_difficulty_home'] if x['is_home'] else x['fixture_difficulty_away'], axis=1)
        cs_components.append(df['cs_prob_from_fixture'])

    if cs_components:
        df['cs_probability'] = pd.concat(cs_components, axis=1).mean(axis=1).fillna(0.5).clip(0, 1)
        df['cs_expected_points'] = df['cs_probability'] * 4
    else:
        df['cs_probability'] = 0.5
        df['cs_expected_points'] = 2

    cs_components = []

    if "p_over25_ewma5" in df.columns:
        df["cs_prob_bets"] = (1 - df["p_over25_ewma5"].clip(0, 1)).fillna(0.5)
        cs_components.append("cs_prob_bets")

    if "opp_gc_ewma5" in df.columns:
        df["cs_prob_opp_gc"] = (1 - (df["opp_gc_ewma5"] / 3.0).clip(0, 1)).fillna(0.5)
        cs_components.append("cs_prob_opp_gc")

    if "opp_shots_ewma5" in df.columns:
        df["cs_prob_opp_shots"] = (1.0 / (1.0 + df["opp_shots_ewma5"].clip(lower=0))).fillna(0.5)
        cs_components.append("cs_prob_opp_shots")

    if "fixture_difficulty_home" in df.columns and "fixture_difficulty_away" in df.columns and "is_home" in df.columns:
        df["fixture_difficulty_effect"] = np.where(
            df["is_home"] == 1,
            1 - df["fixture_difficulty_home"].clip(0, 1),
            1 - df["fixture_difficulty_away"].clip(0, 1),
        )
        df["fixture_difficulty_effect"] = df["fixture_difficulty_effect"].fillna(0.5)
        cs_components.append("fixture_difficulty_effect")

    if cs_components:
        df["cs_probability"] = (
            0.4 * df.get("cs_prob_bets", 0.5)
            + 0.2 * df.get("cs_prob_opp_gc", 0.5)
            + 0.2 * df.get("cs_prob_opp_shots", 0.5)
            + 0.2 * df.get("fixture_difficulty_effect", 0.5)
        )
        df["cs_probability"] = df["cs_probability"].clip(0, 1)
        df["cs_expected_points"] = 4.0 * df["cs_probability"]
    else:
        df["cs_probability"] = 0.5
        df["cs_expected_points"] = 2.0

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

    df["expected_gk_core_points"] = (
        df.get("cs_expected_points", 0)
        + 0.4 * df.get("save_per_90_ewma5", 0)
        - 0.3 * df.get("psxg_per_90_ewma5", 0)
    )

    if verbose:
        print("[OK] expected_gk_core_points (CS + saves + PSxG)")

    return df



def crear_features_fantasy_defensivos(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    if verbose:
        print("="*80)
        print("INGENIERÃA DE FEATURES PARA DEFENSAS (DF) - SIN LEAKAGE")
        print("="*80)
        print()
    
    df = df.copy()
    
    
    if 'opp_shots_ewma5' in df.columns:
        df['cs_probability'] = 1.0 / (1.0 + df['opp_shots_ewma5'].fillna(0) + 0.1)
        if 'puntos_fantasy' in df.columns:
            df['cs_in_last_3'] = df.groupby('player')['puntos_fantasy'].transform(
                lambda x: ((x >= -10) & (x <= 10)).shift().rolling(3, min_periods=1).sum()
            ).fillna(0)
            
            df['cs_rate_recent'] = df['cs_in_last_3'] / 3.0
        
        if verbose:
            print("âœ… cs_probability (tiros rival inverso) - Sin leakage")
            print("âœ… cs_rate_recent (Ãºltimos 3 partidos) - Sin leakage")
    
    if 'entradas' in df.columns and 'min_partido' in df.columns:
        df['entradas'] = pd.to_numeric(df['entradas'], errors='coerce').fillna(0)
        df['min_partido'] = pd.to_numeric(df['min_partido'], errors='coerce').fillna(1)
        
        df['tackles_per_90'] = (
            df['entradas'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        df['tackles_per_90_ewma5'] = df.groupby('player')['tackles_per_90'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print("âœ… tackles_per_90 (normalizadas a 90 min) - Sin leakage")
            print("âœ… tackles_per_90_ewma5 (media mÃ³vil) - Sin leakage")
    
    if 'intercepciones' in df.columns and 'min_partido' in df.columns:
        df['intercepciones'] = pd.to_numeric(df['intercepciones'], errors='coerce').fillna(0)
        
        df['int_per_90'] = (
            df['intercepciones'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        df['int_per_90_ewma5'] = df.groupby('player')['int_per_90'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print("âœ… int_per_90 (normalizadas a 90 min) - Sin leakage")
            print("âœ… int_per_90_ewma5 (media mÃ³vil) - Sin leakage")
    
    if 'despejes' in df.columns and 'min_partido' in df.columns:
        df['despejes'] = pd.to_numeric(df['despejes'], errors='coerce').fillna(0)
        
        df['clearances_per_90'] = (
            df['despejes'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        if verbose:
            print("âœ… clearances_per_90 (normalizadas a 90 min) - Sin leakage")
    
    df['defensive_actions_total'] = (
        df.get('entradas', 0) + 
        df.get('intercepciones', 0) + 
        df.get('despejes', 0) * 0.5
    )
    
    df['def_actions_per_90'] = (
        df['defensive_actions_total'] / (df['min_partido'] / 90.0 + 0.1)
    ).fillna(0)
    
    df['def_actions_ewma5'] = df.groupby('player')['defensive_actions_total'].transform(
        lambda x: x.shift().ewm(span=5, adjust=False).mean()
    ).fillna(0)
    
    if verbose:
        print("âœ… defensive_actions_total (tackles + int + clearances*0.5) - Sin leakage")
        print("âœ… def_actions_per_90 (normalizadas) - Sin leakage")
        print("âœ… def_actions_ewma5 (media mÃ³vil) - Sin leakage")
    
    if 'puntosFantasy' in df.columns:
        df['consistency_5games'] = df.groupby('player')['puntosFantasy'].transform(
            lambda x: 1.0 / (1.0 + x.shift().rolling(5, min_periods=2).std().fillna(0))
        ).fillna(0.5)
        df['def_actions_volatility'] = df.groupby('player')['defensive_actions_total'].transform(
            lambda x: x.shift().rolling(5, min_periods=2).std()
        ).fillna(0)
        
        if verbose:
            print("âœ… consistency_5games (inversa a volatilidad) - Sin leakage")
            print("âœ… def_actions_volatility (desviaciÃ³n acciones) - Sin leakage")
    
    if 'tackles_ewma3' in df.columns and 'tackles_ewma5' in df.columns:
        df['tackles_momentum'] = (
            df['tackles_ewma3'] - df['tackles_ewma5']
        ).fillna(0)
        
        if verbose:
            print("âœ… tackles_momentum (ewma3 - ewma5)")
    
    if 'Intercepciones' in df.columns:
        df['int_momentum'] = df.groupby('player')['Intercepciones'].transform(
            lambda x: (x.shift().ewm(3, adjust=False).mean() - 
                      x.shift().ewm(5, adjust=False).mean())
        ).fillna(0)
        
        if verbose:
            print("âœ… int_momentum (trend de intercepciones) - Sin leakage")
    
    if 'fixture_difficulty_home' in df.columns and 'is_home' in df.columns:
        df['defensive_context'] = (
            df['is_home'].fillna(0) * df['fixture_difficulty_home'].fillna(0.5)
        )
        
        if verbose:
            print("âœ… defensive_context (is_home Ã— fixture_difficulty)")
    if 'cs_probability' in df.columns and 'def_actions_per_90' in df.columns:
        df['cs_activity_alignment'] = (
            df['cs_probability'] * df['def_actions_per_90']
        ).fillna(0)
        
        if verbose:
            print("âœ… cs_activity_alignment (CS prob Ã— activity)")
    
    if 'minutes_pct_roll5' in df.columns:
        df['usage_change_recent'] = df.groupby('player')['minutes_pct_roll5'].transform(
            lambda x: x.shift() - x.shift(2)
        ).fillna(0)
        
        if verbose:
            print("âœ… usage_change_recent (cambio en minutos %) - Sin leakage")
    
    if verbose:
        print(f"\nâœ… Fase 2 completada - Features DF creados\n")
    
    return df

def crear_features_fantasy_mediocampista(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    
    
    if verbose:
        print("\n" + "=" * 80)
        print("FEATURES MEDIOCAMPISTA (FANTASY SPECIFIC)")
        print("=" * 80)
    
    df = df.copy()
    
    if 'pases_totales' in df.columns and 'pases_completados_pct' in df.columns:
        df['pass_attempts_per_90'] = (
            df['pases_totales'] / (df['min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        df['pass_accuracy_consistency'] = df.groupby('player')['pases_completados_pct'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(50)
        
        if verbose:
            print("   âœ… Pass accuracy metrics")
    
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
            print("   âœ… Offensive activity metrics")
    
    if 'entradas' in df.columns and 'intercepciones' in df.columns:
        df['defensive_actions_total'] = df['entradas'] + df['intercepciones']
        
        df['defensive_contribution'] = df.groupby('player')['defensive_actions_total'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print("   âœ… Defensive recovery metrics")
    if 'pases_totales' in df.columns and 'entradas' in df.columns:
        df['creative_vs_defensive'] = (
            df.groupby('player')['pases_totales'].transform(lambda x: x.shift().rolling(5, min_periods=1).mean())
            / (df.groupby('player')['entradas'].transform(lambda x: x.shift().rolling(5, min_periods=1).mean()) + 1)
        ).fillna(0)
        
        if verbose:
            print("   âœ… Creative impact index")
    
    if 'puntos_fantasy' in df.columns or 'puntos_fantasy' in df.columns:
        col_pf = 'puntos_fantasy'
        col_pf = col_pf if col_pf in df.columns else 'puntos_fantasy'
        
        if col_pf in df.columns:
            df['pf_volatility_5'] = df.groupby('player')[col_pf].transform(
                lambda x: x.shift().rolling(5, min_periods=2).std()
            ).fillna(0)
            
            df['pf_consistency'] = 1.0 / (1.0 + df['pf_volatility_5'])
            
            if verbose:
                print("   âœ… Consistency metrics")
    
    if 'regates_completados' in df.columns and 'regates' in df.columns:
        total_dribbles = df['regates'] + 0.1
        df['dribble_success_pct'] = (df['regates_completados'] / total_dribbles * 100).fillna(0)
        
        df['dribble_confidence'] = df.groupby('player')['dribble_success_pct'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(50)
        
        if verbose:
            print("   âœ… Dribble success metrics")
    
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
            print("   âœ… Overall activity index")
    
    if 'minutes_pct_ewma5' in df.columns and 'pf_ewma5' in df.columns:
        df['playing_time_form_combo'] = (
            df['minutes_pct_ewma5'] * df['pf_ewma5']
        ).fillna(0)
        
        if verbose:
            print("   âœ… Form adaptation metrics")
    df = df.fillna(0).replace([np.inf, -np.inf], 0)
    
    if verbose:
        print(f"\nâœ… Fase 2 completada - Features MC creados\n")
    
    return df

def crear_features_fantasy_delantero(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    

    if verbose:
        print("\n" + "=" * 80)
        print("FEATURES DELANTERO (FANTASY SPECIFIC - ST/FW)")
        print("=" * 80)

    df = df.copy()

    if 'xg_partido' in df.columns and 'gol_partido' in df.columns:
        df['xg_partido'] = pd.to_numeric(df['xg_partido'], errors='coerce').fillna(0)
        df['gol_partido'] = pd.to_numeric(df['gol_partido'], errors='coerce').fillna(0)
        df['xg_overperformance'] = df.groupby('player').apply(
            lambda x: (x['gol_partido'] - x['xg_partido']).shift().rolling(5, min_periods=1).mean()
        ).reset_index(level=0, drop=True).fillna(0)

        if verbose:
            print("   âœ… xg_overperformance (goles - xG rolling5) - Sin leakage")

    if 'tiros' in df.columns and 'gol_partido' in df.columns:
        df['tiros'] = pd.to_numeric(df['tiros'], errors='coerce').fillna(0)
        df['gol_partido'] = pd.to_numeric(df['gol_partido'], errors='coerce').fillna(0)
        df['shot_conversion_ewma5'] = df.groupby('player').apply(
            lambda g: (g['gol_partido'] / (g['tiros'] + 0.1)).shift().ewm(span=5, adjust=False).mean()
        ).reset_index(level=0, drop=True).fillna(0)

        if verbose:
            print("   âœ… shot_conversion_ewma5 (goles/tiro) - Sin leakage")

    if 'shots_roll5' in df.columns and 'xg_roll5' in df.columns:
        df['offensive_pressure_score'] = (
            df['shots_roll5'] * 0.4 + df['xg_roll5'] * 0.6
        ).fillna(0)

        if verbose:
            print("   âœ… offensive_pressure_score (shots*0.4 + xg*0.6)")

    if 'goals_roll5' in df.columns and 'goals_ewma5' in df.columns:
        df['scoring_stability'] = 1.0 / (
            1.0 + (df['goals_roll5'] - df['goals_ewma5']).abs().fillna(0)
        )

        if verbose:
            print("   âœ… scoring_stability (consistencia goleadora)")

    if 'xg_roll5' in df.columns and 'minutes_pct_ewma5' in df.columns:
        df['xg_per_minute_ewma'] = (
            df['xg_roll5'] / (df['minutes_pct_ewma5'] + 0.1)
        ).fillna(0)

        if verbose:
            print("   âœ… xg_per_minute_ewma (xG por minuto disponible)")

    if 'goals_roll5' in df.columns and 'minutes_pct_ewma5' in df.columns:
        df['goals_per_minute_ewma'] = (
            df['goals_roll5'] / (df['minutes_pct_ewma5'] + 0.1)
        ).fillna(0)

        if verbose:
            print("   âœ… goals_per_minute_ewma (goles por minuto disponible)")

    if 'prog_dribbles_roll5' in df.columns and 'prog_dist_roll5' in df.columns:
        df['progressive_threat'] = (
            df['prog_dribbles_roll5'] * 0.5 + df['prog_dist_roll5'] * 0.01
        ).fillna(0)

        if verbose:
            print("   âœ… progressive_threat (conducciones + distancia progresiva)")

    if 'goals_ewma3' in df.columns and 'goals_ewma5' in df.columns:
        df['scoring_momentum'] = (df['goals_ewma3'] - df['goals_ewma5']).fillna(0)

        if verbose:
            print("   âœ… scoring_momentum (ewma3 - ewma5, tendencia)")

    if 'xg_ewma3' in df.columns and 'xg_ewma5' in df.columns:
        df['xg_momentum'] = (df['xg_ewma3'] - df['xg_ewma5']).fillna(0)

        if verbose:
            print("   âœ… xg_momentum (tendencia xG reciente)")

    if 'puntos_fantasy' in df.columns:
        df['pf_volatility_fw'] = df.groupby('player')['puntos_fantasy'].transform(
            lambda x: x.shift().rolling(5, min_periods=2).std()
        ).fillna(0)

        df['pf_consistency_fw'] = 1.0 / (1.0 + df['pf_volatility_fw'])

        if verbose:
            print("   âœ… pf_volatility_fw / pf_consistency_fw (estabilidad ST)")
    df = df.fillna(0).replace([np.inf, -np.inf], 0)

    if verbose:
        print(f"\nâœ… Features delantero creados correctamente\n")

    return df

def seleccionar_features_por_correlacion(
    X: pd.DataFrame, 
    y: pd.Series,
    target_name: str = 'puntosFantasy',
    threshold: float = 0.03,
    verbose: bool = True
) -> Tuple[List[str], pd.DataFrame]:
    
    
    if verbose:
        print("="*80)
        print(f"SELECCIÃ“N DE FEATURES POR CORRELACIÃ“N ({target_name})")
        print("="*80)
        print()
    
    correlaciones = []
    
    for col in X.columns:
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
    df_corr = pd.DataFrame(correlaciones).sort_values('abs_spearman', ascending=False)
    features_validos = df_corr[
        df_corr['abs_spearman'] >= threshold
    ]['feature'].tolist()
    features_muertos = (df_corr['spearman'] == 0.0).sum()
    features_bajo_threshold = ((df_corr['abs_spearman'] > 0) & (df_corr['abs_spearman'] < threshold)).sum()
    
    if verbose:
        print(f"\n[CHART] Analisis de correlacion:\n")
        print(f"  â€¢ Features muertos (r=0): {features_muertos}")
        print(f"  â€¢ Features bajo threshold (<{threshold}): {features_bajo_threshold}")
        print(f"  â€¢ Features validos (>={threshold}): {len(features_validos)}")
        print(f"  â€¢ Total: {len(df_corr)}")
        
        print(f"\n[TROPHY] TOP 20 Features por |Spearman|:\n")
        for idx, row in df_corr.head(20).iterrows():
            print(f"  {row['feature']:40s} r={row['spearman']:8.4f} (p={row['p_value']:.4f})")
    
    if verbose:
        print(f"\n[OK] Seleccionados {len(features_validos)} features validos\n")
    
    return features_validos, df_corr




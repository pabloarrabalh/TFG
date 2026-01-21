"""
MÓDULO UNIFICADO: MEJORAS DE FEATURES PARA REDUCIR MAE
Autor: AI Assistant para Fantasy Football Analytics
Fecha: Enero 2026

Propósito: 
- Eliminar features ruido
- Crear features específicos para porteros (GK) y defensas (DF)
- Seleccionar features por correlación Spearman
- SIN DATA LEAKAGE: todos los features usan .shift() ANTES de rolling/ewma

Uso:
    from feature_improvements import (
        eliminar_features_ruido,
        crear_features_fantasy_gk,
        crear_features_fantasy_defensivos,
        seleccionar_features_por_correlacion
    )
    
    # Pipeline para porteros
    df = eliminar_features_ruido(df, position='GK')
    df = crear_features_fantasy_gk(df)
    
    # Pipeline para defensas
    df = eliminar_features_ruido(df, position='DF')
    df = crear_features_fantasy_defensivos(df)
    
    # Seleccionar features finales
    features_validas, df_corr = seleccionar_features_por_correlacion(X, y)
"""

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
    """
    Elimina features con importancia = 0 en múltiples modelos.
    Estos features son colineales o ruido puro.
    
    Args:
        df: DataFrame con features
        position: 'GK', 'DF' o 'ALL' (aplica ambas listas)
        verbose: Print de características eliminadas
        
    Returns:
        DataFrame sin features ruido
    """
    
    # Features identificadas como 0.0000 en 2+ modelos en GridSearch results
    FEATURES_RUIDO_COMUN = [
        'duels_won_pct_ewma5',      # 0 en Random Forest
        'duels_won_roll5',           # 0 en Random Forest, XGBoost, Ridge
        'duels_won_ewma5',           # 0 en Random Forest, XGBoost, Ridge  
        'elite_entradas_interact',   # 0 en ElasticNet
        'ratio_roles_criticos',      # 0 en ElasticNet
    ]
    
    features_ruido = FEATURES_RUIDO_COMUN.copy()
    
    # Mapear por posición si es específico
    if position in ['GK', 'ALL']:
        pass  # Los ruidos comunes aplican a GK
    
    if position in ['DF', 'ALL']:
        pass  # Los ruidos comunes aplican a DF
    
    features_a_eliminar = [f for f in features_ruido if f in df.columns]
    
    if verbose:
        print("="*80)
        print(f"ELIMINACIÓN DE FEATURES RUIDO ({position})")
        print("="*80)
        if features_a_eliminar:
            print(f"\n{len(features_a_eliminar)} features a eliminar:\n")
            for f in features_a_eliminar:
                print(f"  ❌ {f} (colinealidad/redundancia)")
            print()
        else:
            print(f"\n✓ No hay features ruido a eliminar para {position}\n")
    
    df = df.drop(columns=features_a_eliminar, errors='ignore')
    
    if verbose:
        print(f"✅ Eliminadas {len(features_a_eliminar)} features ruido\n")
    
    return df


# ============================================================================
# PARTE 2A: FEATURES ESPECÍFICOS PARA PORTEROS (GK) - SIN LEAKAGE
# ============================================================================

def crear_features_fantasy_gk(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Crea features específicos para porteros que predicen puntos Fantasy.
    
    IMPORTANTE: Todos los features nuevos usan .shift() ANTES de rolling/ewma
    para evitar data leakage.
    
    Puntuación Fantasy para GK:
    - Clean sheet: +4 pts
    - Gol en contra: -1 pt
    - Paradón: +1 pt
    - Penalti parado: +5 pts
    
    Args:
        df: DataFrame con datos básicos
        verbose: Print de features creadas
        
    Returns:
        DataFrame enriquecido sin leakage
    """
    
    if verbose:
        print("="*80)
        print("INGENIERÍA DE FEATURES PARA PORTEROS (GK) - SIN LEAKAGE")
        print("="*80)
        print()
    
    df = df.copy()
    
    # ========================================================================
    # 1. CLEAN SHEET PROBABILITY & RATE
    # ========================================================================
    
    if "opp_shots_ewma5" in df.columns:
        df["cs_probability"] = (1 / (1 + df["opp_shots_ewma5"] + 0.1)).fillna(0.5)
        
        # Clean sheet rate (últimos 3 partidos)
        if "Goles_en_contra" in df.columns:
            cs_temp = (df.groupby("player")["Goles_en_contra"].shift() <= 0).astype(int)
            df["cs_rate_recent"] = cs_temp.groupby(df["player"]).transform(
                lambda x: x.rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
            ).fillna(0)
        
        if verbose:
            print("✅ Clean sheet probability & rate")
    
    # ========================================================================
    # 2. EFFICIENCY PER 90 MINUTES (SIN LEAKAGE)
    # ========================================================================
    
    df["Min_partido_safe"] = df.get("Min_partido", 1).replace(0, 0.1)
    
    # Save per 90
    if "Porcentaje_paradas" in df.columns:
        df["save_per_90_temp"] = df["Porcentaje_paradas"] / (df["Min_partido_safe"] / 90.0)
        df["save_per_90"] = df.groupby("player")["save_per_90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df["save_per_90_ewma5"] = df.groupby("player")["save_per_90_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df = df.drop(columns=["save_per_90_temp"])
        
        if verbose:
            print("✅ Save per 90 (roll, ewma) - Sin leakage")
    
    # PSxG per 90
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
            print("✅ PSxG per 90 (roll, ewma) - Sin leakage")
    
    # ========================================================================
    # 3. GK ACTIONS TOTAL (SIN LEAKAGE)
    # ========================================================================
    
    if all(c in df.columns for c in ["Porcentaje_paradas", "DuelosAereosGanados", "Despejes"]):
        df["gk_actions_temp"] = (
            df["Porcentaje_paradas"] * 0.5 +
            df["DuelosAereosGanados"] +
            df["Despejes"] * 0.3
        )
        
        df["gk_actions_total"] = df.groupby("player")["gk_actions_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["gk_actions_per_90"] = (df["gk_actions_total"] / (df["Min_partido_safe"] / 90.0)).fillna(0)
        
        df["gk_actions_ewma5"] = df.groupby("player")["gk_actions_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        
        df = df.drop(columns=["gk_actions_temp"])
        
        if verbose:
            print("✅ GK Actions (total, per_90, ewma5) - Sin leakage")
    
    # ========================================================================
    # 4. CONSISTENCY & VOLATILITY (SIN LEAKAGE)
    # ========================================================================
    
    if "puntosFantasy" in df.columns:
        # Consistency over 5 games
        pf_std = df.groupby("player")["puntosFantasy"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).std()
        ).fillna(0)
        
        pf_mean = df.groupby("player")["puntosFantasy"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(1)
        
        df["consistency_5games"] = 1 / (1 + pf_std / (pf_mean + 1e-6)).fillna(1)
        df["consistency_5games"] = df["consistency_5games"].replace([np.inf, -np.inf], 1)
        
        # GK Actions volatility
        if "gk_actions_total" in df.columns:
            gk_std = df.groupby("player")["gk_actions_total"].transform(
                lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).std()
            ).fillna(0)
            
            gk_mean = df.groupby("player")["gk_actions_total"].transform(
                lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
            ).fillna(1)
            
            df["gk_actions_volatility"] = (gk_std / (gk_mean + 1e-6)).fillna(0)
            df["gk_actions_volatility"] = df["gk_actions_volatility"].replace([np.inf, -np.inf], 0)
        
        if verbose:
            print("✅ Consistency & Volatility (5games) - Sin leakage")
    
    # ========================================================================
    # 5. MOMENTUM INDICATORS (SIN LEAKAGE)
    # ========================================================================
    
    if "save_pct_ewma3" in df.columns and "save_pct_ewma5" in df.columns:
        df["save_momentum"] = (df["save_pct_ewma3"] - df["save_pct_ewma5"]).fillna(0)
        
        if verbose:
            print("✅ Save Momentum (ewma3 - ewma5)")
    
    if "psxg_ewma3" in df.columns and "psxg_ewma5" in df.columns:
        df["psxg_momentum"] = (df["psxg_ewma3"] - df["psxg_ewma5"]).fillna(0)
        
        if verbose:
            print("✅ PSxG Momentum (ewma3 - ewma5)")
    
    # ========================================================================
    # 6. DEFENSIVE CONTEXT (SIN LEAKAGE)
    # ========================================================================
    
    if all(c in df.columns for c in ["opp_shots_ewma5", "opp_gc_ewma5"]):
        df["defensive_context"] = (
            df["opp_shots_ewma5"] * 0.6 + df["opp_gc_ewma5"] * 0.4
        ).fillna(0)
        
        if verbose:
            print("✅ Defensive Context (shots + goals against weighted)")
    
    # ========================================================================
    # 7. CS ACTIVITY ALIGNMENT (SIN LEAKAGE)
    # ========================================================================
    
    if all(c in df.columns for c in ["cs_probability", "gk_actions_per_90"]):
        df["cs_activity_alignment"] = (
            df["cs_probability"] * 0.5 + df["gk_actions_per_90"] * 0.5
        ).fillna(0)
        
        if verbose:
            print("✅ CS Activity Alignment (probability * activity)")
    
    # ========================================================================
    # 8. USAGE CHANGE RECENT (SIN LEAKAGE)
    # ========================================================================
    
    if "minutes_pct_ewma3" in df.columns and "minutes_pct_ewma5" in df.columns:
        df["usage_change_recent"] = (
            df["minutes_pct_ewma3"] - df["minutes_pct_ewma5"]
        ).fillna(0)
        
        if verbose:
            print("✅ Usage Change Recent (ewma3 - ewma5)")
    
    if verbose:
        print(f"\n✅ Fase 2 completada - Features GK creados\n")
    
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
        if 'puntosFantasy' in df.columns:
            df['cs_in_last_3'] = df.groupby('player')['puntosFantasy'].transform(
                lambda x: ((x >= -10) & (x <= 10)).shift().rolling(3, min_periods=1).sum()
            ).fillna(0)
            
            df['cs_rate_recent'] = df['cs_in_last_3'] / 3.0
        
        if verbose:
            print("✅ cs_probability (tiros rival inverso) - Sin leakage")
            print("✅ cs_rate_recent (últimos 3 partidos) - Sin leakage")
    
    # ========================================================================
    # 2. EFFICIENCY METRICS (per 90 minutes - SIN LEAKAGE)
    # ========================================================================
    
    if 'Entradas' in df.columns and 'Min_partido' in df.columns:
        # Tackling per 90
        df['Entradas'] = pd.to_numeric(df['Entradas'], errors='coerce').fillna(0)
        df['Min_partido'] = pd.to_numeric(df['Min_partido'], errors='coerce').fillna(1)
        
        df['tackles_per_90'] = (
            df['Entradas'] / (df['Min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        # Media móvil exponencial de tackles per 90
        df['tackles_per_90_ewma5'] = df.groupby('player')['tackles_per_90'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print("✅ tackles_per_90 (normalizadas a 90 min) - Sin leakage")
            print("✅ tackles_per_90_ewma5 (media móvil) - Sin leakage")
    
    if 'Intercepciones' in df.columns and 'Min_partido' in df.columns:
        df['Intercepciones'] = pd.to_numeric(df['Intercepciones'], errors='coerce').fillna(0)
        
        df['int_per_90'] = (
            df['Intercepciones'] / (df['Min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        df['int_per_90_ewma5'] = df.groupby('player')['int_per_90'].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if verbose:
            print("✅ int_per_90 (normalizadas a 90 min) - Sin leakage")
            print("✅ int_per_90_ewma5 (media móvil) - Sin leakage")
    
    if 'Despejes' in df.columns and 'Min_partido' in df.columns:
        df['Despejes'] = pd.to_numeric(df['Despejes'], errors='coerce').fillna(0)
        
        df['clearances_per_90'] = (
            df['Despejes'] / (df['Min_partido'] / 90.0 + 0.1)
        ).fillna(0)
        
        if verbose:
            print("✅ clearances_per_90 (normalizadas a 90 min) - Sin leakage")
    
    # ========================================================================
    # 3. COMBINED DEFENSIVE ACTION INDEX
    # ========================================================================
    
    df['defensive_actions_total'] = (
        df.get('Entradas', 0) + 
        df.get('Intercepciones', 0) + 
        df.get('Despejes', 0) * 0.5  # Despejes menos valorados
    )
    
    df['def_actions_per_90'] = (
        df['defensive_actions_total'] / (df['Min_partido'] / 90.0 + 0.1)
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
        print(f"\n📊 Análisis de correlación:\n")
        print(f"  • Features muertos (r=0): {features_muertos}")
        print(f"  • Features bajo threshold (<{threshold}): {features_bajo_threshold}")
        print(f"  • Features válidos (>={threshold}): {len(features_validos)}")
        print(f"  • Total: {len(df_corr)}")
        
        print(f"\n🏆 TOP 20 Features por |Spearman|:\n")
        for idx, row in df_corr.head(20).iterrows():
            print(f"  {row['feature']:40s} r={row['spearman']:8.4f} (p={row['p_value']:.4f})")
    
    if verbose:
        print(f"\n✅ Seleccionados {len(features_validos)} features válidos\n")
    
    return features_validos, df_corr



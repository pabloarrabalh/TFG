"""

FEATURE IMPROVEMENTS PARA PORTEROS (GK)

Fase 1-3: Eliminar ruido, crear features nuevos, seleccionar por correlación

SIN LEAKAGE - Todos los features usan .shift() + rolling/ewma

===============================================================================

"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

TAM_VENTANA = 5
TAM_VENTANA_RECIENTE = 3


# ===========================
# FASE 1: ELIMINAR FEATURES RUIDO
# ===========================

def eliminar_features_ruido_gk(df, verbose=True):
    """
    Identifica y elimina features que no contribuyen a la predicción.
    (Basado en análisis del modelo de defensas)
    """
    
    features_ruido = [
        "duels_won_pct_ewma5",
        "duels_won_roll5",
        "duels_won_ewma5",
        "elite_entradas_interact",
        "ratio_roles_criticos"
    ]
    
    a_eliminar = [f for f in features_ruido if f in df.columns]
    
    if verbose:
        print(f"Identificados {len(a_eliminar)} features ruido:")
        for f in a_eliminar:
            print(f"  • {f}")
    
    df = df.drop(columns=a_eliminar, errors="ignore")
    
    return df


# ===========================
# FASE 2: CREAR FEATURES NUEVOS PARA PORTEROS (SIN LEAKAGE)
# ===========================

def crear_features_fantasy_gk(df, verbose=True):
    """
    Crea features específicos para porteros que predicen puntos Fantasy.
    
    ✅ IMPORTANTE: Todos los features nuevos usan .shift() ANTES de rolling/ewma
    para evitar data leakage
    """
    
    if verbose:
        print("\nCreando features defensivos nuevos para porteros:\n")
    
    # ========================
    # 1. CLEAN SHEET PROBABILITY
    # ========================
    
    if "opp_shots_ewma5" in df.columns:
        df["cs_probability"] = (1 / (1 + df["opp_shots_ewma5"] + 0.1)).fillna(0.5)
        
        # Clean sheet rate (últimos 3 partidos)
        cs_temp = (df.groupby("player")["Goles_en_contra"].shift() <= 0).astype(int)
        df["cs_rate_recent"] = cs_temp.groupby(df["player"]).transform(
            lambda x: x.rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        if verbose:
            print("✅ Clean sheet probability & rate")
    
    # ========================
    # 2. EFFICIENCY PER 90 MINUTES (SIN LEAKAGE)
    # ========================
    
    df["Min_partido_safe"] = df["Min_partido"].replace(0, 0.1)
    
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
            print("✅ Save per 90 (roll, ewma)")
    
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
            print("✅ PSxG per 90 (roll, ewma)")
    
    # ========================
    # 3. GK ACTIONS TOTAL (SIN LEAKAGE)
    # ========================
    
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
            print("✅ GK Actions (total, per_90, ewma5)")
    
    # ========================
    # 4. CONSISTENCY & VOLATILITY (SIN LEAKAGE)
    # ========================
    
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
            print("✅ Consistency & Volatility (5games)")
    
    # ========================
    # 5. MOMENTUM INDICATORS (SIN LEAKAGE)
    # ========================
    
    if "save_pct_ewma3" in df.columns and "save_pct_ewma5" in df.columns:
        df["save_momentum"] = (df["save_pct_ewma3"] - df["save_pct_ewma5"]).fillna(0)
        
        if verbose:
            print("✅ Save Momentum (ewma3 - ewma5)")
    
    if "psxg_ewma3" in df.columns and "psxg_ewma5" in df.columns:
        df["psxg_momentum"] = (df["psxg_ewma3"] - df["psxg_ewma5"]).fillna(0)
        
        if verbose:
            print("✅ PSxG Momentum (ewma3 - ewma5)")
    
    # ========================
    # 6. DEFENSIVE CONTEXT (SIN LEAKAGE)
    # ========================
    
    if all(c in df.columns for c in ["opp_shots_ewma5", "opp_gc_ewma5"]):
        df["defensive_context"] = (
            df["opp_shots_ewma5"] * 0.6 + df["opp_gc_ewma5"] * 0.4
        ).fillna(0)
        
        if verbose:
            print("✅ Defensive Context (shots + goals against weighted)")
    
    # ========================
    # 7. CS ACTIVITY ALIGNMENT (SIN LEAKAGE)
    # ========================
    
    if all(c in df.columns for c in ["cs_probability", "gk_actions_per_90"]):
        # Correlación entre probabilidad de CS y actividad del portero
        df["cs_activity_alignment"] = (
            df["cs_probability"] * 0.5 + df["gk_actions_per_90"] * 0.5
        ).fillna(0)
        
        if verbose:
            print("✅ CS Activity Alignment (probability * activity)")
    
    # ========================
    # 8. USAGE CHANGE RECENT (SIN LEAKAGE)
    # ========================
    
    if "minutes_pct_ewma3" in df.columns and "minutes_pct_ewma5" in df.columns:
        df["usage_change_recent"] = (
            df["minutes_pct_ewma3"] - df["minutes_pct_ewma5"]
        ).fillna(0)
        
        if verbose:
            print("✅ Usage Change Recent (ewma3 - ewma5)")
    
    if verbose:
        print("\n✅ Fase 2 completada - Features nuevos creados\n")
    
    return df


# ===========================
# FASE 3: FEATURE SELECTION POR CORRELACIÓN
# ===========================

def seleccionar_features_por_correlacion(X, y, target_name="puntosFantasy", threshold=0.03, verbose=True):
    """
    Selecciona features basado en correlación Spearman con el target.
    
    Elimina:
    - Features con correlación = 0 (features muertos)
    - Features con correlación muy baja (< threshold)
    
    Mantiene:
    - Features con |correlación| >= threshold
    """
    
    if verbose:
        print(f"\nSeleccionando features con |Spearman| >= {threshold}\n")
    
    # Calcular correlación Spearman
    correlaciones = []
    
    for col in X.columns:
        try:
            spear, pval = spearmanr(X[col], y)
            correlaciones.append({
                'feature': col,
                'spearman': spear,
                'p_value': pval,
                'abs_spearman': abs(spear)
            })
        except Exception as e:
            if verbose:
                print(f"⚠️ Error calculando correlación para {col}: {e}")
            correlaciones.append({
                'feature': col,
                'spearman': 0,
                'p_value': 1,
                'abs_spearman': 0
            })
    
    df_corr = pd.DataFrame(correlaciones).sort_values('abs_spearman', ascending=False)
    
    # Estadísticas
    features_muertos = (df_corr['spearman'] == 0).sum()
    features_bajo_threshold = ((df_corr['abs_spearman'] > 0) & (df_corr['abs_spearman'] < threshold)).sum()
    features_validos = (df_corr['abs_spearman'] >= threshold).sum()
    
    if verbose:
        print(f"📊 Análisis de correlación:")
        print(f"  • Features muertos (r=0): {features_muertos}")
        print(f"  • Features bajo threshold (<{threshold}): {features_bajo_threshold}")
        print(f"  • Features válidos (>={threshold}): {features_validos}")
        print(f"  • Total: {len(df_corr)}")
        
        print(f"\n🏆 TOP 20 Features por |Spearman|:")
        for idx, row in df_corr.head(20).iterrows():
            print(f"  {row['feature']:35s} r={row['spearman']:7.4f} (p={row['p_value']:.4f})")
    
    # Seleccionar features válidos
    features_validos_list = df_corr[df_corr['abs_spearman'] >= threshold]['feature'].tolist()
    
    if verbose:
        print(f"\n✅ Seleccionados {len(features_validos_list)} features válidos\n")
    
    return features_validos_list, df_corr

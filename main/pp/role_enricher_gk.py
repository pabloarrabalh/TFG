"""

ROLE ENRICHER PARA PORTEROS (GK)

Roles FBRef específicos para porteros y features de interacción

===============================================================================

"""

import numpy as np
import pandas as pd

# Roles críticos para porteros
ROLES_CRITICOS_GK = {
    "paradas": 1.5,           # Saves - MUY IMPORTANTE
    "distribucion": 1.2,      # Distribution
    "manejo": 1.3,            # Handling - CRÍTICO
    "salidas": 1.1,           # Rushing/Distribution
    "comando": 1.2,           # Command of Box
    "posicionamiento": 1.0,   # Positioning
    "minutos": 1.1,
    "apariciones_suplente": 0.3,
    "amarillas": -0.6,
    "rojas": -1.2,
}


def enriquecer_dataframe_con_roles_gk(df, columna_roles="roles"):
    """
    Enriquece el dataframe con información de roles de porteros.
    """
    
    print("=" * 80)
    print("ENRIQUECIMIENTO CON ROLES DE PORTEROS")
    print("=" * 80)
    
    if columna_roles not in df.columns:
        print(f"⚠️ Columna '{columna_roles}' no encontrada.")
        print("   Creando roles por defecto...\n")
        df["role_saves"] = 1
        df["role_distribution"] = 0.8
        df["role_handling"] = 0.9
        return df
    
    # Parsear roles
    for role_name, weight in ROLES_CRITICOS_GK.items():
        if role_name in ["minutos", "apariciones_suplente", "amarillas", "rojas"]:
            continue
        
        df[f"role_{role_name}"] = df[columna_roles].apply(
            lambda x: 1 if isinstance(x, str) and role_name.lower() in x.lower() else 0
        )
    
    print("✅ Roles de porteros parseados\n")
    
    return df


def crear_features_gk_roles(df, columna_objetivo="puntosFantasy"):
    """
    Crea features de interacción basados en roles de porteros.
    """
    
    print("Creando features de interacción con roles:\n")
    
    # Elite saves interaction
    if "save_pct_ewma5" in df.columns:
        save_pct_elite = df["save_pct_ewma5"].quantile(0.75)
        df["elite_saves_interact"] = (
            (df["save_pct_ewma5"] >= save_pct_elite).astype(int) *
            df.get("pf_ewma5", 0)
        )
        print("✅ Elite saves interaction")
    
    # Elite distribution interaction
    if "pass_comp_pct_ewma5" in df.columns:
        pass_pct_elite = df["pass_comp_pct_ewma5"].quantile(0.75)
        df["elite_distribution_interact"] = (
            (df["pass_comp_pct_ewma5"] >= pass_pct_elite).astype(int) *
            df.get("pf_ewma5", 0)
        )
        print("✅ Elite distribution interaction")
    
    # Elite handling interaction
    if "clearances_ewma5" in df.columns:
        clear_elite = df["clearances_ewma5"].quantile(0.75)
        df["elite_handling_interact"] = (
            (df["clearances_ewma5"] >= clear_elite).astype(int) *
            df.get("pf_ewma5", 0)
        )
        print("✅ Elite handling interaction")
    
    # Role score (ponderado)
    score_cols = [
        "save_pct_ewma5", "psxg_ewma5", "pass_comp_pct_ewma5",
        "clearances_ewma5", "aerial_won_ewma5"
    ]
    
    score_cols = [c for c in score_cols if c in df.columns]
    
    if score_cols:
        # Normalizar cada score
        df_norm = df[score_cols].copy()
        for col in df_norm.columns:
            df_norm[col] = (df_norm[col] - df_norm[col].mean()) / (df_norm[col].std() + 1e-6)
            df_norm[col] = df_norm[col].fillna(0)
        
        # Score ponderado
        weights = [1.5, 1.2, 1.0, 0.8, 1.1]  # Pesos por rol
        df["score_roles_normalizado"] = (df_norm.iloc[:, :len(weights)] * weights).sum(axis=1) / sum(weights[:len(score_cols)])
        df["score_roles_normalizado"] = df["score_roles_normalizado"].fillna(0)
        
        print("✅ Score roles normalizado")
    
    # Indicador de rol GK core
    gk_core_cols = [
        "elite_saves_interact", "elite_distribution_interact", "elite_handling_interact"
    ]
    
    gk_core_cols = [c for c in gk_core_cols if c in df.columns]
    
    if gk_core_cols:
        df["num_roles_criticos"] = (df[gk_core_cols] > 0).sum(axis=1)
        df["ratio_roles_criticos"] = df["num_roles_criticos"] / len(gk_core_cols)
        df["tiene_rol_gk_core"] = (df["num_roles_criticos"] > 0).astype(int)
        df["score_gk"] = df["score_roles_normalizado"] * df["tiene_rol_gk_core"]
        
        print("✅ Indicadores de rol GK core")
    
    print()
    
    return df


def resumen_roles_gk(df):
    """
    Muestra resumen de roles de porteros en el dataframe.
    """
    
    print("=" * 80)
    print("RESUMEN DE ROLES DE PORTEROS")
    print("=" * 80)
    
    role_cols = [c for c in df.columns if c.startswith("role_")]
    
    if role_cols:
        print("\nRoles encontrados:")
        for col in role_cols:
            count = df[col].sum()
            pct = 100 * count / len(df)
            print(f"  • {col:30s}: {count:4.0f} porteros ({pct:5.1f}%)")
    
    interaction_cols = [
        "elite_saves_interact", "elite_distribution_interact",
        "elite_handling_interact", "score_roles_normalizado",
        "num_roles_criticos", "tiene_rol_gk_core", "score_gk"
    ]
    
    interaction_cols = [c for c in interaction_cols if c in df.columns]
    
    if interaction_cols:
        print("\nFeatures de interacción:")
        for col in interaction_cols:
            print(f"  • {col:30s}: media={df[col].mean():7.4f} std={df[col].std():7.4f}")
    
    print()

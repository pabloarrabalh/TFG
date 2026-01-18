"""
===============================================================================

MÓDULO DE INTEGRACIÓN DE ROLES DEFENSIVOS (FBRef) - SOLO DEFENSAS

===============================================================================

Enriquecimiento robusto para defensas con atributos: Tackles, Interceptions,
Clearances, Successful Take-Ons, Minutes, Substitute Appearances, Yellow Cards,
Red Cards, Fouls Committed, Fouls Drawn

Autor: Pablo
Fecha: Enero 2026

===============================================================================
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import json

# ===========================
# CONFIGURACIÓN DE ROLES DEFENSIVOS
# ===========================

# Roles críticos para DEFENSAS (todos son DF: centrales, laterales, wing backs)
# Ponderación por importancia en Fantasy Football
ROLES_CRITICOS_DEFENSAS = {
    "entradas": 1.3,              # Tackles - muy importante
    "intercepciones": 1.4,        # Interceptions - crítico
    "despejes": 1.2,              # Clearances - importante
    "regates_exitosos": 0.8,      # Successful Take-Ons - neutralizar oponentes
    "minutos": 1.1,               # Minutes - disponibilidad
    "apariciones_suplente": 0.3,  # Substitute Appearances - menos valor
    "amarillas": -0.6,            # Yellow Cards - castigo
    "rojas": -1.2,                # Red Cards - castigo severo
    "faltas_cometidas": -0.4,     # Fouls Committed - indisciplina
    "faltas_recibidas": 0.4,      # Fouls Drawn - resistencia
}

# Todos los roles reconocibles (general)
ROLES_TODOS = {
    "entradas": 1.3,
    "intercepciones": 1.4,
    "despejes": 1.2,
    "regates_exitosos": 0.8,
    "minutos": 1.1,
    "apariciones_suplente": 0.3,
    "amarillas": -0.6,
    "rojas": -1.2,
    "faltas_cometidas": -0.4,
    "faltas_recibidas": 0.4,
    "goles": 0.5,
    "asistencias": 0.6,
    "tiros_puerta": 0.3,
    "pases_clave": 0.4,
    "pases_completados_pct": 0.3,
}

# ===========================
# FUNCIONES DE PARSING
# ===========================

def parsear_roles_json(rol_json_str) -> Dict[str, tuple]:
    """
    Parsea la columna de roles JSON y extrae {rol_clave: (posicion, valor)}
    
    Maneja múltiples formatos:
    - "[{'entradas': [1, 5.2]}, {'intercepciones': [3, 4.1]}, ...]"
    - JSON válido
    - Listas vacías
    - Valores None/NaN
    
    Returns:
    dict: {rol_clave: (posicion, valor), ...}
    """
    if pd.isna(rol_json_str):
        return {}
    
    if not isinstance(rol_json_str, (str, list)):
        return {}
    
    # Si es lista, procesarla directamente
    if isinstance(rol_json_str, list):
        if len(rol_json_str) == 0:
            return {}
        rol_list = rol_json_str
    else:
        # Es string
        rol_json_str = rol_json_str.strip()
        if rol_json_str == "[]" or rol_json_str == "":
            return {}
        
        try:
            rol_list = json.loads(rol_json_str)
        except:
            try:
                import ast
                rol_list = ast.literal_eval(rol_json_str)
            except:
                return {}
    
    if not isinstance(rol_list, list) or len(rol_list) == 0:
        return {}
    
    # Extraer roles
    roles_dict = {}
    for item in rol_list:
        if isinstance(item, dict):
            for clave_rol, valores in item.items():
                if isinstance(valores, (list, tuple)) and len(valores) >= 2:
                    try:
                        posicion = int(valores[0])
                        valor = float(valores[1])
                        roles_dict[clave_rol.lower().strip()] = (posicion, valor)
                    except (ValueError, TypeError):
                        continue
    
    return roles_dict

def calcular_score_roles_defensivos(roles_dict: Dict[str, tuple]) -> float:
    """
    Calcula score ponderado de roles con factor de posición.
    Específico para defensas.
    
    Score = suma(valor * multiplicador * factor_posicion)
    """
    score = 0.0
    
    for rol_clave, (posicion, valor) in roles_dict.items():
        # Multiplicador del rol defensivo
        multiplicador = ROLES_CRITICOS_DEFENSAS.get(
            rol_clave, 
            ROLES_TODOS.get(rol_clave, 0.5)
        )
        
        # Factor de posición: penaliza si está bajo en ranking
        factor_posicion = max(1.0 - (posicion - 1) / 100.0, 0.1)
        
        score += valor * multiplicador * factor_posicion
    
    return score

# ===========================
# FUNCIONES PRINCIPALES
# ===========================

def enriquecer_dataframe_con_roles_defensivos(df: pd.DataFrame,
                                             columna_roles: str = "roles") -> pd.DataFrame:
    """
    Enriquece el dataframe con información de roles defensivos (DF).
    
    Crea columnas:
    - num_roles: cantidad de roles
    - score_roles: score ponderado global
    - tiene_rol_destacado: indicador binario
    - es_defensa_elite: top 25% en score
    - rol_{rol_key}_valor: valor específico de cada rol crítico
    - rol_{rol_key}_posicion: ranking específico
    
    CRÍTICO: Rellena NaNs de roles con 0 (no tiene ese rol)
    """
    
    print("=" * 80)
    print("ENRIQUECIMIENTO CON ROLES DEFENSIVOS (FBRef) - SOLO DEFENSAS")
    print("=" * 80)
    
    if columna_roles not in df.columns:
        print(f"⚠️  Columna '{columna_roles}' no encontrada.\n")
        return df
    
    print(f"\nParseando roles desde columna '{columna_roles}'...")
    
    # Parsear roles
    df_temp = df.copy()
    df_temp["roles_parsed"] = df_temp[columna_roles].apply(parsear_roles_json)
    
    # Contar roles
    df["num_roles"] = df_temp["roles_parsed"].apply(len)
    df["tiene_rol_destacado"] = (df["num_roles"] > 0).astype(int)
    
    con_roles = df["num_roles"].sum()
    print(f"✓ Defensas con roles: {con_roles} / {len(df)}")
    
    # Score global
    print(f"\nCalculando score ponderado de roles defensivos...")
    df["score_roles"] = df_temp["roles_parsed"].apply(calcular_score_roles_defensivos)
    
    if con_roles > 0:
        score_media = df[df['num_roles'] > 0]['score_roles'].mean()
        score_std = df[df['num_roles'] > 0]['score_roles'].std()
        print(f"✓ Score de roles - Media: {score_media:.2f}, Std: {score_std:.2f}")
    
    # Elite: top 25%
    if con_roles > 0:
        threshold_elite = df[df["num_roles"] > 0]["score_roles"].quantile(0.75)
        df["es_defensa_elite"] = (df["score_roles"] >= threshold_elite).astype(int)
        elite_count = df["es_defensa_elite"].sum()
        print(f"✓ Defensas elite (top 25%): {elite_count}")
    else:
        df["es_defensa_elite"] = 0
    
    # Extraer roles críticos defensivos
    print(f"\nExtrayendo roles críticos para defensas:")
    for rol_clave in ROLES_CRITICOS_DEFENSAS.keys():
        df[f"rol_{rol_clave}_valor"] = df_temp["roles_parsed"].apply(
            lambda x: x.get(rol_clave, (np.nan, np.nan))[1]
        )
        df[f"rol_{rol_clave}_posicion"] = df_temp["roles_parsed"].apply(
            lambda x: x.get(rol_clave, (np.nan, np.nan))[0]
        )
        
        tiene_rol = df[f"rol_{rol_clave}_valor"].notna().sum()
        print(f" ✓ rol_{rol_clave}: {tiene_rol} defensas")
    
    # CRÍTICO: Rellenar NaNs de roles con 0
    rol_cols = [c for c in df.columns if c.startswith("rol_")]
    for col in rol_cols:
        df[col] = df[col].fillna(0)
    
    print("\n✅ Enriquecimiento con roles defensivos completado\n")
    
    return df

def crear_features_defensivas_roles(df: pd.DataFrame,
                                   columna_objetivo: Optional[str] = None) -> pd.DataFrame:
    """
    Crea variables de interacción entre roles defensivos y performance.
    
    Variables:
    - elite_entradas_interact
    - elite_intercepciones_interact
    - elite_despejes_interact
    - score_roles_normalizado
    - num_roles_criticos
    - ratio_roles_criticos
    - tiene_rol_defensivo
    """
    
    print("=" * 80)
    print("INGENIERÍA DE VARIABLES DE INTERACCIÓN (ROLES DEFENSIVOS + PERFORMANCE)")
    print("=" * 80)
    
    print("\nVariables de interacción roles-performance:\n")
    
    # 1. Elite × Entradas
    if "es_defensa_elite" in df.columns and "rol_entradas_valor" in df.columns:
        df["elite_entradas_interact"] = (
            df["es_defensa_elite"].fillna(0).astype(float) *
            df["rol_entradas_valor"].fillna(0).astype(float)
        )
        print(" ✓ elite_entradas_interact")
    
    # 2. Elite × Intercepciones
    if "es_defensa_elite" in df.columns and "rol_intercepciones_valor" in df.columns:
        df["elite_intercepciones_interact"] = (
            df["es_defensa_elite"].fillna(0).astype(float) *
            df["rol_intercepciones_valor"].fillna(0).astype(float)
        )
        print(" ✓ elite_intercepciones_interact")
    
    # 3. Elite × Despejes
    if "es_defensa_elite" in df.columns and "rol_despejes_valor" in df.columns:
        df["elite_despejes_interact"] = (
            df["es_defensa_elite"].fillna(0).astype(float) *
            df["rol_despejes_valor"].fillna(0).astype(float)
        )
        print(" ✓ elite_despejes_interact")
    
    # 4. Score normalizado
    if "score_roles" in df.columns:
        df["score_roles_normalizado"] = df["score_roles"].fillna(0).astype(float)
        print(" ✓ score_roles_normalizado")
    
    # 5. Contar roles críticos específicos
    roles_criticos_cols = [c for c in df.columns
                          if any(rc in c for rc in ROLES_CRITICOS_DEFENSAS.keys())
                          and c.endswith("_valor")]
    
    if len(roles_criticos_cols) > 0:
        df["num_roles_criticos"] = (df[roles_criticos_cols] > 0).sum(axis=1)
        print(f" ✓ num_roles_criticos (basado en {len(roles_criticos_cols)} roles)")
    
    # 6. Ratio roles críticos
    if "num_roles_criticos" in df.columns and "num_roles" in df.columns:
        df["ratio_roles_criticos"] = (
            df["num_roles_criticos"] / (df["num_roles"] + 1)
        ).fillna(0)
        print(" ✓ ratio_roles_criticos")
    
    # 7. Tiene rol defensivo core (entradas + intercepciones + despejes)
    roles_defensivos_core = {"entradas", "intercepciones", "despejes"}
    rol_def_core_cols = [c for c in df.columns
                        if any(rc in c for rc in roles_defensivos_core)
                        and c.endswith("_valor")]
    
    if len(rol_def_core_cols) > 0:
        df["tiene_rol_defensivo_core"] = (df[rol_def_core_cols] > 0).any(axis=1).astype(int)
        count = df["tiene_rol_defensivo_core"].sum()
        print(f" ✓ tiene_rol_defensivo_core ({count} defensas)")
    
    # 8. Score defensivo (solo roles defensivos)
    def calcular_score_defensivo(row):
        score = 0.0
        for rol_key in roles_defensivos_core:
            col_valor = f"rol_{rol_key}_valor"
            if col_valor in row.index and row[col_valor] > 0:
                multiplicador = ROLES_CRITICOS_DEFENSAS.get(rol_key, 0.5)
                score += row[col_valor] * multiplicador
        return score
    
    df["score_defensivo"] = df.apply(calcular_score_defensivo, axis=1)
    print(" ✓ score_defensivo (sum: entradas + intercepciones + despejes ponderadas)")
    
    print("\n✅ Variables de interacción defensivas creadas\n")
    
    return df

def resumen_roles_defensivos(df: pd.DataFrame) -> None:
    """
    Imprime resumen detallado de roles defensivos en el dataset.
    """
    
    print("=" * 80)
    print("RESUMEN DE ROLES DEFENSIVOS EN EL DATASET")
    print("=" * 80 + "\n")
    
    total = len(df)
    con_roles = (df["num_roles"] > 0).sum() if "num_roles" in df.columns else 0
    sin_roles = total - con_roles
    
    print(f"Total de registros (defensas): {total}")
    print(f"Registros con roles: {con_roles} ({con_roles/total*100:.1f}%)")
    print(f"Registros sin roles: {sin_roles} ({sin_roles/total*100:.1f}%)")
    
    if "num_roles" in df.columns:
        print("\nDistribución de número de roles por defensa:")
        print(df["num_roles"].value_counts().sort_index())
    
    if "score_roles" in df.columns and con_roles > 0:
        print(f"\nEstadísticas de score_roles (solo con roles):")
        scores = df[df["num_roles"] > 0]["score_roles"]
        print(f" Media: {scores.mean():.2f}")
        print(f" Std: {scores.std():.2f}")
        print(f" Min: {scores.min():.2f}")
        print(f" Max: {scores.max():.2f}")
    
    print(f"\nRoles críticos defensivos más frecuentes:")
    for rol_clave in ROLES_CRITICOS_DEFENSAS.keys():
        col_valor = f"rol_{rol_clave}_valor"
        if col_valor in df.columns:
            count = (df[col_valor] > 0).sum()
            if count > 0:
                media = df[df[col_valor] > 0][col_valor].mean()
                print(f" {rol_clave:20s}: {count:4d} defensas, media={media:6.2f}")
    
    print()

if __name__ == "__main__":
    print("Módulo role_enricher_defensas.py cargado correctamente.")
    print("\nFunciones disponibles:")
    print(" - enriquecer_dataframe_con_roles_defensivos(df, columna_roles='roles')")
    print(" - crear_features_defensivas_roles(df, columna_objetivo=None)")
    print(" - resumen_roles_defensivos(df)")

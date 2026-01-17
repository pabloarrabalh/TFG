"""
===============================================================================
MÓDULO DE INTEGRACIÓN DE ROLES DESTACADOS (FBRef)
===============================================================================
Enriquecimiento robusto de datos con información de roles
Autor: Pablo
Fecha: Enero 2026
===============================================================================
"""


import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import json



# ===========================
# CONFIGURACIÓN DE ROLES
# ===========================

# Roles críticos para porteros (ponderación por importancia)
ROLES_CRITICOS_PORTEROS = {
    "paradas": 1.5,
    "save_pct": 1.4,
    "porterias_cero": 1.5,
    "minutos": 1.2,
    "despejes": 1.1,
}

# Todos los roles reconocibles
ROLES_TODOS = {
    "goles": 1.0,
    "goles_90": 1.0,
    "asistencias": 1.0,
    "asistencias_90": 1.0,
    "penaltis_marcados": 0.8,
    "tiros_puerta": 0.8,
    "goles_por_tiro": 0.9,
    "pases_clave": 0.7,
    "pases_completados_pct": 0.6,
    "pases_ultimo_tercio": 0.6,
    "centros_area": 0.6,
    "corners": 0.5,
    "entradas": 0.7,
    "intercepciones": 0.7,
    "despejes": 1.1,
    "regates_exitosos": 0.6,
    "minutos": 1.2,
    "apariciones_suplente": 0.3,
    "amarillas": -0.7,
    "rojas": -0.5,
    "faltas_cometidas": -0.5,
    "faltas_recibidas": 0.5,
    "porterias_cero": 1.5,
    "paradas": 1.5,
    "save_pct": 1.4,
}


# ===========================
# FUNCIONES DE PARSING
# ===========================

def parsear_roles_json(rol_json_str) -> Dict[str, tuple]:
    """
    Parsea la columna de roles JSON y extrae {rol_clave: (posicion, valor)}
    
    Maneja múltiples formatos:
    - "[{'paradas': [1, 80.0]}, {'porterias_cero': [7, 5.0]}, ...]"
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


def calcular_score_roles(roles_dict: Dict[str, tuple]) -> float:
    """
    Calcula score ponderado de roles con factor de posición.
    
    Score = suma(valor * multiplicador * factor_posicion)
    """
    score = 0.0
    
    for rol_clave, (posicion, valor) in roles_dict.items():
        # Multiplicador del rol
        multiplicador = ROLES_CRITICOS_PORTEROS.get(rol_clave, ROLES_TODOS.get(rol_clave, 0.5))
        
        # Factor de posición: penaliza si está bajo en ranking
        factor_posicion = max(1.0 - (posicion - 1) / 100.0, 0.1)
        
        score += valor * multiplicador * factor_posicion
    
    return score


# ===========================
# FUNCIONES PRINCIPALES
# ===========================

def enriquecer_dataframe_con_roles(df: pd.DataFrame, 
                                    columna_roles: str = "roles") -> pd.DataFrame:
    """
    Enriquece el dataframe con información de roles FBRef.
    
    Crea columnas:
    - num_roles: cantidad de roles
    - score_roles: score ponderado global
    - tiene_rol_destacado: indicador binario
    - es_portero_elite: top 25% en score
    - rol_{rol_key}_valor: valor específico de cada rol crítico
    - rol_{rol_key}_posicion: ranking específico
    
    CRÍTICO: Rellena NaNs de roles con 0 (no tiene ese rol)
    """
    print("=" * 80)
    print("ENRIQUECIMIENTO CON ROLES DESTACADOS (FBRef)")
    print("=" * 80)
    
    if columna_roles not in df.columns:
        print(f"⚠️ Columna '{columna_roles}' no encontrada.\n")
        return df
    
    print(f"\nParseando roles desde columna '{columna_roles}'...")
    
    # Parsear roles
    df_temp = df.copy()
    df_temp["roles_parsed"] = df_temp[columna_roles].apply(parsear_roles_json)
    
    # Contar roles
    df["num_roles"] = df_temp["roles_parsed"].apply(len)
    df["tiene_rol_destacado"] = (df["num_roles"] > 0).astype(int)
    
    con_roles = df["num_roles"].sum()
    print(f"✓ Jugadores con roles: {con_roles} / {len(df)}")
    
    # Score global
    print(f"\nCalculando score ponderado de roles...")
    df["score_roles"] = df_temp["roles_parsed"].apply(calcular_score_roles)
    
    if con_roles > 0:
        print(f"✓ Score de roles - Media: {df[df['num_roles'] > 0]['score_roles'].mean():.2f}, "
              f"Std: {df[df['num_roles'] > 0]['score_roles'].std():.2f}")
    
    # Elite: top 25%
    if con_roles > 0:
        threshold_elite = df[df["num_roles"] > 0]["score_roles"].quantile(0.75)
        df["es_portero_elite"] = (df["score_roles"] >= threshold_elite).astype(int)
        elite_count = df["es_portero_elite"].sum()
        print(f"✓ Porteros elite (top 25%): {elite_count}")
    else:
        df["es_portero_elite"] = 0
    
    # Extraer roles críticos
    print(f"\nExtrayendo roles críticos para porteros:")
    for rol_clave in ROLES_CRITICOS_PORTEROS.keys():
        df[f"rol_{rol_clave}_valor"] = df_temp["roles_parsed"].apply(
            lambda x: x.get(rol_clave, (np.nan, np.nan))[1]
        )
        df[f"rol_{rol_clave}_posicion"] = df_temp["roles_parsed"].apply(
            lambda x: x.get(rol_clave, (np.nan, np.nan))[0]
        )
        
        tiene_rol = df[f"rol_{rol_clave}_valor"].notna().sum()
        print(f"  ✓ rol_{rol_clave}: {tiene_rol} jugadores")
    
    # CRÍTICO: Rellenar NaNs de roles con 0
    rol_cols = [c for c in df.columns if c.startswith("rol_")]
    for col in rol_cols:
        df[col] = df[col].fillna(0)
    
    print("\n✅ Enriquecimiento con roles completado\n")
    return df


def crear_features_interaccion_roles_v2(df: pd.DataFrame, 
                                        columna_objetivo: Optional[str] = None) -> pd.DataFrame:
    """
    Crea variables de interacción entre roles y performance.
    
    Variables:
    - elite_paradas_interact
    - porterias_cero_eficiencia
    - score_roles_normalizado
    - num_roles_criticos
    - ratio_roles_criticos
    - tiene_rol_defensivo
    """
    print("=" * 80)
    print("INGENIERÍA DE VARIABLES DE INTERACCIÓN (ROLES + PERFORMANCE)")
    print("=" * 80)
    
    print("\nVariables de interacción roles-performance:\n")
    
    # 1. Elite × paradas
    if "es_portero_elite" in df.columns and "rol_paradas_valor" in df.columns:
        df["elite_paradas_interact"] = (
            df["es_portero_elite"].fillna(0).astype(float) * 
            df["rol_paradas_valor"].fillna(0).astype(float)
        )
        print("  ✓ elite_paradas_interact")
    
    # 2. Porterías × eficiencia (si existe eficiencia_defensiva)
    if "rol_porterias_cero_valor" in df.columns and "eficiencia_defensiva" in df.columns:
        df["porterias_cero_eficiencia"] = (
            df["rol_porterias_cero_valor"].fillna(0).astype(float) * 
            df["eficiencia_defensiva"].fillna(0).astype(float)
        )
        print("  ✓ porterias_cero_eficiencia")
    
    # 3. Score normalizado
    if "score_roles" in df.columns:
        df["score_roles_normalizado"] = df["score_roles"].fillna(0).astype(float)
        print("  ✓ score_roles_normalizado")
    
    # 4. Contar roles críticos específicos
    roles_criticos_cols = [c for c in df.columns 
                           if any(rc in c for rc in ROLES_CRITICOS_PORTEROS.keys()) 
                           and c.endswith("_valor")]
    if len(roles_criticos_cols) > 0:
        df["num_roles_criticos"] = (df[roles_criticos_cols] > 0).sum(axis=1)
        print(f"  ✓ num_roles_criticos (basado en {len(roles_criticos_cols)} roles)")
    
    # 5. Ratio roles críticos
    if "num_roles_criticos" in df.columns and "num_roles" in df.columns:
        df["ratio_roles_criticos"] = (
            df["num_roles_criticos"] / (df["num_roles"] + 1)
        ).fillna(0)
        print("  ✓ ratio_roles_criticos")
    
    # 6. Tiene rol defensivo
    roles_defensivos = {"paradas", "porterias_cero", "despejes"}
    rol_def_cols = [c for c in df.columns 
                    if any(rd in c for rd in roles_defensivos) 
                    and c.endswith("_valor")]
    if len(rol_def_cols) > 0:
        df["tiene_rol_defensivo"] = (df[rol_def_cols] > 0).any(axis=1).astype(int)
        count = df["tiene_rol_defensivo"].sum()
        print(f"  ✓ tiene_rol_defensivo ({count} jugadores)")
    
    print("\n✅ Variables de interacción creadas\n")
    return df


def resumen_roles(df: pd.DataFrame) -> None:
    """
    Imprime resumen detallado de roles en el dataset.
    """
    print("=" * 80)
    print("RESUMEN DE ROLES EN EL DATASET")
    print("=" * 80 + "\n")
    
    total = len(df)
    con_roles = (df["num_roles"] > 0).sum() if "num_roles" in df.columns else 0
    sin_roles = total - con_roles
    
    print(f"Total de registros: {total}")
    print(f"Registros con roles: {con_roles} ({con_roles/total*100:.1f}%)")
    print(f"Registros sin roles: {sin_roles} ({sin_roles/total*100:.1f}%)")
    
    if "num_roles" in df.columns:
        print("\nDistribución de número de roles por jugador:")
        print(df["num_roles"].value_counts().sort_index())
    
    if "score_roles" in df.columns and con_roles > 0:
        print(f"\nEstadísticas de score_roles (solo con roles):")
        scores = df[df["num_roles"] > 0]["score_roles"]
        print(f"  Media: {scores.mean():.2f}")
        print(f"  Std: {scores.std():.2f}")
        print(f"  Min: {scores.min():.2f}")
        print(f"  Max: {scores.max():.2f}")
    
    print(f"\nRoles críticos más frecuentes:")
    for rol_clave in ROLES_CRITICOS_PORTEROS.keys():
        col_valor = f"rol_{rol_clave}_valor"
        if col_valor in df.columns:
            count = (df[col_valor] > 0).sum()
            if count > 0:
                media = df[df[col_valor] > 0][col_valor].mean()
                print(f"  {rol_clave:15s}: {count:4d} jugadores, media={media:6.1f}")
    
    print()


if __name__ == "__main__":
    print("Módulo roles_enricher.py cargado correctamente.")
    print("\nFunciones disponibles:")
    print("  - enriquecer_dataframe_con_roles(df, columna_roles='roles')")
    print("  - crear_features_interaccion_roles_v2(df, columna_objetivo=None)")
    print("  - resumen_roles(df)")
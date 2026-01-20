"""
MÓDULO UNIFICADO: ENRIQUECIMIENTO DE ROLES FBRef POR POSICIÓN
===============================================================================
Integración robusta de datos con información de roles FBRef
- Porteros (GK)
- Defensas (DF)
- Genérico (ALL)

Autor: Pablo + AI Assistant
Fecha: Enero 2026
===============================================================================
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import json


# ============================================================================
# CONFIGURACIÓN DE ROLES POR POSICIÓN
# ============================================================================

# Roles críticos para PORTEROS (GK)
ROLES_CRITICOS_GK = {
    "paradas": 1.5,              # Saves - MUY IMPORTANTE
    "save_pct": 1.4,             # Save percentage
    "porterias_cero": 1.5,       # Clean sheets
    "distribucion": 1.2,         # Distribution
    "manejo": 1.3,               # Handling - CRÍTICO
    "salidas": 1.1,              # Rushing/Distribution
    "comando": 1.2,              # Command of Box
    "posicionamiento": 1.0,      # Positioning
    "minutos": 1.2,              # Minutes
    "apariciones_suplente": 0.3, # Substitute Appearances
    "amarillas": -0.6,           # Yellow Cards
    "rojas": -1.2,               # Red Cards
    "despejes": 1.1,             # Clearances
}

# Roles críticos para DEFENSAS (DF)
ROLES_CRITICOS_DF = {
    "entradas": 1.3,              # Tackles - muy importante
    "intercepciones": 1.4,        # Interceptions - crítico
    "despejes": 1.2,              # Clearances - importante
    "regates_exitosos": 0.8,      # Successful Take-Ons
    "minutos": 1.1,               # Minutes - disponibilidad
    "apariciones_suplente": 0.3,  # Substitute Appearances
    "amarillas": -0.6,            # Yellow Cards
    "rojas": -1.2,                # Red Cards
    "faltas_cometidas": -0.4,     # Fouls Committed
    "faltas_recibidas": 0.4,      # Fouls Drawn
}

# Todos los roles reconocibles (genérico)
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


# ============================================================================
# FUNCIONES DE PARSING
# ============================================================================

def parsear_roles_json(rol_json_str: str) -> Dict[str, tuple]:
    """
    Parsea la columna de roles JSON y extrae {rol_clave: (posicion, valor)}.
    
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


def calcular_score_roles(roles_dict: Dict[str, tuple], 
                        roles_config: Dict[str, float] = None) -> float:
    """
    Calcula score ponderado de roles con factor de posición.
    
    Score = suma(valor * multiplicador * factor_posicion)
    
    Args:
        roles_dict: Diccionario de roles parseados
        roles_config: Configuración de multiplicadores (GK, DF, o TODOS)
    
    Returns:
        float: Score ponderado
    """
    if roles_config is None:
        roles_config = ROLES_TODOS
    
    score = 0.0
    
    for rol_clave, (posicion, valor) in roles_dict.items():
        multiplicador = roles_config.get(rol_clave, ROLES_TODOS.get(rol_clave, 0.5))
        factor_posicion = max(1.0 - (posicion - 1) / 100.0, 0.1)
        score += valor * multiplicador * factor_posicion
    
    return score


# ============================================================================
# FUNCIONES PRINCIPALES
# ============================================================================

def enriquecer_dataframe_con_roles(df: pd.DataFrame,
                                   position: str = 'ALL',
                                   columna_roles: str = "roles",
                                   verbose: bool = True) -> pd.DataFrame:
    """
    Enriquece el dataframe con información de roles FBRef.
    Específico por posición (GK, DF, o ALL).
    
    Crea columnas:
    - num_roles: cantidad de roles
    - score_roles: score ponderado global
    - tiene_rol_destacado: indicador binario
    - es_{posicion}_elite: top 25% en score (ej: es_portero_elite, es_defensa_elite)
    - rol_{rol_key}_valor: valor específico de cada rol crítico
    - rol_{rol_key}_posicion: ranking específico
    
    CRÍTICO: Rellena NaNs de roles con 0 (no tiene ese rol)
    
    Args:
        df: DataFrame a enriquecer
        position: 'GK', 'DF' o 'ALL'
        columna_roles: nombre de columna con roles JSON
        verbose: print detallado
        
    Returns:
        DataFrame enriquecido
    """
    
    if verbose:
        print("=" * 80)
        print(f"ENRIQUECIMIENTO CON ROLES FBRef ({position})")
        print("=" * 80)
    
    if columna_roles not in df.columns:
        if verbose:
            print(f"⚠️  Columna '{columna_roles}' no encontrada.\n")
        return df
    
    if verbose:
        print(f"\nParseando roles desde columna '{columna_roles}'...")
    
    # Seleccionar configuración de roles por posición
    if position == 'GK':
        roles_config = ROLES_CRITICOS_GK
        elite_col_name = "es_portero_elite"
        tipo_posicion = "Porteros"
    elif position == 'DF':
        roles_config = ROLES_CRITICOS_DF
        elite_col_name = "es_defensa_elite"
        tipo_posicion = "Defensas"
    else:
        roles_config = ROLES_TODOS
        elite_col_name = "es_jugador_elite"
        tipo_posicion = "Jugadores"
    
    # Parsear roles
    df_temp = df.copy()
    df_temp["roles_parsed"] = df_temp[columna_roles].apply(parsear_roles_json)
    
    # Contar roles
    df["num_roles"] = df_temp["roles_parsed"].apply(len)
    df["tiene_rol_destacado"] = (df["num_roles"] > 0).astype(int)
    
    con_roles = df["num_roles"].sum()
    if verbose:
        print(f"✓ {tipo_posicion} con roles: {con_roles} / {len(df)}")
    
    # Score global
    if verbose:
        print(f"\nCalculando score ponderado de roles...")
    
    df["score_roles"] = df_temp["roles_parsed"].apply(
        lambda x: calcular_score_roles(x, roles_config)
    )
    
    if con_roles > 0 and verbose:
        scores_con_roles = df[df['num_roles'] > 0]['score_roles']
        print(f"✓ Score de roles - Media: {scores_con_roles.mean():.2f}, Std: {scores_con_roles.std():.2f}")
    
    # Elite: top 25%
    if con_roles > 0:
        threshold_elite = df[df["num_roles"] > 0]["score_roles"].quantile(0.75)
        df[elite_col_name] = (df["score_roles"] >= threshold_elite).astype(int)
        elite_count = df[elite_col_name].sum()
        if verbose:
            print(f"✓ {tipo_posicion} elite (top 25%): {elite_count}")
    else:
        df[elite_col_name] = 0
    
    # Extraer roles críticos
    if verbose:
        print(f"\nExtrayendo roles críticos ({position}):")
    
    for rol_clave in roles_config.keys():
        df[f"rol_{rol_clave}_valor"] = df_temp["roles_parsed"].apply(
            lambda x: x.get(rol_clave, (np.nan, np.nan))[1]
        )
        df[f"rol_{rol_clave}_posicion"] = df_temp["roles_parsed"].apply(
            lambda x: x.get(rol_clave, (np.nan, np.nan))[0]
        )
        
        tiene_rol = df[f"rol_{rol_clave}_valor"].notna().sum()
        if verbose and tiene_rol > 0:
            print(f" ✓ rol_{rol_clave}: {tiene_rol} jugadores")
    
    # CRÍTICO: Rellenar NaNs de roles con 0
    rol_cols = [c for c in df.columns if c.startswith("rol_")]
    for col in rol_cols:
        df[col] = df[col].fillna(0)
    
    if verbose:
        print("\n✅ Enriquecimiento con roles completado\n")
    
    return df


def crear_features_interaccion_roles(df: pd.DataFrame,
                                    position: str = 'ALL',
                                    columna_objetivo: Optional[str] = None,
                                    verbose: bool = True) -> pd.DataFrame:
    """
    Crea variables de interacción entre roles y performance.
    Específico por posición (GK, DF, o ALL).
    
    Para GK:
    - elite_paradas_interact
    - elite_manejo_interact
    - elite_distribucion_interact
    - porterias_cero_eficiencia (si existe eficiencia_defensiva)
    - score_roles_normalizado
    - tiene_rol_gk_core
    - num_roles_criticos
    - ratio_roles_criticos
    
    Para DF:
    - elite_entradas_interact
    - elite_intercepciones_interact
    - elite_despejes_interact
    - score_roles_normalizado
    - tiene_rol_defensivo_core
    - score_defensivo
    - num_roles_criticos
    - ratio_roles_criticos
    
    Args:
        df: DataFrame con roles ya enriquecidos
        position: 'GK', 'DF' o 'ALL'
        columna_objetivo: columna objetivo (opcional, para contexto)
        verbose: print detallado
        
    Returns:
        DataFrame con features de interacción
    """
    
    if verbose:
        print("=" * 80)
        print(f"INGENIERÍA DE VARIABLES DE INTERACCIÓN ({position})")
        print("=" * 80)
        print()
    
    if position == 'GK':
        # ===== GK INTERACTIONS =====
        
        # Elite paradas
        if "es_portero_elite" in df.columns and "rol_paradas_valor" in df.columns:
            df["elite_paradas_interact"] = (
                df["es_portero_elite"].fillna(0).astype(float) * 
                df["rol_paradas_valor"].fillna(0).astype(float)
            )
            if verbose:
                print("✅ elite_paradas_interact")
        
        # Elite manejo
        if "es_portero_elite" in df.columns and "rol_manejo_valor" in df.columns:
            df["elite_manejo_interact"] = (
                df["es_portero_elite"].fillna(0).astype(float) * 
                df["rol_manejo_valor"].fillna(0).astype(float)
            )
            if verbose:
                print("✅ elite_manejo_interact")
        
        # Elite distribución
        if "es_portero_elite" in df.columns and "rol_distribucion_valor" in df.columns:
            df["elite_distribucion_interact"] = (
                df["es_portero_elite"].fillna(0).astype(float) * 
                df["rol_distribucion_valor"].fillna(0).astype(float)
            )
            if verbose:
                print("✅ elite_distribucion_interact")
        
        # Porterías × eficiencia defensiva
        if "rol_porterias_cero_valor" in df.columns and "eficiencia_defensiva" in df.columns:
            df["porterias_cero_eficiencia"] = (
                df["rol_porterias_cero_valor"].fillna(0).astype(float) * 
                df["eficiencia_defensiva"].fillna(0).astype(float)
            )
            if verbose:
                print("✅ porterias_cero_eficiencia")
        
        # Score normalizado
        if "score_roles" in df.columns:
            df["score_roles_normalizado"] = df["score_roles"].fillna(0).astype(float)
            if verbose:
                print("✅ score_roles_normalizado")
        
        # Tiene rol GK core (paradas + manejo + distribución)
        gk_core_cols = [c for c in df.columns 
                       if any(rc in c for rc in ["paradas", "manejo", "distribucion"]) 
                       and c.endswith("_valor")]
        if gk_core_cols:
            df["tiene_rol_gk_core"] = (df[gk_core_cols] > 0).any(axis=1).astype(int)
            if verbose:
                print(f"✅ tiene_rol_gk_core ({df['tiene_rol_gk_core'].sum()} porteros)")
    
    elif position == 'DF':
        # ===== DF INTERACTIONS =====
        
        # Elite entradas
        if "es_defensa_elite" in df.columns and "rol_entradas_valor" in df.columns:
            df["elite_entradas_interact"] = (
                df["es_defensa_elite"].fillna(0).astype(float) * 
                df["rol_entradas_valor"].fillna(0).astype(float)
            )
            if verbose:
                print("✅ elite_entradas_interact")
        
        # Elite intercepciones
        if "es_defensa_elite" in df.columns and "rol_intercepciones_valor" in df.columns:
            df["elite_intercepciones_interact"] = (
                df["es_defensa_elite"].fillna(0).astype(float) * 
                df["rol_intercepciones_valor"].fillna(0).astype(float)
            )
            if verbose:
                print("✅ elite_intercepciones_interact")
        
        # Elite despejes
        if "es_defensa_elite" in df.columns and "rol_despejes_valor" in df.columns:
            df["elite_despejes_interact"] = (
                df["es_defensa_elite"].fillna(0).astype(float) * 
                df["rol_despejes_valor"].fillna(0).astype(float)
            )
            if verbose:
                print("✅ elite_despejes_interact")
        
        # Score normalizado
        if "score_roles" in df.columns:
            df["score_roles_normalizado"] = df["score_roles"].fillna(0).astype(float)
            if verbose:
                print("✅ score_roles_normalizado")
        
        # Tiene rol defensivo core (entradas + intercepciones + despejes)
        def_core_cols = [c for c in df.columns 
                        if any(rc in c for rc in ["entradas", "intercepciones", "despejes"]) 
                        and c.endswith("_valor")]
        if def_core_cols:
            df["tiene_rol_defensivo_core"] = (df[def_core_cols] > 0).any(axis=1).astype(int)
            if verbose:
                print(f"✅ tiene_rol_defensivo_core ({df['tiene_rol_defensivo_core'].sum()} defensas)")
        
        # Score defensivo (solo roles defensivos core)
        def calcular_score_defensivo(row):
            score = 0.0
            for rol_key in ["entradas", "intercepciones", "despejes"]:
                col_valor = f"rol_{rol_key}_valor"
                if col_valor in row.index and row[col_valor] > 0:
                    multiplicador = ROLES_CRITICOS_DF.get(rol_key, 0.5)
                    score += row[col_valor] * multiplicador
            return score
        
        df["score_defensivo"] = df.apply(calcular_score_defensivo, axis=1)
        if verbose:
            print("✅ score_defensivo (sum: entradas + intercepciones + despejes ponderadas)")
    
    # ===== COMMON FOR ALL =====
    
    # Contar roles críticos específicos
    roles_criticos_cols = [c for c in df.columns if c.endswith("_valor")]
    if roles_criticos_cols:
        df["num_roles_criticos"] = (df[roles_criticos_cols] > 0).sum(axis=1)
        if verbose:
            print(f"✅ num_roles_criticos (basado en {len(roles_criticos_cols)} roles)")
    
    # Ratio roles críticos
    if "num_roles_criticos" in df.columns and "num_roles" in df.columns:
        df["ratio_roles_criticos"] = (
            df["num_roles_criticos"] / (df["num_roles"] + 1)
        ).fillna(0)
        if verbose:
            print("✅ ratio_roles_criticos")
    
    # Tiene rol destacado genérico
    if "tiene_rol_destacado" in df.columns:
        if "num_roles" in df.columns:
            df["tiene_rol_destacado"] = (df["num_roles"] > 0).astype(int)
            if verbose:
                print(f"✅ tiene_rol_destacado ({df['tiene_rol_destacado'].sum()} jugadores)")
    
    if verbose:
        print("\n✅ Variables de interacción creadas\n")
    
    return df


def resumen_roles(df: pd.DataFrame, position: str = 'ALL') -> None:
    """
    Imprime resumen detallado de roles en el dataset.
    
    Args:
        df: DataFrame enriquecido con roles
        position: 'GK', 'DF' o 'ALL'
    """
    
    # Determinar tipo de posición
    if position == 'GK':
        roles_mostrar = ROLES_CRITICOS_GK.keys()
        tipo_posicion = "PORTEROS"
    elif position == 'DF':
        roles_mostrar = ROLES_CRITICOS_DF.keys()
        tipo_posicion = "DEFENSAS"
    else:
        roles_mostrar = ROLES_TODOS.keys()
        tipo_posicion = "TODOS"
    
    print("="*80)
    print(f"RESUMEN DE ROLES ({tipo_posicion})")
    print("="*80 + "\n")
    
    total = len(df)
    con_roles = (df["num_roles"] > 0).sum() if "num_roles" in df.columns else 0
    sin_roles = total - con_roles
    
    print(f"Total de registros: {total}")
    print(f"Con roles: {con_roles} ({con_roles/total*100:.1f}%)")
    print(f"Sin roles: {sin_roles} ({sin_roles/total*100:.1f}%)")
    
    if "num_roles" in df.columns:
        print("\nDistribución de número de roles:")
        print(df["num_roles"].value_counts().sort_index())
    
    if "score_roles" in df.columns and con_roles > 0:
        print(f"\nEstadísticas de score_roles (solo con roles):")
        scores = df[df["num_roles"] > 0]["score_roles"]
        print(f"  Media: {scores.mean():.2f}")
        print(f"  Std: {scores.std():.2f}")
        print(f"  Min: {scores.min():.2f}")
        print(f"  Max: {scores.max():.2f}")
    
    print(f"\nRoles críticos más frecuentes:")
    for rol_clave in roles_mostrar:
        col_valor = f"rol_{rol_clave}_valor"
        if col_valor in df.columns:
            count = (df[col_valor] > 0).sum()
            if count > 0:
                media = df[df[col_valor] > 0][col_valor].mean()
                print(f"  {rol_clave:20s}: {count:4d} jugadores, media={media:6.1f}")
    
    print()


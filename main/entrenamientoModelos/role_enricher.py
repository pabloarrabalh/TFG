
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import json

ROLES_CRITICOS_GK = {
    "paradas": 1.5,              
    "porterias_cero": 1.5,       
    "amarillas": -0.6,         
    "rojas": -1.2,              
}

ROLES_CRITICOS_DF = {
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
}

ROLES_CRITICOS_MC = {
    "pases_clave": 1.6,          
    "asistencias": 1.5,           
    "pases_completados_pct": 1.2,
    "regates_exitosos": 1.1,      
    "minutos": 1.0,               
    "entradas": 0.8,              
    "intercepciones": 0.8,       
    "apariciones_suplente": 0.3,  
    "amarillas": -0.6,            
    "rojas": -1.2,                
    "faltas_cometidas": -0.4,    
    "faltas_recibidas": 0.4,      
}

ROLES_CRITICOS_DT = {
    "goles": 2.0,                 
    "goles_90": 1.9,              
    "penaltis_marcados": 1.5,    
    "asistencias": 1.3,          
    "tiros_puerta": 1.2,         
    "goles_por_tiro": 1.4,       
    "pases_clave": 0.9,         
    "regates_exitosos": 0.8,     
    "minutos": 1.1,              
    "apariciones_suplente": 0.2, 
    "amarillas": -0.5,           
    "rojas": -1.0,               
    "faltas_cometidas": -0.3,     
}

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


def parsear_roles_json(rol_json_str: str) -> Dict[str, tuple]:
    if pd.isna(rol_json_str):
        return {}
    
    if not isinstance(rol_json_str, (str, list)):
        return {}
    
    if isinstance(rol_json_str, list):
        if len(rol_json_str) == 0:
            return {}
        rol_list = rol_json_str
    else:
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


def calcular_factor_posicion(posicion: int, agresivo: bool = True) -> float:
    if posicion <= 0:
        return 0.1
    
    if agresivo:
        factor = 1.0 / (posicion ** 0.5)
    else:
        factor = max(1.0 - (posicion - 1) / 100.0, 0.1)
    
    return max(min(factor, 1.0), 0.1)  # Clamp [0.1, 1.0]


def calcular_score_roles(roles_dict: Dict[str, tuple], 
                        roles_config: Dict[str, float] = None,
                        agresivo: bool = True) -> float:
    if roles_config is None:
        roles_config = ROLES_TODOS
    
    score = 0.0
    
    for rol_clave, (posicion, valor) in roles_dict.items():
        multiplicador = roles_config.get(rol_clave, ROLES_TODOS.get(rol_clave, 0.5))
        factor_posicion = calcular_factor_posicion(posicion, agresivo=agresivo)
        score += valor * multiplicador * factor_posicion
    
    return score


def enriquecer_dataframe_con_roles(df: pd.DataFrame,
                                   position: str = 'ALL',
                                   columna_roles: str = "roles",
                                   verbose: bool = True) -> pd.DataFrame:
    
    if verbose:
        print("=" * 80)
        print(f"ENRIQUECIMIENTO CON ROLES FBRef ({position})")
        print("=" * 80)
    
    if columna_roles not in df.columns:
        if verbose:
            print(f"  Columna '{columna_roles}' no encontrada.\n")
        return df
    
    if verbose:
        print(f"\nParseando roles desde columna '{columna_roles}'...")
    
    if position == 'GK':
        roles_config = ROLES_CRITICOS_GK
        elite_col_name = "es_portero_elite"
        tipo_posicion = "Porteros"
    elif position == 'DF':
        roles_config = ROLES_CRITICOS_DF
        elite_col_name = "es_defensa_elite"
        tipo_posicion = "Defensas"
    elif position == 'MC':
        roles_config = ROLES_CRITICOS_MC
        elite_col_name = "es_mediocampista_elite"
        tipo_posicion = "Mediocampistas"
    elif position == 'DT':
        roles_config = ROLES_CRITICOS_DT
        elite_col_name = "es_delantero_elite"
        tipo_posicion = "Delanteros"
    else:
        roles_config = ROLES_TODOS
        elite_col_name = "es_jugador_elite"
        tipo_posicion = "Jugadores"
    
    df_temp = df.copy()
    df_temp["roles_parsed"] = df_temp[columna_roles].apply(parsear_roles_json)
    
    df["num_roles"] = df_temp["roles_parsed"].apply(len)
    df["tiene_rol_destacado"] = (df["num_roles"] > 0).astype(int)
    
    con_roles = df["num_roles"].sum()
    if verbose:
        print(f" {tipo_posicion} con roles: {con_roles} / {len(df)}")
    
    if verbose:
        print(f"\nCalculando score ponderado de roles...")
    
    df["score_roles"] = df_temp["roles_parsed"].apply(
        lambda x: calcular_score_roles(x, roles_config)
    )
    
    if con_roles > 0 and verbose:
        scores_con_roles = df[df['num_roles'] > 0]['score_roles']
        print(f" Score de roles - Media: {scores_con_roles.mean():.2f}, Std: {scores_con_roles.std():.2f}")
    
    if con_roles > 0:
        threshold_elite = df[df["num_roles"] > 0]["score_roles"].quantile(0.75)
        df[elite_col_name] = (df["score_roles"] >= threshold_elite).astype(int)
        elite_count = df[elite_col_name].sum()
        if verbose:
            print(f" {tipo_posicion} elite (top 25%): {elite_count}")
    else:
        df[elite_col_name] = 0
    
    if verbose:
        print(f"\nExtrayendo roles críticos ({position}) con ponderación por posición:")
    
    nuevas_cols = {}
    
    for rol_clave in roles_config.keys():
        nuevas_cols[f"rol_{rol_clave}_valor"] = df_temp["roles_parsed"].apply(
            lambda x: x.get(rol_clave, (np.nan, np.nan))[1]
        )
        nuevas_cols[f"rol_{rol_clave}_posicion"] = df_temp["roles_parsed"].apply(
            lambda x: x.get(rol_clave, (np.nan, np.nan))[0]
        )
        def calcular_valor_ponderado(row):
            posicion = row[f"rol_{rol_clave}_posicion"]
            valor = row[f"rol_{rol_clave}_valor"]
            if pd.isna(posicion) or pd.isna(valor):
                return np.nan
            factor = calcular_factor_posicion(int(posicion), agresivo=True)
            return valor * factor
        
        nuevas_cols[f"rol_{rol_clave}_ponderado"] = pd.DataFrame({
            f"rol_{rol_clave}_posicion": nuevas_cols[f"rol_{rol_clave}_posicion"],
            f"rol_{rol_clave}_valor": nuevas_cols[f"rol_{rol_clave}_valor"]
        }).apply(calcular_valor_ponderado, axis=1)
        
        tiene_rol = nuevas_cols[f"rol_{rol_clave}_valor"].notna().sum()
        if verbose and tiene_rol > 0:
            media_ponderado = nuevas_cols[f"rol_{rol_clave}_ponderado"].dropna().mean()
            print(f"  rol_{rol_clave}: {tiene_rol} jugadores, media ponderada={media_ponderado:.2f}")
    
    # Agregar todas las columnas nuevas de una vez
    df_nuevas_cols = pd.DataFrame(nuevas_cols, index=df.index)
    df = pd.concat([df, df_nuevas_cols], axis=1)
    
    rol_cols = [c for c in df.columns if c.startswith("rol_") and not c.endswith("_ponderado")]
    rol_cols_ponderados = [c for c in df.columns if c.endswith("_ponderado")]
    
    df[rol_cols + rol_cols_ponderados] = df[rol_cols + rol_cols_ponderados].fillna(0)
    
    if verbose:
        print("\n Enriquecimiento con roles completado\n")
    
    return df


def crear_features_interaccion_roles(df: pd.DataFrame,
                                    position: str = 'ALL',
                                    columna_objetivo: Optional[str] = None,
                                    verbose: bool = True) -> pd.DataFrame:
   
    if verbose:
        print("=" * 80)
        print(f"INGENIERÍA DE VARIABLES DE INTERACCIÓN ({position})")
        print("=" * 80)
        print()
    
    if position in ['PT']:
        
        if "es_portero_elite" in df.columns and "rol_paradas_ponderado" in df.columns:
            df["elite_paradas_interact"] = (
                df["es_portero_elite"].fillna(0).astype(float) * 
                df["rol_paradas_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_paradas_interact (ponderado)")
        
        if "rol_porterias_cero_valor" in df.columns and "eficiencia_defensiva" in df.columns:
            df["porterias_cero_eficiencia"] = (
                df["rol_porterias_cero_valor"].fillna(0).astype(float) * 
                df["eficiencia_defensiva"].fillna(0).astype(float)
            )
            if verbose:
                print(" porterias_cero_eficiencia")
        
        if "score_roles" in df.columns:
            df["score_roles_normalizado"] = df["score_roles"].fillna(0).astype(float)
            if verbose:
                print(" score_roles_normalizado")
        
        gk_core_cols = [c for c in df.columns 
                       if any(rc in c for rc in ["paradas", "porterias_cero"]) 
                       and c.endswith("_valor")]
        if gk_core_cols:
            df["tiene_rol_gk_core"] = (df[gk_core_cols] > 0).any(axis=1).astype(int)
            if verbose:
                print(f" tiene_rol_gk_core ({df['tiene_rol_gk_core'].sum()} porteros)")
    
    elif position == 'DF':

        if "es_defensa_elite" in df.columns and "rol_entradas_ponderado" in df.columns:
            df["elite_entradas_interact"] = (
                df["es_defensa_elite"].fillna(0).astype(float) * 
                df["rol_entradas_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_entradas_interact (ponderado)")
        
        if "es_defensa_elite" in df.columns and "rol_intercepciones_ponderado" in df.columns:
            df["elite_intercepciones_interact"] = (
                df["es_defensa_elite"].fillna(0).astype(float) * 
                df["rol_intercepciones_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_intercepciones_interact (ponderado)")
        
        if "es_defensa_elite" in df.columns and "rol_despejes_ponderado" in df.columns:
            df["elite_despejes_interact"] = (
                df["es_defensa_elite"].fillna(0).astype(float) * 
                df["rol_despejes_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_despejes_interact (ponderado)")
        
        if "score_roles" in df.columns:
            df["score_roles_normalizado"] = df["score_roles"].fillna(0).astype(float)
            if verbose:
                print(" score_roles_normalizado")
        
        def_core_cols = [c for c in df.columns 
                        if any(rc in c for rc in ["entradas", "intercepciones", "despejes"]) 
                        and c.endswith("_valor")]
        if def_core_cols:
            df["tiene_rol_defensivo_core"] = (df[def_core_cols] > 0).any(axis=1).astype(int)
            if verbose:
                print(f" tiene_rol_defensivo_core ({df['tiene_rol_defensivo_core'].sum()} defensas)")
        
        def calcular_score_defensivo(row):
            score = 0.0
            for rol_key in ["entradas", "intercepciones", "despejes"]:
                col_ponderado = f"rol_{rol_key}_ponderado"
                if col_ponderado in row.index and row[col_ponderado] > 0:
                    multiplicador = ROLES_CRITICOS_DF.get(rol_key, 0.5)
                    score += row[col_ponderado] * multiplicador
            return score
        
        df["score_defensivo"] = df.apply(calcular_score_defensivo, axis=1)
        if verbose:
            print(" score_defensivo (sum: entradas + intercepciones + despejes PONDERADOS por posición)")
    
    elif position == 'MC':
        if "es_mediocampista_elite" in df.columns and "rol_pases_clave_ponderado" in df.columns:
            df["elite_pases_clave_interact"] = (
                df["es_mediocampista_elite"].fillna(0).astype(float) * 
                df["rol_pases_clave_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_pases_clave_interact (ponderado)")
        
        if "es_mediocampista_elite" in df.columns and "rol_asistencias_ponderado" in df.columns:
            df["elite_asistencias_interact"] = (
                df["es_mediocampista_elite"].fillna(0).astype(float) * 
                df["rol_asistencias_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_asistencias_interact (ponderado)")
        
        if "score_roles" in df.columns:
            df["score_roles_normalizado"] = df["score_roles"].fillna(0).astype(float)
            if verbose:
                print(" score_roles_normalizado")
        
        mc_core_cols = [c for c in df.columns 
                       if any(rc in c for rc in ["pases_clave", "asistencias"]) 
                       and c.endswith("_valor")]
        if mc_core_cols:
            df["tiene_rol_mediocampista_core"] = (df[mc_core_cols] > 0).any(axis=1).astype(int)
            if verbose:
                print(f" tiene_rol_mediocampista_core ({df['tiene_rol_mediocampista_core'].sum()} mediocampistas)")
        
        def calcular_score_creativo(row):
            score = 0.0
            for rol_key in ["pases_clave", "asistencias", "regates_exitosos"]:
                col_ponderado = f"rol_{rol_key}_ponderado"
                if col_ponderado in row.index and row[col_ponderado] > 0:
                    multiplicador = ROLES_CRITICOS_MC.get(rol_key, 0.5)
                    score += row[col_ponderado] * multiplicador
            return score
        
        df["score_creativo"] = df.apply(calcular_score_creativo, axis=1)
        if verbose:
            print(" score_creativo (sum: pases_clave + asistencias + regates PONDERADOS por posición)")
    
    elif position == 'DT':
        
        if "es_delantero_elite" in df.columns and "rol_goles_ponderado" in df.columns:
            df["elite_goles_interact"] = (
                df["es_delantero_elite"].fillna(0).astype(float) * 
                df["rol_goles_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_goles_interact (ponderado)")
        
        if "es_delantero_elite" in df.columns and "rol_penaltis_marcados_ponderado" in df.columns:
            df["elite_penaltis_interact"] = (
                df["es_delantero_elite"].fillna(0).astype(float) * 
                df["rol_penaltis_marcados_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_penaltis_interact (ponderado)")
        
        if "es_delantero_elite" in df.columns and "rol_tiros_puerta_ponderado" in df.columns:
            df["elite_tiros_puerta_interact"] = (
                df["es_delantero_elite"].fillna(0).astype(float) * 
                df["rol_tiros_puerta_ponderado"].fillna(0).astype(float)
            )
            if verbose:
                print(" elite_tiros_puerta_interact (ponderado)")
        
        if "score_roles" in df.columns:
            df["score_roles_normalizado"] = df["score_roles"].fillna(0).astype(float)
            if verbose:
                print(" score_roles_normalizado")
        
        dt_core_cols = [c for c in df.columns 
                       if any(rc in c for rc in ["goles", "tiros_puerta"]) 
                       and c.endswith("_valor")]
        if dt_core_cols:
            df["tiene_rol_delantero_core"] = (df[dt_core_cols] > 0).any(axis=1).astype(int)
            if verbose:
                print(f" tiene_rol_delantero_core ({df['tiene_rol_delantero_core'].sum()} delanteros)")
        
        def calcular_score_goleador(row):
            score = 0.0
            for rol_key in ["goles", "penaltis_marcados", "goles_por_tiro"]:
                col_ponderado = f"rol_{rol_key}_ponderado"
                if col_ponderado in row.index and row[col_ponderado] > 0:
                    multiplicador = ROLES_CRITICOS_DT.get(rol_key, 0.5)
                    score += row[col_ponderado] * multiplicador
            return score
        
        df["score_goleador"] = df.apply(calcular_score_goleador, axis=1)
        if verbose:
            print(" score_goleador (sum: goles + penaltis + goles_por_tiro PONDERADOS por posición)")
    
    roles_criticos_cols = [c for c in df.columns if c.endswith("_valor")]
    if roles_criticos_cols:
        if position in ['GK', 'PT']:
            roles_positivos = ["paradas", "porterias_cero"]
            roles_negativos = ["amarillas", "rojas"]
        elif position == 'DF':
            roles_positivos = ["entradas", "intercepciones", "despejes", "regates_exitosos", "minutos"]
            roles_negativos = ["amarillas", "rojas", "faltas_cometidas"]
        elif position == 'MC':
            roles_positivos = ["pases_clave", "asistencias", "pases_completados_pct", "regates_exitosos", "minutos"]
            roles_negativos = ["amarillas", "rojas", "faltas_cometidas"]
        elif position == 'DT':
            roles_positivos = ["goles", "goles_90", "tiros_puerta", "penaltis_marcados", "goles_por_tiro", "asistencias", "minutos"]
            roles_negativos = ["amarillas", "rojas", "faltas_cometidas"]
        else:
            roles_positivos = None
            roles_negativos = ["amarillas", "rojas"]
        
        nuevas_cols_num = {}
        
        if roles_positivos:
            cols_positivos = [c for c in roles_criticos_cols 
                            if any(rp in c for rp in roles_positivos)]
            if cols_positivos:
                nuevas_cols_num["num_roles_positivos"] = (df[cols_positivos] > 0).sum(axis=1)
                if verbose:
                    print(f" num_roles_positivos ({len(cols_positivos)} roles: {roles_positivos})")
        
        if roles_negativos:
            cols_negativos = [c for c in roles_criticos_cols 
                            if any(rn in c for rn in roles_negativos)]
            if cols_negativos:
                nuevas_cols_num["num_roles_negativos"] = (df[cols_negativos] > 0).sum(axis=1)
                if verbose:
                    print(f" num_roles_negativos ({len(cols_negativos)} roles: {roles_negativos})")
        
        nuevas_cols_num["num_roles_criticos"] = (df[roles_criticos_cols] > 0).sum(axis=1)
        if verbose:
            print(f" num_roles_criticos (total de {len(roles_criticos_cols)} roles)")
        
        if "num_roles_positivos" in nuevas_cols_num and "num_roles_criticos" in nuevas_cols_num:
            nuevas_cols_num["ratio_roles_positivos"] = (
                nuevas_cols_num["num_roles_positivos"] / (nuevas_cols_num["num_roles_criticos"] + 1)
            ).fillna(0)
            if verbose:
                print(" ratio_roles_positivos (proporción de roles positivos)")
        
        if "num_roles_criticos" in nuevas_cols_num and "num_roles" in df.columns:
            nuevas_cols_num["ratio_roles_criticos"] = (
                nuevas_cols_num["num_roles_criticos"] / (df["num_roles"] + 1)
            ).fillna(0)
            if verbose:
                print(" ratio_roles_criticos (legacy)")
        
        df_nuevas = pd.DataFrame(nuevas_cols_num, index=df.index)
        df = pd.concat([df, df_nuevas], axis=1)
    
    if "tiene_rol_destacado" in df.columns:
        if "num_roles" in df.columns:
            df["tiene_rol_destacado"] = (df["num_roles"] > 0).astype(int)
            if verbose:
                print(f" tiene_rol_destacado ({df['tiene_rol_destacado'].sum()} jugadores)")
    
    if verbose:
        print("\n Variables de interacción creadas\n")
    
    return df


def resumen_roles(df: pd.DataFrame, position: str = 'ALL') -> None:
    if position == 'GK':
        roles_mostrar = ROLES_CRITICOS_GK.keys()
        tipo_posicion = "PORTEROS"
    elif position == 'DF':
        roles_mostrar = ROLES_CRITICOS_DF.keys()
        tipo_posicion = "DEFENSAS"
    elif position == 'MC':
        roles_mostrar = ROLES_CRITICOS_MC.keys()
        tipo_posicion = "MEDIOCAMPISTAS"
    elif position == 'DT':
        roles_mostrar = ROLES_CRITICOS_DT.keys()
        tipo_posicion = "DELANTEROS"
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


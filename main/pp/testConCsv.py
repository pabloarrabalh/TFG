"""
================================================================================
PREDICCIÓN DE PORTEROS - FANTASY FOOTBALL (VERSION NO-LEAKAGE)
================================================================================
"""

import warnings
import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

# ===========================
# 1. CONFIGURACIÓN Y RUTAS
# ===========================

ARCHIVO_CSV = "csv/csvGenerados/players_with_features_MINIMO.csv"
DIRECTORIO_MODELOS = Path("csv/csvGenerados/entrenamiento/portero/modelos")
DIRECTORIO_SALIDA = Path("csv/csvGenerados/predicciones")
DIRECTORIO_SALIDA.mkdir(parents=True, exist_ok=True)
COLUMNA_OBJETIVO = "puntosFantasy"
# Diccionario de Nombres (Asegúrate que coincidan con tu CSV)
PORTEROS = {
    "Alavés": "Antonio Sivera",
    "Sevilla": "Odysseas Vlachodimos",
    "Athletic Club": "Unai Simón",
    "Barcelona": "Joan García",
    "Real Madrid": "Thibaut Courtois",
    "Valencia": "Stole Dimitrievski",
    "Villarreal": "Luiz Lúcio Reis Júnior",
    "Atletico Madrid": "Jan Oblak",
    "Getafe": "David Soria",
    "Real Sociedad": "Álex Remiro",
    "Osasuna": "Sergio Herrera",
    "Celta": "Ionuț Radu",
    "Betis": "Álvaro Vallés",
    "Girona": "Paulo Gazzaniga",
    "Mallorca": "Leo Román",
    "Rayo Vallecano": "Augusto Batalla",
    "Elche": "Matías Dituro",
    "Espanyol": "Marko Dmitrović",
    "Oviedo": "Aarón Escandell",
    "Levante":"Mathew Ryan"
}

# ===========================
# 2. DATOS DE LA PRÓXIMA JORNADA (INPUT MANUAL)
# ===========================
# Aquí defines los partidos y SUS ODDS REALES. 
# p_home_win: Probabilidad de que gane el local (0 a 1). 
# p_over25: Probabilidad de más de 2.5 goles.

INFO_PARTIDOS = [
    # (Local, Visitante, Prob_Victoria_Local, Prob_Over_2.5_Goles)
    {"local": "Rayo Vallecano",  "visitante": "Getafe",          "p_home_win": 0.467, "p_over25": 0.35},
    {"local": "Celta",          "visitante": "Valencia",        "p_home_win": 0.477, "p_over25": 0.55},
    {"local": "Osasuna",         "visitante": "Athletic Club",   "p_home_win": 0.312, "p_over25": 0.60},
    {"local": "Elche",           "visitante": "Villarreal",      "p_home_win": 0.290, "p_over25": 0.55},
    {"local": "Espanyol",        "visitante": "Barcelona",       "p_home_win": 0.155, "p_over25": 0.50},
    {"local": "Sevilla",         "visitante": "Levante",         "p_home_win": 0.538, "p_over25": 0.45},
    {"local": "Real Madrid",     "visitante": "Betis",           "p_home_win": 0.652, "p_over25": 0.65}, # Añadido
    {"local": "Alavés",          "visitante": "Oviedo",           "p_home_win": 0.501, "p_over25": 0.40},
    {"local": "Mallorca",        "visitante": "Girona",          "p_home_win": 0.422, "p_over25": 0.35},
    {"local": "Real Sociedad",   "visitante": "Atletico Madrid", "p_home_win": 0.242, "p_over25": 0.45},
]
FEATURES_MODELO = [
    'fixture_difficulty_away', 'fixture_difficulty_home', 'p_over25_ewma5', 
    'pass_comp_pct_ewma5', 'num_roles_criticos', 'tiene_rol_gk_core', 
    'aerial_won_ewma5', 'aerial_won_roll5', 'psxg_per_90_ewma5', 
    'starter_pct_roll5', 'psxg_per_90', 'elite_handling_interact', 
    'minutes_pct_roll3', 'psxg_ewma5', 'elite_distribution_interact', 
    'psxg_roll5', 'minutes_pct_roll5', 'starter_pct_ewma5', 'pf_roll7', 
    'score_roles_normalizado', 'goles_contra_ewma5', 'psxg_ewma3', 
    'clearances_ewma5', 'pf_ewma5', 'pf_roll5', 'minutes_pct_ewma3', 
    'minutes_pct_ewma5', 'is_home', 'pf_lag1'
]

# ===========================
# 3. FUNCIONES (LIMPIAS DE LEAKAGE)
# ===========================

def cargar_datos():
    print(f"📂 Cargando historial: {ARCHIVO_CSV}")
    try:
        df = pd.read_csv(ARCHIVO_CSV)
        return df
    except:
        return pd.read_csv(ARCHIVO_CSV, encoding='latin-1')

def cargar_modelo():
    # Ajusta aquí el nombre exacto de tu modelo
    ruta_modelo = DIRECTORIO_MODELOS / "best_model_RF.pkl" # <--- OJO: Puse RF por defecto
    ruta_params = DIRECTORIO_MODELOS / "best_model_params_RF.json"
    
    if not ruta_modelo.exists():
        print(f"❌ No encuentro el modelo en {ruta_modelo}")
        return None, None
        
    with open(ruta_modelo, 'rb') as f: modelo = pickle.load(f)
    return modelo, None

def preparar_features_safe(df_historico, portero_nombre, es_local, p_home_win, p_over25):
    """
    Construye las features usando:
    1. Datos HISTÓRICOS (del CSV, hasta el último partido jugado).
    2. Datos CONTEXTUALES (Odds del partido que va a jugarse).
    """
    
    # 1. Obtener historial del portero
    df_portero = df_historico[df_historico['player'] == portero_nombre].copy()
    
    if df_portero.empty:
        print(f"   ⚠️ No hay datos históricos para {portero_nombre}")
        return None
        
    # Ordenar y coger el ÚLTIMO partido JUGADO
    df_portero = df_portero.sort_values('jornada') # Asegúrate que existe columna jornada o fecha
    ultimo_partido_jugado = df_portero.iloc[-1]
    
    features = {}

    # --- A. FEATURES DE CONTEXTO (DEL PARTIDO FUTURO) ---
    # Calculamos la dificultad basada en las ODDS que tú has introducido
    if es_local:
        features['is_home'] = 1
        features['fixture_difficulty_home'] = 1 - p_home_win # Si es muy probable ganar, dificultad baja
        features['fixture_difficulty_away'] = 0
    else:
        features['is_home'] = 0
        features['fixture_difficulty_home'] = 0
        features['fixture_difficulty_away'] = p_home_win # Si el local es probable que gane, difícil para visitante

    # Esta feature a veces es una media histórica o la del partido actual.
    # Si tu modelo se entrenó con la del partido actual, usamos el dato de Odds.
    # Si no, intentamos sacar la media histórica.
    features['p_over25_ewma5'] = float(ultimo_partido_jugado.get('p_over25_ewma5', p_over25))

    # --- B. FEATURES HISTÓRICAS (DEL ÚLTIMO PARTIDO REGISTRADO) ---
    # Aquí mapeamos lo que pasó antes para predecir lo que pasará
    
    # Lista de métricas que son medias móviles (EWMA/Rolling)
    campos_historicos = [
        'pass_comp_pct_ewma5', 'aerial_won_ewma5', 'aerial_won_roll5', 
        'psxg_per_90_ewma5', 'starter_pct_roll5', 'minutes_pct_roll3', 
        'psxg_ewma5', 'psxg_roll5', 'minutes_pct_roll5', 'starter_pct_ewma5', 
        'pf_roll7', 'goles_contra_ewma5', 'psxg_ewma3', 'clearances_ewma5', 
        'pf_ewma5', 'pf_roll5', 'minutes_pct_ewma3', 'minutes_pct_ewma5'
    ]
    
    for campo in campos_historicos:
        # Cogemos el valor del último partido. Si es NaN, ponemos 0.
        features[campo] = float(ultimo_partido_jugado.get(campo, 0))

    # Features estáticas o de rol
    features['num_roles_criticos'] = float(ultimo_partido_jugado.get('num_roles_criticos', 0))
    features['tiene_rol_gk_core'] = float(ultimo_partido_jugado.get('tiene_rol_gk_core', 0))
    features['score_roles_normalizado'] = float(ultimo_partido_jugado.get('score_roles_normalizado', 0))
    features['elite_handling_interact'] = float(ultimo_partido_jugado.get('elite_handling_interact', 0))
    features['elite_distribution_interact'] = float(ultimo_partido_jugado.get('elite_distribution_interact', 0))
    
    # Features especiales
    features['pf_lag1'] = float(ultimo_partido_jugado.get(COLUMNA_OBJETIVO, 0)) # Puntos del partido anterior
    
    # PSxG raw y per 90 (Usamos la media histórica como proxy de la capacidad actual)
    features['psxg_per_90'] = float(ultimo_partido_jugado.get('psxg_per_90_ewma5', 0)) 

    return pd.DataFrame([features])

def asegurar_columnas(df, columnas_modelo):
    # Rellenar con 0 lo que falte para que el modelo no falle
    for col in columnas_modelo:
        if col not in df.columns:
            df[col] = 0.0
    return df[columnas_modelo]

# ===========================
# 4. EJECUCIÓN PRINCIPAL
# ===========================

def main():
    print("🚀 INICIANDO PREDICCIÓN SIN LEAKAGE...")
    
    df_historico = cargar_datos()
    modelo, _ = cargar_modelo()
    
    if modelo is None: return

    resultados = []

    print("\nCalculando predicciones partido a partido...")
    print("-" * 60)

    for info in INFO_PARTIDOS:
        local = info['local']
        visitante = info['visitante']
        p_win = info['p_home_win']
        p_over = info['p_over25']
        
        portero_local_nom = PORTEROS.get(local)
        portero_visit_nom = PORTEROS.get(visitante)
        
        if not portero_local_nom or not portero_visit_nom:
            print(f"⚠️ Saltando {local} vs {visitante} (Falta mapear portero)")
            continue

        # --- Predicción LOCAL ---
        df_feats_loc = preparar_features_safe(df_historico, portero_local_nom, True, p_win, p_over)
        if df_feats_loc is not None:
            df_feats_loc = asegurar_columnas(df_feats_loc, FEATURES_MODELO)
            pred_loc = modelo.predict(df_feats_loc)[0]
        else:
            pred_loc = 0.0

        # --- Predicción VISITANTE ---
        df_feats_vis = preparar_features_safe(df_historico, portero_visit_nom, False, p_win, p_over)
        if df_feats_vis is not None:
            df_feats_vis = asegurar_columnas(df_feats_vis, FEATURES_MODELO)
            pred_vis = modelo.predict(df_feats_vis)[0]
        else:
            pred_vis = 0.0
            
        # Guardar
        resultados.append({
            "Partido": f"{local} vs {visitante}",
            "Portero_Local": portero_local_nom,
            "Prediccion_Local": round(pred_loc, 2),
            "Portero_Visitante": portero_visit_nom,
            "Prediccion_Visitante": round(pred_vis, 2),
            "Diferencia": round(abs(pred_loc - pred_vis), 2)
        })
        
        print(f"✅ {local} ({pred_loc:.2f}) vs {visitante} ({pred_vis:.2f})")

    # Guardar y mostrar
    df_res = pd.DataFrame(resultados)
    print("\n" + "="*60)
    print("RESULTADOS FINALES")
    print("="*60)
    print(df_res.to_string(index=False))
    
    archivo = DIRECTORIO_SALIDA / f"prediccion_final_{datetime.now().strftime('%H%M')}.csv"
    df_res.to_csv(archivo, index=False)
    print(f"\n📁 Guardado en: {archivo}")

if __name__ == "__main__":
    main()
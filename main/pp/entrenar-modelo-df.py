"""
===============================================================================

ENTRENAMIENTO MODELOS FANTASY FOOTBALL - DEFENSAS (DF) CON ROLES MEJORADO

Con GridSearchCV y selección automática de mejores hiperparámetros

===============================================================================

Pipeline: EDA -> Features (TODAS + ROLES DEFENSIVOS) -> GridSearchCV 
          -> Selección Best -> CSV

Autor: Pablo
Fecha: Enero 2026

Clave: GridSearchCV para cada modelo + exportación de features importance + best params

===============================================================================
"""

import warnings
from itertools import product
from pathlib import Path
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from xgboost import XGBRegressor
from scipy.stats import spearmanr
import pickle
import json

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Importar módulo de roles defensivos
try:
    from role_enricher_defensas import (
        enriquecer_dataframe_con_roles_defensivos,
        crear_features_defensivas_roles,
        resumen_roles_defensivos
    )
    ROLES_DISPONIBLES = True
except ImportError:
    print("⚠️  Módulo role_enricher_defensas.py no encontrado. Funcionará sin roles.")
    ROLES_DISPONIBLES = False

warnings.filterwarnings("ignore")

# ===========================
# CONFIGURACIÓN GENERAL
# ===========================

DIRECTORIO_SALIDA = Path("csv/csvGenerados/entrenamiento/defensa_gridsearch_roles")
DIRECTORIO_IMAGENES = DIRECTORIO_SALIDA / "imagenes"
DIRECTORIO_MODELOS = DIRECTORIO_SALIDA / "modelos"
DIRECTORIO_CSVS = DIRECTORIO_SALIDA / "csvs"

for d in [DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS]:
    d.mkdir(parents=True, exist_ok=True)

ARCHIVO_CSV = "csv/csvGenerados/players_with_features_MINIMO.csv"
TAM_VENTANA = 5
TAM_VENTANA_RECIENTE = 3
COLUMNA_OBJETIVO = "puntosFantasy"
TEST_SIZE = 0.2  # 80/20 split

# Usar roles si están disponibles
USAR_ROLES = ROLES_DISPONIBLES

# ===========================
# FUNCIONES AUXILIARES
# ===========================

def extraer_feature_importance(modelo, X_ent, feature_names):
    """Extrae feature importance de un modelo."""
    try:
        if hasattr(modelo, 'feature_importances_'):
            importances = modelo.feature_importances_
        elif hasattr(modelo, 'named_steps'):
            modelo_interno = modelo.named_steps.get('regresor', None)
            if modelo_interno is None:
                return None
            if hasattr(modelo_interno, 'coef_'):
                importances = np.abs(modelo_interno.coef_)
            else:
                return None
        else:
            return None
        
        feature_importance = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
        
        feature_importance['importance'] = (
            feature_importance['importance'] / feature_importance['importance'].sum()
        )
        
        return feature_importance
    except Exception as e:
        print(f"    ⚠️  Error extrayendo importancias: {e}")
        return None

def visualizar_feature_importance(feature_importance, titulo, nombre_archivo, top_n=20):
    """Crea visualización de feature importance"""
    if feature_importance is None or len(feature_importance) == 0:
        return
    
    df_top = feature_importance.head(top_n)
    fig, ax = plt.subplots(figsize=(12, max(8, top_n * 0.4)))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(df_top)))
    
    ax.barh(range(len(df_top)), df_top['importance'].values, color=colors)
    ax.set_yticks(range(len(df_top)))
    ax.set_yticklabels(df_top['feature'].values, fontsize=9)
    ax.set_xlabel('Importancia', fontsize=11, fontweight='bold')
    ax.set_title(titulo, fontsize=12, fontweight='bold', pad=15)
    ax.invert_yaxis()
    
    for i, v in enumerate(df_top['importance'].values):
        ax.text(v + 0.001, i, f'{v:.4f}', va='center', fontsize=8)
    
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / nombre_archivo, dpi=150, bbox_inches='tight')
    plt.close()

def convertir_racha_a_numerico(racha):
    if pd.isna(racha) or not isinstance(racha, str):
        return 0, 0, 0, 0.0
    victorias = racha.count("W")
    empates = racha.count("D")
    derrotas = racha.count("L")
    total = victorias + empates + derrotas
    ratio = victorias / total if total > 0 else 0.0
    return victorias, empates, derrotas, ratio

# ===========================
# CARGA Y PREPARACIÓN
# ===========================

def cargar_datos():
    print(f"📂 Cargando: {ARCHIVO_CSV}")
    try:
        df = pd.read_csv(ARCHIVO_CSV)
        print(f"✅ CSV cargado exitosamente")
    except Exception as e:
        print(f"❌ Error cargando CSV: {e}")
        print(f"   Intentando con encoding 'latin-1'...")
        df = pd.read_csv(ARCHIVO_CSV, encoding='latin-1')
    
    print(f"ℹ️  Total registros: {len(df)}")
    print(f"ℹ️  Total columnas: {len(df.columns)}")
    
    # Filtrar solo defensas (posición DF)
    posicion_cols = [col for col in df.columns if 'posicion' in col.lower()]
    print(f"ℹ️  Columnas de posición encontradas: {posicion_cols}")
    
    if len(posicion_cols) > 0:
        col_pos = posicion_cols[0]
        df_defensas = df[df[col_pos].str.upper() == "DF"].copy()
    else:
        print("⚠️  No se encontró columna de posición. Usando todos los registros.")
        df_defensas = df.copy()
    
    print(f"✅ {df_defensas.shape[0]} defensas (DF) cargadas\n")
    return df_defensas

def diagnosticar_y_limpiar(df):
    print("=" * 80)
    print("DIAGNÓSTICO Y LIMPIEZA DE DATOS")
    print("=" * 80)
    
    filas_inicio = len(df)
    
    print("\n1️⃣ Verificando columnas necesarias...")
    cols_necesarias = ['player', COLUMNA_OBJETIVO, 'Min_partido']
    cols_faltantes = [c for c in cols_necesarias if c not in df.columns]
    if cols_faltantes:
        print(f"   ⚠️  Faltan columnas: {cols_faltantes}")
        print(f"   Columnas disponibles: {df.columns.tolist()[:20]}...")
    else:
        print("   ✅ Todas columnas necesarias presentes")
    
    print("\n2️⃣ Ordenando por jugador + jornada...")
    if 'jornada' in df.columns:
        df = df.sort_values(['player', 'jornada']).reset_index(drop=True)
    else:
        df = df.sort_values('player').reset_index(drop=True)
    print("   ✅ Datos ordenados temporalmente")
    
    print("\n3️⃣ Eliminando registros con <10 minutos...")
    muy_poco_antes = (df['Min_partido'] < 10).sum()
    df = df[df['Min_partido'] >= 10].copy()
    print(f"   ✅ Eliminados {muy_poco_antes} registros")
    
    print("\n4️⃣ Filtrando defensas con <5 partidos...")
    jugs_validos = df.groupby('player').size() >= 5
    jugs_validos = jugs_validos[jugs_validos].index
    antes_jugs = len(df)
    df = df[df['player'].isin(jugs_validos)]
    print(f"   ✅ Eliminados {antes_jugs - len(df)} registros")
    
    print("\n5️⃣ Eliminando outliers extremos...")
    outliers_pf = (df[COLUMNA_OBJETIVO] > 30).sum()
    df = df[df[COLUMNA_OBJETIVO] <= 30].copy()
    print(f"   ✅ Eliminados {outliers_pf} registros")
    
    print("\n6️⃣ Limpiando valores NaN e infinitos...")
    nan_inicio = df.isnull().sum().sum()
    df = df.fillna(df.median(numeric_only=True))
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.fillna(df.median(numeric_only=True))
    print(f"   ✅ Procesados {nan_inicio} valores NaN")
    
    print(f"\nTotal: {filas_inicio} → {len(df)} filas ({100*len(df)/filas_inicio:.1f}%)\n")
    return df

def preparar_basicos(df):
    print("=" * 80)
    print("PREPARACIÓN BÁSICA - ELIMINANDO RUIDO")
    print("=" * 80)
    
    a_eliminar = [
        "posicion", "Equipo_propio", "Equipo_rival",
        "TiroFallado_partido", "TiroPuerta_partido",
        "Regates", "RegatesCompletados", "RegatesFallidos",
        "Conducciones", "DistanciaConduccion", "MetrosAvanzadosConduccion",
        "ConduccionesProgresivas",
        "jornada", "jornada_anterior", "Date", "home", "away",
        "Goles_en_contra", "Porcentaje_paradas",
        "Asist_partido", "xAG", "xG_partido", "Tiros", "target_pf_next",
    ]
    a_eliminar = [c for c in a_eliminar if c in df.columns]
    df = df.drop(columns=a_eliminar, errors="ignore")
    
    if "racha5partidos" in df.columns:
        datos = df["racha5partidos"].apply(convertir_racha_a_numerico)
        df["racha_victorias"] = datos.apply(lambda x: x[0])
        df["racha_ratio_victorias"] = datos.apply(lambda x: x[3])
        df = df.drop(columns=["racha5partidos"], errors="ignore")
    
    if "racha5partidos_rival" in df.columns:
        datos_rival = df["racha5partidos_rival"].apply(convertir_racha_a_numerico)
        df["racha_rival_victorias"] = datos_rival.apply(lambda x: x[0])
        df["racha_rival_ratio_victorias"] = datos_rival.apply(lambda x: x[3])
        df = df.drop(columns=["racha5partidos_rival"], errors="ignore")
    
    print("✅ Limpieza completada\n")
    return df

# ===========================
# INGENIERÍA DE FEATURES DEFENSIVAS
# ===========================

def crear_features_probabilisticas(df):
    """Features basadas en probabilidades del partido"""
    print("=" * 80)
    print("FEATURES PROBABILÍSTICAS - EXPECTATIVAS DEL PARTIDO")
    print("=" * 80)
    
    if "p_win_propio" in df.columns:
        df["p_win_propio"] = pd.to_numeric(df["p_win_propio"], errors='coerce').fillna(0.5)
        df["p_win_propio_ewma5"] = df.groupby("player")["p_win_propio"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0.5)
        print("✅ Probabilidad de victoria propia (ewma5)")
    
    if "p_loss_propio" in df.columns:
        df["p_loss_propio"] = pd.to_numeric(df["p_loss_propio"], errors='coerce').fillna(0.5)
        df["p_loss_propio_ewma5"] = df.groupby("player")["p_loss_propio"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0.5)
        print("✅ Probabilidad de derrota propia (ewma5)")
    
    if "p_over25" in df.columns:
        df["p_over25"] = pd.to_numeric(df["p_over25"], errors='coerce').fillna(0.5)
        df["p_over25_ewma5"] = df.groupby("player")["p_over25"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0.5)
        print("✅ Probabilidad over 2.5 (ewma5)")
    
    print()
    return df

def crear_features_defensivas_mejoradas(df):
    print("=" * 80)
    print("FEATURES DEFENSIVAS MEJORADAS - ANÁLISIS PROFUNDO")
    print("=" * 80)
    
    df["Min_partido_safe"] = df["Min_partido"].replace(0, np.nan)
    
    # ENTRADAS (Tackles)
    if "Entradas" in df.columns:
        df["Entradas"] = pd.to_numeric(df["Entradas"], errors='coerce').fillna(0)
        df["tackles_ewma3"] = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
        ).fillna(0)
        df["tackles_ewma5"] = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df["tackles_roll7"] = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift().rolling(7, min_periods=1).mean()
        ).fillna(0)
        df["tackles_lag1"] = df.groupby("player")["Entradas"].shift(1).fillna(0)
        print("✅ Tackles (ewma3, ewma5, roll7, lag1)")
    
    # INTERCEPCIONES
    if "Intercepciones" in df.columns:
        df["Intercepciones"] = pd.to_numeric(df["Intercepciones"], errors='coerce').fillna(0)
        df["interceptions_ewma5"] = df.groupby("player")["Intercepciones"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df["interceptions_roll5"] = df.groupby("player")["Intercepciones"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df["interceptions_lag1"] = df.groupby("player")["Intercepciones"].shift(1).fillna(0)
        print("✅ Interceptions (ewma5, roll5, lag1)")
    
    # DESPEJES
    if "Despejes" in df.columns:
        df["Despejes"] = pd.to_numeric(df["Despejes"], errors='coerce').fillna(0)
        df["clearances_ewma3"] = df.groupby("player")["Despejes"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
        ).fillna(0)
        df["clearances_ewma5"] = df.groupby("player")["Despejes"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df["clearances_roll7"] = df.groupby("player")["Despejes"].transform(
            lambda x: x.shift().rolling(7, min_periods=1).mean()
        ).fillna(0)
        df["clearances_lag1"] = df.groupby("player")["Despejes"].shift(1).fillna(0)
        print("✅ Clearances (ewma3, ewma5, roll7, lag1)")
    
    # DUELOS
    if "Duelos" in df.columns:
        df["Duelos"] = pd.to_numeric(df["Duelos"], errors='coerce').fillna(0)
        df["duels_roll5"] = df.groupby("player")["Duelos"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df["duels_ewma5"] = df.groupby("player")["Duelos"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        print("✅ Duels (roll5, ewma5)")
    
    # DUELOS GANADOS
    if "DuelosGanados" in df.columns:
        df["DuelosGanados"] = pd.to_numeric(df["DuelosGanados"], errors='coerce').fillna(0)
        df["duels_won_ewma5"] = df.groupby("player")["DuelosGanados"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df["duels_won_roll5"] = df.groupby("player")["DuelosGanados"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        print("✅ Duels won (ewma5, roll5)")
    
    # WIN PERCENTAGE EN DUELOS
    if "Duelos" in df.columns and "DuelosGanados" in df.columns:
        df["duels_pct_temp"] = (df["DuelosGanados"] / (df["Duelos"] + 1)).fillna(0.5)
        df["duels_won_pct_ewma5"] = df.groupby("player")["duels_pct_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0.5)
        df = df.drop(columns=["duels_pct_temp"])
        print("✅ Win % en duelos (ewma5)")
    
    # DUELOS AÉREOS GANADOS
    if "DuelosAereosGanados" in df.columns:
        df["DuelosAereosGanados"] = pd.to_numeric(df["DuelosAereosGanados"], errors='coerce').fillna(0)
        df["aerial_won_ewma5"] = df.groupby("player")["DuelosAereosGanados"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df["aerial_won_roll5"] = df.groupby("player")["DuelosAereosGanados"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        print("✅ Aerial duels won (ewma5, roll5)")
    
    # ACCIONES DEFENSIVAS TOTALES
    if all(c in df.columns for c in ["Entradas", "Despejes"]):
        df["def_actions_temp"] = df["Entradas"] + df["Despejes"]
        df["def_actions_ewma5"] = df.groupby("player")["def_actions_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df["def_actions_roll7"] = df.groupby("player")["def_actions_temp"].transform(
            lambda x: x.shift().rolling(7, min_periods=1).mean()
        ).fillna(0)
        df = df.drop(columns=["def_actions_temp"])
        print("✅ Defensive actions (ewma5, roll7)")
    
    print()
    return df

def crear_features_form_mejorado(df):
    print("=" * 80)
    print("FANTASY POINTS FORM - ANÁLISIS EXTENDIDO")
    print("=" * 80)
    
    if COLUMNA_OBJETIVO in df.columns:
        df[COLUMNA_OBJETIVO] = pd.to_numeric(df[COLUMNA_OBJETIVO], errors='coerce').fillna(0)
        
        df["pf_roll3"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        df["pf_ewma3"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
        ).fillna(0)
        df["pf_roll5"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df["pf_ewma5"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df["pf_roll7"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(7, min_periods=1).mean()
        ).fillna(0)
        df["pf_std3"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).std()
        ).fillna(0)
        
        pf_mean3 = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(1)
        df["pf_volatility3"] = (df["pf_std3"] / (pf_mean3 + 1e-6)).fillna(0).replace([np.inf, -np.inf], 0)
        
        df["pf_lag1"] = df.groupby("player")[COLUMNA_OBJETIVO].shift(1).fillna(0)
        df["pf_lag2"] = df.groupby("player")[COLUMNA_OBJETIVO].shift(2).fillna(0)
        
        print("✅ PF Form (roll3/5/7, ewma3/5, std3, volatility3, lag1/2)\n")
    
    return df

def crear_features_disponibilidad_completo(df):
    print("=" * 80)
    print("DISPONIBILIDAD - ANÁLISIS COMPLETO")
    print("=" * 80)
    
    df["Min_partido"] = pd.to_numeric(df["Min_partido"], errors='coerce').fillna(45)
    df["minutes_pct_temp"] = (df["Min_partido"] / 90).fillna(0).clip(0, 1)
    
    df["minutes_pct_roll3"] = df.groupby("player")["minutes_pct_temp"].transform(
        lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
    ).fillna(0)
    df["minutes_pct_roll5"] = df.groupby("player")["minutes_pct_temp"].transform(
        lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
    ).fillna(0)
    df["minutes_pct_ewma3"] = df.groupby("player")["minutes_pct_temp"].transform(
        lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
    ).fillna(0)
    df["minutes_pct_ewma5"] = df.groupby("player")["minutes_pct_temp"].transform(
        lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
    ).fillna(0)
    
    if "Titular" in df.columns:
        df["Titular"] = pd.to_numeric(df["Titular"], errors='coerce').fillna(0)
        df["starter_pct_roll5"] = df.groupby("player")["Titular"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df["starter_pct_ewma5"] = df.groupby("player")["Titular"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        print("✅ Starter % (roll5, ewma5)")
    
    df = df.drop(columns=["minutes_pct_temp"])
    
    print("✅ Minutes (pct_roll3/5, pct_ewma3/5)\n")
    return df

def crear_features_contexto_completo(df):
    print("=" * 80)
    print("CONTEXTO PRE-PARTIDO - ANÁLISIS COMPLETO")
    print("=" * 80)
    
    if "local" in df.columns:
        df["local"] = pd.to_numeric(df["local"], errors='coerce').fillna(0)
        df["is_home"] = (df["local"] == 1).astype(int)
    else:
        df["is_home"] = 0
    
    if "p_home" in df.columns:
        df["p_home"] = pd.to_numeric(df["p_home"], errors='coerce').fillna(0.5)
        df["fixture_difficulty_home"] = (1 - df["p_home"]).clip(0, 1)
        df["fixture_difficulty_away"] = df["p_home"].clip(0, 1)
        print("✅ Fixture difficulty (home/away)")
    
    print("✅ Home/Away (is_home)\n")
    return df

def crear_features_rival_completo(df):
    print("=" * 80)
    print("FEATURES RIVAL - CONTEXTO OFENSIVO Y DEFENSIVO")
    print("=" * 80)
    
    if "shots_rival_partido" in df.columns:
        df["shots_rival_partido"] = pd.to_numeric(df["shots_rival_partido"], errors='coerce').fillna(0)
        df["opp_shots_roll5"] = df.groupby("player")["shots_rival_partido"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df["opp_shots_ewma5"] = df.groupby("player")["shots_rival_partido"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        print("✅ Opponent shots (roll5, ewma5)")
    
    if "gc" in df.columns:
        df["gc"] = pd.to_numeric(df["gc"], errors='coerce').fillna(0)
        df["opp_gc_ewma5"] = df.groupby("player")["gc"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        df["opp_gc_roll5"] = df.groupby("player")["gc"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        print("✅ Opponent goals conceded (ewma5, roll5)")
    
    if "racha_rival_ratio_victorias" in df.columns:
        df["racha_rival_ratio_victorias"] = pd.to_numeric(df["racha_rival_ratio_victorias"], errors='coerce').fillna(0.5)
        df["opp_form_roll5"] = df.groupby("player")["racha_rival_ratio_victorias"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0.5)
        print("✅ Opponent form (roll5)")
    
    print()
    return df

def crear_features_eficiencia_completo(df):
    print("=" * 80)
    print("EFICIENCIA DEFENSIVA - ÍNDICES COMPLETOS")
    print("=" * 80)
    
    if all(c in df.columns for c in ["Entradas", "Despejes"]):
        df["ratio_temp"] = (df["Entradas"] / (df["Despejes"] + 1)).fillna(0).replace([np.inf, -np.inf], 0)
        df["tackles_clearances_ratio_roll5"] = df.groupby("player")["ratio_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        df = df.drop(columns=["ratio_temp"])
        print("✅ Tackles to clearances ratio (roll5)")
    
    print()
    return df

# ===========================
# INTEGRACIÓN DE ROLES
# ===========================

def integrar_roles(df):
    """Integra roles defensivos si están disponibles"""
    if not USAR_ROLES:
        print("⚠️  Roles deshabilitados. Saltando integración.\n")
        return df
    
    try:
        print("=" * 80)
        print("INTEGRACIÓN DE ROLES DEFENSIVOS (FBRef)")
        print("=" * 80)
        
        # Enriquecer con roles
        df = enriquecer_dataframe_con_roles_defensivos(df, columna_roles="roles")
        
        # Crear features de interacción
        df = crear_features_defensivas_roles(df, columna_objetivo=COLUMNA_OBJETIVO)
        
        print("✅ Roles defensivos integrados exitosamente\n")
        
    except Exception as e:
        print(f"❌ Error integrando roles: {e}\n")
    
    return df

# ===========================
# DEFINICIÓN DE VARIABLES FINALES
# ===========================

def definir_variables_finales(df):
    print("=" * 80)
    print("VARIABLES FINALES - SELECCIÓN COMPLETA")
    print("=" * 80)
    
    variables = [
        # Defensive core
        "tackles_ewma3", "tackles_ewma5", "tackles_roll7", "tackles_lag1",
        "interceptions_ewma5", "interceptions_roll5", "interceptions_lag1",
        "clearances_ewma3", "clearances_ewma5", "clearances_roll7", "clearances_lag1",
        "duels_roll5", "duels_ewma5", "duels_won_ewma5", "duels_won_roll5", "duels_won_pct_ewma5",
        "def_actions_ewma5", "def_actions_roll7",
        "aerial_won_ewma5", "aerial_won_roll5",
        # Eficiencia
        "tackles_clearances_ratio_roll5",
        # Form
        "pf_roll3", "pf_ewma3", "pf_roll5", "pf_ewma5", "pf_roll7", "pf_volatility3", "pf_lag1", "pf_lag2",
        # Availability
        "minutes_pct_roll3", "minutes_pct_roll5", "minutes_pct_ewma3", "minutes_pct_ewma5",
        "starter_pct_roll5", "starter_pct_ewma5",
        # Context
        "is_home", "fixture_difficulty_home", "fixture_difficulty_away",
        # Opponent
        "opp_shots_roll5", "opp_shots_ewma5", "opp_gc_ewma5", "opp_gc_roll5", "opp_form_roll5",
        # Probabilistic
        "p_win_propio_ewma5", "p_loss_propio_ewma5", "p_over25_ewma5",
    ]
    
    variables = [v for v in variables if v in df.columns]
    
    # Agregar solo las variables de interacción/resumen de roles defensivos
    if USAR_ROLES:
        roles_vars = [
            "elite_entradas_interact", "elite_intercepciones_interact", "elite_despejes_interact",
            "score_roles_normalizado", "num_roles_criticos", "ratio_roles_criticos",
            "tiene_rol_defensivo_core", "score_defensivo"
        ]
        variables.extend([v for v in roles_vars if v in df.columns])
    
    variables = list(set(variables))
    variables = [v for v in variables if v in df.columns]
    
    print(f"\n📊 Total de variables seleccionadas: {len(variables)}")
    print("  (Solo se incluyen variables de interacción/resumen de roles, no num_roles ni rol_*_valor)\n")
    
    return variables

# ===========================
# GRIDSEARCHCV - ENTRENAMIENTO
# ===========================

def entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables):
    print("=" * 80)
    print("ENTRENAMIENTO CON GRIDSEARCHCV - OPTIMIZACIÓN DE HIPERPARÁMETROS")
    print("=" * 80)
    print()
    
    resultados_finales = {}
    lista_resultados = []
    
    # ========================
    # 1. RANDOM FOREST
    # ========================
    print("🌲 Random Forest con GridSearchCV...")
    rf_params = {
        'n_estimators': [ 200, 300],
        'max_depth': [10, 20, 25],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'max_features': ['sqrt', 'log2']
    }
    
    rf_base = RandomForestRegressor(random_state=42, n_jobs=-1)
    rf_gs = GridSearchCV(rf_base, rf_params, cv=3, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    rf_gs.fit(X_train, y_train)
    
    rf_best = rf_gs.best_estimator_
    pred_rf = rf_best.predict(X_test)
    mae_rf = mean_absolute_error(y_test, pred_rf)
    rmse_rf = root_mean_squared_error(y_test, pred_rf)
    spearman_rf, _ = spearmanr(y_test, pred_rf)
    
    print(f"  ✅ MAE: {mae_rf:.4f}, RMSE: {rmse_rf:.4f}, Spearman: {spearman_rf:.4f}")
    print(f"  ✅ Best params: {rf_gs.best_params_}\n")
    
    resultados_finales['RF'] = {
        'mae': mae_rf, 'rmse': rmse_rf, 'spearman': spearman_rf, 
        'modelo': rf_best, 'params': rf_gs.best_params_,
        'cv_score': rf_gs.best_score_
    }
    
    lista_resultados.append({
        'Model': 'Random Forest',
        'MAE': mae_rf,
        'RMSE': rmse_rf,
        'Spearman': spearman_rf,
        'Best_Params': str(rf_gs.best_params_)
    })
    
    # Feature importance RF
    fi_rf = extraer_feature_importance(rf_best, X_train, variables)
    if fi_rf is not None:
        fi_rf.to_csv(DIRECTORIO_CSVS / "feature_importance_rf.csv", index=False)
        print(f"  ✅ Feature importance guardado\n")
    visualizar_feature_importance(fi_rf, "Random Forest - Top 20 Features", "01_feature_importance_rf.png", top_n=20)
    
    # ========================
    # 2. XGBOOST
    # ========================
    print("🚀 XGBoost con GridSearchCV...")
    xgb_params = {
        'max_depth': [ 5, 7],
        'learning_rate': [0.01, 0.1],
        'n_estimators': [50, 100, 150],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.7, 0.8, 0.9],
        'gamma': [0, 0.1, 0.5]
    }
    
    xgb_base = XGBRegressor(random_state=42, n_jobs=-1)
    xgb_gs = GridSearchCV(xgb_base, xgb_params, cv=3, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    xgb_gs.fit(X_train, y_train)
    
    xgb_best = xgb_gs.best_estimator_
    pred_xgb = xgb_best.predict(X_test)
    mae_xgb = mean_absolute_error(y_test, pred_xgb)
    rmse_xgb = root_mean_squared_error(y_test, pred_xgb)
    spearman_xgb, _ = spearmanr(y_test, pred_xgb)
    
    print(f"  ✅ MAE: {mae_xgb:.4f}, RMSE: {rmse_xgb:.4f}, Spearman: {spearman_xgb:.4f}")
    print(f"  ✅ Best params: {xgb_gs.best_params_}\n")
    
    resultados_finales['XGB'] = {
        'mae': mae_xgb, 'rmse': rmse_xgb, 'spearman': spearman_xgb, 
        'modelo': xgb_best, 'params': xgb_gs.best_params_,
        'cv_score': xgb_gs.best_score_
    }
    
    lista_resultados.append({
        'Model': 'XGBoost',
        'MAE': mae_xgb,
        'RMSE': rmse_xgb,
        'Spearman': spearman_xgb,
        'Best_Params': str(xgb_gs.best_params_)
    })
    
    # Feature importance XGB
    fi_xgb = extraer_feature_importance(xgb_best, X_train, variables)
    if fi_xgb is not None:
        fi_xgb.to_csv(DIRECTORIO_CSVS / "feature_importance_xgb.csv", index=False)
        print(f"  ✅ Feature importance guardado\n")
    visualizar_feature_importance(fi_xgb, "XGBoost - Top 20 Features", "02_feature_importance_xgb.png", top_n=20)
    
    # ========================
    # 3. RIDGE
    # ========================
    print("📏 Ridge Regression con GridSearchCV...")
    ridge_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('regresor', Ridge())
    ])
    
    ridge_params = {
        'regresor__alpha': [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
    }
    
    ridge_gs = GridSearchCV(ridge_pipeline, ridge_params, cv=3, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    ridge_gs.fit(X_train, y_train)
    
    ridge_best = ridge_gs.best_estimator_
    pred_ridge = ridge_best.predict(X_test)
    mae_ridge = mean_absolute_error(y_test, pred_ridge)
    rmse_ridge = root_mean_squared_error(y_test, pred_ridge)
    spearman_ridge, _ = spearmanr(y_test, pred_ridge)
    
    print(f"  ✅ MAE: {mae_ridge:.4f}, RMSE: {rmse_ridge:.4f}, Spearman: {spearman_ridge:.4f}")
    print(f"  ✅ Best params: {ridge_gs.best_params_}\n")
    
    resultados_finales['Ridge'] = {
        'mae': mae_ridge, 'rmse': rmse_ridge, 'spearman': spearman_ridge, 
        'modelo': ridge_best, 'params': ridge_gs.best_params_,
        'cv_score': ridge_gs.best_score_
    }
    
    lista_resultados.append({
        'Model': 'Ridge',
        'MAE': mae_ridge,
        'RMSE': rmse_ridge,
        'Spearman': spearman_ridge,
        'Best_Params': str(ridge_gs.best_params_)
    })
    
    # Feature importance Ridge
    fi_ridge = extraer_feature_importance(ridge_best, X_train, variables)
    if fi_ridge is not None:
        fi_ridge.to_csv(DIRECTORIO_CSVS / "feature_importance_ridge.csv", index=False)
        print(f"  ✅ Feature importance guardado\n")
    visualizar_feature_importance(fi_ridge, "Ridge - Top 20 Features", "03_feature_importance_ridge.png", top_n=20)
    
    # ========================
    # 4. ELASTICNET
    # ========================
    print("🔗 ElasticNet con GridSearchCV...")
    elastic_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('regresor', ElasticNet(random_state=42))
    ])
    
    elastic_params = {
        'regresor__alpha': [0.001, 0.01, 0.1, 1.0],
        'regresor__l1_ratio': [0.2, 0.5, 0.8],
        'regresor__max_iter': [2000, 4000, 8000]
    }
    
    elastic_gs = GridSearchCV(elastic_pipeline, elastic_params, cv=3, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    elastic_gs.fit(X_train, y_train)
    
    elastic_best = elastic_gs.best_estimator_
    pred_elastic = elastic_best.predict(X_test)
    mae_elastic = mean_absolute_error(y_test, pred_elastic)
    rmse_elastic = root_mean_squared_error(y_test, pred_elastic)
    spearman_elastic, _ = spearmanr(y_test, pred_elastic)
    
    print(f"  ✅ MAE: {mae_elastic:.4f}, RMSE: {rmse_elastic:.4f}, Spearman: {spearman_elastic:.4f}")
    print(f"  ✅ Best params: {elastic_gs.best_params_}\n")
    
    resultados_finales['ElasticNet'] = {
        'mae': mae_elastic, 'rmse': rmse_elastic, 'spearman': spearman_elastic, 
        'modelo': elastic_best, 'params': elastic_gs.best_params_,
        'cv_score': elastic_gs.best_score_
    }
    
    lista_resultados.append({
        'Model': 'ElasticNet',
        'MAE': mae_elastic,
        'RMSE': rmse_elastic,
        'Spearman': spearman_elastic,
        'Best_Params': str(elastic_gs.best_params_)
    })
    
    # Feature importance ElasticNet
    fi_elastic = extraer_feature_importance(elastic_best, X_train, variables)
    if fi_elastic is not None:
        fi_elastic.to_csv(DIRECTORIO_CSVS / "feature_importance_elastic.csv", index=False)
        print(f"  ✅ Feature importance guardado\n")
    visualizar_feature_importance(fi_elastic, "ElasticNet - Top 20 Features", "04_feature_importance_elastic.png", top_n=20)
    
    # ========================
    # GUARDAR RESULTADOS GENERALES
    # ========================
    df_resultados = pd.DataFrame(lista_resultados)
    df_resultados.to_csv(DIRECTORIO_CSVS / "resultados_gridsearch.csv", index=False)
    print(f"✅ Resultados guardados en CSV\n")
    
    return resultados_finales

# ===========================
# MAIN
# ===========================

def main():
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETO - ENTRENAMIENTO DEFENSAS CON ROLES Y GRIDSEARCHCV")
    print("=" * 80 + "\n")
    
    # Cargar datos
    df = cargar_datos()
    
    # Limpiar
    df = diagnosticar_y_limpiar(df)
    
    # Preparar básicos
    df = preparar_basicos(df)
    
    # Features defensivas
    df = crear_features_defensivas_mejoradas(df)
    
    # Features de forma
    df = crear_features_form_mejorado(df)
    
    # Features de disponibilidad
    df = crear_features_disponibilidad_completo(df)
    
    # Features de contexto
    df = crear_features_contexto_completo(df)
    
    # Features rival
    df = crear_features_rival_completo(df)
    
    # Features de eficiencia
    df = crear_features_eficiencia_completo(df)
    
    # Features probabilísticas
    df = crear_features_probabilisticas(df)
    
    # INTEGRACIÓN DE ROLES DEFENSIVOS
    df = integrar_roles(df)
    
    # Definir variables finales
    variables = definir_variables_finales(df)
    
    
    # Preparar datos para entrenamiento
    print("=" * 80)
    print("PREPARACIÓN PARA ENTRENAMIENTO")
    print("=" * 80)
    
    df_train = df.dropna(subset=[COLUMNA_OBJETIVO])
    df_train = df_train[df_train[COLUMNA_OBJETIVO] > 0]
    
    X = df_train[variables].fillna(0)
    y = df_train[COLUMNA_OBJETIVO]
    
    # Split
    split_idx = int(len(X) * (1 - TEST_SIZE))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Training set: {len(X_train)} muestras")
    print(f"Test set: {len(X_test)} muestras\n")
    
    # Entrenar con GridSearchCV
    resultados = entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables)
    
    # ========================
    # RESUMEN Y SELECCIÓN DEL MEJOR MODELO
    # ========================
    print("=" * 80)
    print("RESUMEN FINAL - MEJORES HIPERPARÁMETROS POR MODELO")
    print("=" * 80)
    print()
    
    # Encontrar modelo con mejor MAE
    mejor_modelo = min(resultados.items(), key=lambda x: x[1]['mae'])
    mejor_nombre = mejor_modelo[0]
    mejor_metrics = mejor_modelo[1]
    
    print("RANKING DE MODELOS POR MAE:\n")
    for i, (modelo_name, metrics) in enumerate(sorted(resultados.items(), key=lambda x: x[1]['mae']), 1):
        print(f"{i}. {modelo_name:12s}")
        print(f"   MAE:    {metrics['mae']:.4f}")
        print(f"   RMSE:   {metrics['rmse']:.4f}")
        print(f"   Spearman: {metrics['spearman']:.4f}")
        print(f"   CV Score: {metrics['cv_score']:.4f}")
        print(f"   Hyperparameters: {metrics['params']}")
        print()
    
    print("=" * 80)
    print(f"🏆 MEJOR MODELO: {mejor_nombre}")
    print("=" * 80)
    print(f"MAE:    {mejor_metrics['mae']:.4f}")
    print(f"RMSE:   {mejor_metrics['rmse']:.4f}")
    print(f"Spearman: {mejor_metrics['spearman']:.4f}")
    print(f"CV Score: {mejor_metrics['cv_score']:.4f}")
    print(f"\nHiperparámetros óptimos:")
    for param, value in mejor_metrics['params'].items():
        print(f"  • {param}: {value}")
    print()
    
    # Guardar mejor modelo
    with open(DIRECTORIO_MODELOS / f"best_model_{mejor_nombre}.pkl", 'wb') as f:
        pickle.dump(mejor_metrics['modelo'], f)
    print(f"✅ Modelo guardado en: {DIRECTORIO_MODELOS / f'best_model_{mejor_nombre}.pkl'}")
    
    # Guardar configuración del mejor modelo
    with open(DIRECTORIO_MODELOS / f"best_model_params_{mejor_nombre}.json", 'w') as f:
        json.dump(mejor_metrics['params'], f, indent=4)
    print(f"✅ Parámetros guardados en: {DIRECTORIO_MODELOS / f'best_model_params_{mejor_nombre}.json'}\n")
    
    print("✅ Pipeline completado exitosamente\n")

if __name__ == "__main__":
    main()
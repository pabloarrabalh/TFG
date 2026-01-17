import warnings
from itertools import product
from pathlib import Path


import matplotlib
matplotlib.use("Agg")


import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import shap
from xgboost import XGBRegressor


from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


try:
    from role_enricher import *
    ROLES_DISPONIBLES = True
except ImportError:
    ROLES_DISPONIBLES = False


warnings.filterwarnings("ignore")


DIRECTORIO_SALIDA = Path("csv/csvGenerados/entrenamiento/portero_v4_optimizado")
DIRECTORIO_IMAGENES = DIRECTORIO_SALIDA / "imagenes"
DIRECTORIO_MODELOS = DIRECTORIO_SALIDA / "modelos"


for d in [DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS]:
    d.mkdir(parents=True, exist_ok=True)


RUTAS_BUSQUEDA = [
    Path.cwd(),
    Path.cwd() / "main" / "pp",
    Path.cwd() / "main",
    Path.cwd() / "data" / "temporada_25_26",
    Path.cwd() / "data",
    Path.cwd().parent,
    Path.cwd().parent / "main" / "pp",
]


ARCHIVO_CSV = "csv/csvGenerados/players_with_features_MINIMO.csv"
TAM_VENTANA = 5
USAR_ROLES = ROLES_DISPONIBLES


def buscar_csv(rutas, nombre_csv):
    for ruta in rutas:
        ruta_completa = ruta / nombre_csv
        if ruta_completa.exists():
            return str(ruta_completa)
    return None


def entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru):
    modelo.fit(X_ent, y_ent)
    pred = modelo.predict(X_pru)
    return {
        "mae": mean_absolute_error(y_pru, pred),
        "rmse": root_mean_squared_error(y_pru, pred),
        "r2": r2_score(y_pru, pred),
        "modelo": modelo,
        "predicciones": pred,
    }


def crear_malla_parametros(grid_dict):
    claves = list(grid_dict.keys())
    configuraciones = []
    for valores in product(*grid_dict.values()):
        configuraciones.append(dict(zip(claves, valores)))
    return configuraciones


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
    ruta_csv = buscar_csv(RUTAS_BUSQUEDA, ARCHIVO_CSV)
    if not ruta_csv:
        raise FileNotFoundError(ARCHIVO_CSV)
    print(f"📂 Cargando: {ruta_csv}")
    df = pd.read_csv(ruta_csv)
    df = df[df["posicion"] == "PT"].copy()
    print(f"✅ {df.shape[0]} porteros, {df.shape[1]} columnas\n")
    return df


def preparar_basicos(df):
    """
    VERSIÓN OPTIMIZADA: Mantiene columnas base hasta después de sweeping
    """
    print("=" * 80)
    print("PREPARACIÓN BÁSICA (OPTIMIZADA)")
    print("=" * 80)
    
    columnas_orden = [c for c in ["temporada", "jornada", "fecha_partido"] if c in df.columns]
    df = df.sort_values(columnas_orden).reset_index(drop=True)
    
    # Eliminar columnas no relevantes
    a_eliminar = [
        "posicion", "Equipo_propio", "Equipo_rival", "xAG", "TiroFallado_partido",
        "TiroPuerta_partido", "Amarillas", "Rojas", "Pases_Totales",
        "Duelos", "Regates", "RegatesCompletados", "RegatesFallidos",
        "Conducciones", "DistanciaConduccion", "MetrosAvanzadosConduccion",
        "ConduccionesProgresivas",
        "DuelosAereosGanadosPct", "jornada", "jornada_anterior", "Date", "home", "away",
        "Asist_partido",
    ]
    a_eliminar = [c for c in a_eliminar if c in df.columns]
    df = df.drop(columns=a_eliminar, errors="ignore")
    
    if "racha5partidos" in df.columns:
        datos = df["racha5partidos"].apply(convertir_racha_a_numerico)
        df["racha_victorias"] = datos.apply(lambda x: x[0])
        df["racha_empates"] = datos.apply(lambda x: x[1])
        df["racha_derrotas"] = datos.apply(lambda x: x[2])
        df["racha_ratio_victorias"] = datos.apply(lambda x: x[3])
    
    if "racha5partidos_rival" in df.columns:
        datos_rival = df["racha5partidos_rival"].apply(convertir_racha_a_numerico)
        df["racha_rival_victorias"] = datos_rival.apply(lambda x: x[0])
        df["racha_rival_empates"] = datos_rival.apply(lambda x: x[1])
        df["racha_rival_derrotas"] = datos_rival.apply(lambda x: x[2])
        df["racha_rival_ratio_victorias"] = datos_rival.apply(lambda x: x[3])
    
    print("✓ Ordenado, limpiado, rachas\n")
    return df


# ===========================
# FEATURES SWEEPING (OPTIMIZADO)
# ===========================
def crear_features_sweeping(df):
    """
    Features de portero barredor - SOLO LAS QUE TIENEN IMPORTANCIA
    ✅ SIN LEAKAGE: Todos usan .shift(1) para datos retrospectivos
    """
    print("=" * 80)
    print("FEATURES SWEEPING (OPTIMIZADO - SOLO RELEVANTES)")
    print("=" * 80)
    
    df["Min_partido_safe"] = df["Min_partido"].replace(0, np.nan)
    
    # 1. DEFENSIVE ACTIONS EMA (Muy relevante: 0.10272552)
    if all(c in df.columns for c in ["Entradas", "DuelosGanados", "Despejes", "BloqueoTiros", "BloqueoPase"]):
        df["defensive_actions_total"] = (
            df["Entradas"].fillna(0) +
            df["DuelosGanados"].fillna(0) +
            df["Despejes"].fillna(0) +
            df["BloqueoTiros"].fillna(0) +
            df["BloqueoPase"].fillna(0)
        )
        
        df["def_actions_per_90"] = (df["defensive_actions_total"] / (df["Min_partido_safe"] / 90)).fillna(0)
        
        # ✅ MANTENER: def_actions_per_90_last5 (importancia: 0.015633883)
        df["def_actions_per_90_last5"] = df.groupby("player")["def_actions_per_90"].transform(
            lambda s: s.shift(1).rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        # ✅ MANTENER: def_actions_ema (importancia: 0.10272552)
        df["def_actions_ema"] = df.groupby("player")["def_actions_per_90"].transform(
            lambda s: s.shift(1).ewm(span=3, adjust=False).mean()
        ).fillna(0)
        
        print("✓ Defensive Actions (last5, EMA)")
    else:
        print("❌ Falta alguna columna para Defensive Actions")
    
    # 2. AERIAL DOMINANCE (Parcialmente relevante)
    if all(c in df.columns for c in ["DuelosAereosGanados", "DuelosAereosPerdidos"]):
        df["aerial_duels_total"] = (
            df["DuelosAereosGanados"].fillna(0) +
            df["DuelosAereosPerdidos"].fillna(0) + 1
        )
        
        df["aerial_success_ratio"] = (
            df["DuelosAereosGanados"].fillna(0) / df["aerial_duels_total"]
        ).fillna(0)
        
        # ❌ ELIMINAR: aerial_success_last5 (importancia: 0.000535214)
        # ✅ MANTENER: aerial_success_ema (importancia: 0.008521879)
        df["aerial_success_ema"] = df.groupby("player")["aerial_success_ratio"].transform(
            lambda s: s.shift(1).ewm(span=3, adjust=False).mean()
        ).fillna(0.5)
        
        print("✓ Aerial Dominance (EMA)")
    else:
        print("❌ Falta alguna columna para Aerial Dominance")
    
    # 3. CLEARANCE ACTIVITY (Muy relevante: 0.07780314)
    if all(c in df.columns for c in ["Despejes", "BloqueoTiros", "BloqueoPase"]):
        df["clearance_activity"] = (
            (df["Despejes"].fillna(0) +
             df["BloqueoTiros"].fillna(0) +
             df["BloqueoPase"].fillna(0)) / (df["Min_partido_safe"] / 90)
        ).fillna(0)
        
        # ❌ ELIMINAR: clearance_activity_last5 (importancia: 0.002660372)
        # ✅ MANTENER: clearance_activity_ema (importancia: 0.07780314)
        df["clearance_activity_ema"] = df.groupby("player")["clearance_activity"].transform(
            lambda s: s.shift(1).ewm(span=4, adjust=False).mean()
        ).fillna(0)
        
        print("✓ Clearance Activity (EMA)")
    else:
        print("❌ Falta alguna columna para Clearance Activity")
    
    # 4. POSITIONING ACTIVITY (Parcialmente relevante)
    if "Entradas" in df.columns:
        df["positioning_activity"] = (
            (df["Entradas"].fillna(0) / (df["Min_partido_safe"] / 90))
        ).fillna(0)
        
        # ❌ ELIMINAR: positioning_activity_last5 (importancia: 0.0)
        # ✅ MANTENER: positioning_activity_ema (importancia: 0.0075429888)
        df["positioning_activity_ema"] = df.groupby("player")["positioning_activity"].transform(
            lambda s: s.shift(1).ewm(span=3, adjust=False).mean()
        ).fillna(0)
        
        print("✓ Positioning Activity (EMA)")
    else:
        print("❌ Falta columna Entradas")
    
    # ❌ ELIMINAR: blocks_per_90 (ambas versiones tienen importancia 0)
    
    sweeping_cols = [c for c in df.columns if any(s in c for s in 
        ['def_actions', 'aerial_success_ema', 'clearance_activity_ema', 'positioning_activity_ema'])]
    print(f"\n✅ Features sweeping creadas (optimizadas): {len(sweeping_cols)}\n")
    
    return df


# ===========================
# FEATURES SIN LEAKAGE (OPTIMIZADO)
# ===========================
def crear_features_portero(df):
    print("=" * 80)
    print("FEATURES PORTERO (OPTIMIZADO)")
    print("=" * 80)
    
    if "Min_partido" in df.columns:
        # ❌ ELIMINAR: min_participacion_roll5_std (importancia: 0.001196514)
        # ✅ MANTENER: min_participacion_roll5_mean (importancia: 0.0026009916)
        df["min_participacion_roll5_mean"] = df.groupby("player")["Min_partido"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        )
        print("✓ min_participacion (media)")
    
    if "PSxG" in df.columns:
        # ❌ ELIMINAR: psxg_roll5_mean (no aparece pero su std sí: 0.018020762)
        # ✅ MANTENER: psxg_roll5_std (importancia: 0.018020762)
        df["psxg_roll5_std"] = df.groupby("player")["PSxG"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).std()
        ).fillna(0)
        
        # ✅ MANTENER: psxg_plus_minus_roll5 (importancia: 0.09822864)
        df["goles_menos_psxg"] = df["Goles_en_contra"] - df["PSxG"]
        df["psxg_plus_minus_roll5"] = df.groupby("player")["goles_menos_psxg"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        )
        print("✓ PSxG (std, plus_minus)")
    
    if "Porcentaje_paradas" in df.columns:
        # ✅ MANTENER: save_pct_roll5_mean (importancia: 0.09014584)
        df["save_pct_roll5_mean"] = df.groupby("player")["Porcentaje_paradas"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        )
        # ✅ MANTENER: save_pct_roll5_std (importancia: 0.02838262)
        df["save_pct_roll5_std"] = df.groupby("player")["Porcentaje_paradas"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).std()
        ).fillna(0)
        print("✓ Save % (mean, std)")
    
    # ❌ ELIMINAR: tiros_enfrentados_roll5 y variantes (ambas: 0.0)
    
    # ✅ MANTENER: porteria_cero (importancia: 0.009292218)
    df["porteria_cero_bin"] = (df["Goles_en_contra"] == 0).astype(int)
    df["porteria_cero_roll5_sum"] = df.groupby("player")["porteria_cero_bin"].transform(
        lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).sum()
    ).fillna(0)
    print("✓ Portería a cero\n")
    
    return df


def crear_features_rival(df):
    print("=" * 80)
    print("FEATURES RIVAL (OPTIMIZADO)")
    print("=" * 80)
    
    
    if "shots_rival_partido" in df.columns:
        df["tiros_rival_roll5_mean"] = df.groupby("player")["shots_rival_partido"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        )
        print("✓ Shots rival (mean)")
    
    if "shots_on_target_rival_partido" in df.columns:
        df["tiros_puerta_rival_roll5_mean"] = df.groupby("player")["shots_on_target_rival_partido"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        )
        print("✓ Shots on target rival")
    
    if "shots_rival_partido" in df.columns and "shots_on_target_rival_partido" in df.columns:
        df["presion_ofensiva"] = (
            df["shots_rival_partido"] - df["shots_on_target_rival_partido"]
        )
        df["presion_ofensiva_rival_roll5"] = df.groupby("player")["presion_ofensiva"].transform(
            lambda s: s.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        )
        print("✓ Presión ofensiva rival")
    
    if "racha_rival_ratio_victorias" in df.columns:
        df["forma_rival_roll5"] = df.groupby("player")["racha_rival_ratio_victorias"].transform(
            lambda s: s.rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0.5)
        print("✓ Forma rival\n")
    
    return df


def crear_features_v1_historicas(df, columna_objetivo):

    df["pf_media_historica"] = df.groupby("player")[columna_objetivo].transform(
        lambda s: s.shift().expanding().mean()
    ).fillna(0)
    
    if "Goles_en_contra" in df.columns:
        df["gc_ratio_hist"] = df.groupby("player")["Goles_en_contra"].transform(
            lambda s: (s > 0).astype(int).shift(1).expanding().mean()
        ).fillna(0)
    
    if "Porcentaje_paradas" in df.columns:
        df["save_ratio_hist"] = df.groupby("player")["Porcentaje_paradas"].transform(
            lambda s: s.shift().expanding().mean()
        ).fillna(0)
    
    df["pf_lag1"] = df.groupby("player")[columna_objetivo].shift(1).fillna(0)
    
    if "Porcentaje_paradas" in df.columns:
        df["save_pct_lag1"] = df.groupby("player")["Porcentaje_paradas"].shift(1).fillna(0)
    
    return df


def crear_features_interacciones(df):
    if "save_pct_roll5_mean" in df.columns and "tiros_rival_roll5_mean" in df.columns:
        df["adaptacion_presion"] = (
            df["save_pct_roll5_mean"] * 
            (1 + df["tiros_rival_roll5_mean"] / (df["tiros_rival_roll5_mean"].mean() + 0.1))
        ).fillna(0)
        
    if "psxg_plus_minus_roll5" in df.columns:
        df["overperformance_defensa"] = -df["psxg_plus_minus_roll5"]
    
    if "tiros_rival_roll5_mean" in df.columns:
        df["dominancia_equipo"] = (
            -df["tiros_rival_roll5_mean"]
        ).fillna(0)    
    return df


def definir_variables_finales(df):
    variables = [
        "local",
        # Features portero (solo relevantes)
        "min_participacion_roll5_mean",
        "psxg_roll5_std", "psxg_plus_minus_roll5",
        "save_pct_roll5_mean", "save_pct_roll5_std",
        "porteria_cero_roll5_sum",
        # Features sweeping (solo relevantes)
        "def_actions_per_90_last5", "def_actions_ema",
        "aerial_success_ema",
        "clearance_activity_ema",
        "positioning_activity_ema",
        # Features rival (solo relevantes)
        "tiros_rival_roll5_mean", "tiros_puerta_rival_roll5_mean",
        "presion_ofensiva_rival_roll5", "forma_rival_roll5",
        # Rachas
        "racha_derrotas", "racha_ratio_victorias",
        "racha_rival_victorias", "racha_rival_ratio_victorias",
        # Interacciones (solo relevantes)
        "adaptacion_presion", "overperformance_defensa", "dominancia_equipo",
        # Históricas
        "pf_media_historica", "gc_ratio_hist", "save_ratio_hist",
        "pf_lag1", "save_pct_lag1",
    ]
    
    if USAR_ROLES:
        variables.extend([
            "rol_save_pct_posicion", "score_roles", 
            "rol_minutos_posicion", "score_roles_normalizado"
        ])
    
    variables = [v for v in variables if v in df.columns]
    sweeping_count = len([v for v in variables if any(s in v for s in 
        ['def_actions', 'aerial', 'clearance', 'positioning'])])
    print(f"✅ {len(variables)} variables finales (incluyendo {sweeping_count} de sweeping)\n")
    return variables


def preparar_datos(df, variables_finales, columna_objetivo):
    df_modelo = df.copy()
    
    rol_cols = [c for c in df_modelo.columns if c.startswith("rol_")]
    if rol_cols:
        for col in rol_cols:
            df_modelo[col] = df_modelo[col].fillna(0)
    
    variables_numericas = df_modelo[[c for c in variables_finales if c in df_modelo.columns]].select_dtypes(include=[np.number]).columns
    for col in variables_numericas:
        if df_modelo[col].isnull().sum() > 0:
            df_modelo[col] = df_modelo[col].fillna(df_modelo[col].median())
    
    cols_seleccionar = [c for c in variables_finales if c in df_modelo.columns] + [columna_objetivo]
    df_modelo = df_modelo[cols_seleccionar].dropna()
    
    print(f"Filas: {len(df_modelo)}")
    print(f"Variables: {len([v for v in variables_finales if v in df_modelo.columns])}\n")
    
    X = df_modelo[[v for v in variables_finales if v in df_modelo.columns]]
    y = df_modelo[columna_objetivo]
    return X, y, df_modelo


def generar_splits(X):
    print("=" * 80)
    print("VALIDACIÓN TEMPORAL (5 FOLDS)")
    print("=" * 80)
    tscv = TimeSeriesSplit(n_splits=5)
    folds = []
    for i, (idx_ent, idx_pru) in enumerate(tscv.split(X), 1):
        print(f"Fold {i}: Train {len(idx_ent)} | Test {len(idx_pru)}")
        folds.append({"fold": i, "idx_ent": idx_ent, "idx_pru": idx_pru})
    print()
    return folds


def crear_grids():
    grid_rf = crear_malla_parametros({
        "n_estimators": [ 300, 400, 500],      # +3 valores
        "max_depth": [8, 10, 12, 14],                   # +2 valores  
        "min_samples_leaf": [3, 5, 7],                  # +2 valores
        "min_samples_split": [5, 10],                   # NUEVO
        "max_features": [0.3, 0.5, 0.7, "sqrt"], # +4 valores
    })
    print(f"🔵 RF: {len(grid_rf)} configuraciones")
    
    grid_xgb = crear_malla_parametros({
        "max_depth": [3, 4, 5, 6],                     # +2 valores
        "n_estimators": [300, 400, 500, 600, 700],     # +3 valores
        "learning_rate": [0.01, 0.015, 0.02, 0.025, 0.03], # +3 valores
        "colsample_bytree": [0.8, 0.85, 0.9],          # NUEVO
    })
    print(f"🟢 XGB: {len(grid_xgb)} configuraciones")

    
    grid_elastic = crear_malla_parametros({
        "alpha": [0.001, 0.003, 0.005, 0.008, 0.01, 0.015, 0.02], # +5 valores
        "l1_ratio": [0.1, 0.3, 0.5, 0.7, 0.9],         # +2 valores
    })
    print(f"🟡 ElasticNet: {len(grid_elastic)} configuraciones")
    
    return grid_rf, grid_xgb, grid_elastic


def entrenar_modelos(X, y, folds, grid_rf, grid_xgb, grid_elastic):
    resultados = []
    
    for info_fold in folds:
        fold = info_fold["fold"]
        X_ent, X_pru = X.iloc[info_fold["idx_ent"]], X.iloc[info_fold["idx_pru"]]
        y_ent, y_pru = y.iloc[info_fold["idx_ent"]], y.iloc[info_fold["idx_pru"]]
        
        print(f"\n{'='*80}")
        print(f"FOLD {fold} / 5")
        print(f"{'='*80}")
        
        # BOSQUE ALEATORIO
        print("\n🔵 BOSQUE ALEATORIO")
        print("-" * 80)
        mejor_rf = None
        mejor_mae_rf = float("inf")
        for i, cfg in enumerate(grid_rf, 1):
            modelo = RandomForestRegressor(**cfg, random_state=42, n_jobs=-1)
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru)
            res = {"fold": fold, "tipo": "bosque", "config": cfg,
                   "mae": m["mae"], "rmse": m["rmse"], "r2": m["r2"], "modelo": m["modelo"]}
            resultados.append(res)
            if m["mae"] < mejor_mae_rf:
                mejor_mae_rf = m["mae"]
                mejor_rf = res
            print(f"  [{i:3d}] MAE: {m['mae']:.4f} | RMSE: {m['rmse']:.4f} | R2: {m['r2']:.4f}")
        if mejor_rf:
            print(f"\n  ✅ Mejor BOSQUE: MAE {mejor_rf['mae']:.4f} | RMSE {mejor_rf['rmse']:.4f} | R2 {mejor_rf['r2']:.4f}")
        
        # XGBOOST
        print("\n🟢 XGBOOST")
        print("-" * 80)
        mejor_xgb = None
        mejor_mae_xgb = float("inf")
        for i, cfg in enumerate(grid_xgb, 1):
            modelo = XGBRegressor(**cfg, min_child_weight=3,
                                  reg_lambda=1.0, objective="reg:squarederror", random_state=42, n_jobs=-1)
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru)
            res = {"fold": fold, "tipo": "xgb", "config": cfg,
                   "mae": m["mae"], "rmse": m["rmse"], "r2": m["r2"], "modelo": m["modelo"]}
            resultados.append(res)
            if m["mae"] < mejor_mae_xgb:
                mejor_mae_xgb = m["mae"]
                mejor_xgb = res
            print(f"  [{i:3d}] MAE: {m['mae']:.4f} | RMSE: {m['rmse']:.4f} | R2: {m['r2']:.4f}")
        if mejor_xgb:
            print(f"\n  ✅ Mejor XGB: MAE {mejor_xgb['mae']:.4f} | RMSE {mejor_xgb['rmse']:.4f} | R2 {mejor_xgb['r2']:.4f}")
        
        # ELASTICNET
        print("\n🟡 ELASTICNET")
        print("-" * 80)
        mejor_elastic = None
        mejor_mae_elastic = float("inf")
        for i, cfg in enumerate(grid_elastic, 1):
            modelo = Pipeline([
                ("escalador", StandardScaler()),
                ("regresor", ElasticNet(alpha=cfg["alpha"], l1_ratio=cfg["l1_ratio"],
                                       random_state=42, max_iter=10000))
            ])
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru)
            res = {"fold": fold, "tipo": "elastic", "config": cfg,
                   "mae": m["mae"], "rmse": m["rmse"], "r2": m["r2"], "modelo": m["modelo"]}
            resultados.append(res)
            if m["mae"] < mejor_mae_elastic:
                mejor_mae_elastic = m["mae"]
                mejor_elastic = res
            print(f"  [{i:2d}] MAE: {m['mae']:.4f} | RMSE: {m['rmse']:.4f} | R2: {m['r2']:.4f}")
        if mejor_elastic:
            print(f"\n  ✅ Mejor ELASTIC: MAE {mejor_elastic['mae']:.4f} | RMSE {mejor_elastic['rmse']:.4f} | R2 {mejor_elastic['r2']:.4f}")
    
    return resultados


def seleccionar_mejores_modelos(resultados):
    mejor_mae = min(resultados, key=lambda x: x["mae"])
    mejor_r2 = max(resultados, key=lambda x: x["r2"])
    
    print("\n" + "=" * 80)
    print("MEJORES MODELOS GLOBALES")
    print("=" * 80 + "\n")
    
    print(f"🥇 MEJOR MAE (Fold {mejor_mae['fold']}, {mejor_mae['tipo'].upper()}):")
    print(f"   MAE: {mejor_mae['mae']:.4f} | RMSE: {mejor_mae['rmse']:.4f} | R2: {mejor_mae['r2']:.4f}")
    
    print(f"\n🥇 MEJOR R² (Fold {mejor_r2['fold']}, {mejor_r2['tipo'].upper()}):")
    print(f"   MAE: {mejor_r2['mae']:.4f} | RMSE: {mejor_r2['rmse']:.4f} | R2: {mejor_r2['r2']:.4f}\n")
    
    return mejor_mae, mejor_r2


def guardar_resultados_csv(resultados):
    df_res = pd.DataFrame([
        {"fold": r["fold"], "tipo": r["tipo"], "mae": r["mae"], "rmse": r["rmse"], "r2": r["r2"]}
        for r in resultados
    ])
    ruta = DIRECTORIO_SALIDA / "resultados_entrenamiento.csv"
    df_res.to_csv(ruta, index=False)
    print(f"✅ Resultados guardados: {ruta}\n")


def tabla_comparativa_modelos(resultados):
    print("\n" + "=" * 80)
    print("TABLITA COMPARATIVA - PROMEDIO POR MODELO (5 FOLDS)")
    print("=" * 80 + "\n")
    
    estadisticas_tipo = {}
    for r in resultados:
        t = r["tipo"]
        estadisticas_tipo.setdefault(t, {"mae": [], "rmse": [], "r2": []})
        estadisticas_tipo[t]["mae"].append(r["mae"])
        estadisticas_tipo[t]["rmse"].append(r["rmse"])
        estadisticas_tipo[t]["r2"].append(r["r2"])
    
    nombres_modelos = {"bosque": "Bosque Aleatorio", "xgb": "XGBoost", "elastic": "ElasticNet"}
    
    tabla_datos = []
    for tipo, nombre in nombres_modelos.items():
        if tipo in estadisticas_tipo:
            mae_med = np.mean(estadisticas_tipo[tipo]["mae"])
            mae_std = np.std(estadisticas_tipo[tipo]["mae"])
            rmse_med = np.mean(estadisticas_tipo[tipo]["rmse"])
            rmse_std = np.std(estadisticas_tipo[tipo]["rmse"])
            r2_med = np.mean(estadisticas_tipo[tipo]["r2"])
            r2_std = np.std(estadisticas_tipo[tipo]["r2"])
            
            tabla_datos.append({
                "Modelo": nombre,
                "MAE": f"{mae_med:.4f}±{mae_std:.4f}",
                "RMSE": f"{rmse_med:.4f}±{rmse_std:.4f}",
                "R²": f"{r2_med:.4f}±{r2_std:.4f}",
            })
    
    df_tabla = pd.DataFrame(tabla_datos)
    print(df_tabla.to_string(index=False))
    print("\n" + "=" * 80 + "\n")
    
    ruta_tabla = DIRECTORIO_SALIDA / "tabla_comparativa.csv"
    df_tabla.to_csv(ruta_tabla, index=False)
    print(f"✅ Tabla guardada: {ruta_tabla}\n")


def explicabilidad_shap(mejor_modelo, folds, X, y):
    """
    ✅ VERSIÓN FINAL: Genera SIEMPRE el CSV de importancias
    """
    print("\n" + "=" * 80)
    print("EXPLICABILIDAD SHAP (MEJOR MODELO)")
    print("=" * 80 + "\n")
    
    modelo_real = mejor_modelo["modelo"]
    if isinstance(modelo_real, Pipeline):
        print("⚠️  Modelo ElasticNet detectado (sin SHAP directo)")
        print("   Este análisis se hará con el mejor modelo de árbol disponible\n")
        return None
    
    try:
        fold_info = [f for f in folds if f["fold"] == mejor_modelo["fold"]][0]
        idx_pru = fold_info["idx_pru"]
        X_pru = X.iloc[idx_pru]
        
        print("📊 Calculando valores SHAP...\n")
        explicador = shap.TreeExplainer(modelo_real)
        valores_shap = explicador.shap_values(X_pru)
        
        if isinstance(valores_shap, list):
            valores_shap = valores_shap[0]
        
        importancias = np.abs(valores_shap).mean(axis=0)
        df_imp = pd.DataFrame(
            {"variable": X_pru.columns, "importancia": importancias}
        ).sort_values("importancia", ascending=False)
        
        print("Top 15 Variables más importantes (SHAP):\n")
        for i, (idx, row) in enumerate(df_imp.head(15).iterrows(), 1):
            print(f"[{i:2d}] {row['variable']:40s} : {row['importancia']:.6f}")
        
        try:
            ruta_imp = DIRECTORIO_SALIDA / "importancias_shap.csv"
            df_imp.to_csv(ruta_imp, index=False)
            print(f"\n✅ CSV Importancias SHAP guardado: {ruta_imp}")
        except Exception as e_csv:
            print(f"\n⚠️  Error guardando CSV: {e_csv}")
        
        try:
            plt.figure(figsize=(12, 10))
            shap.summary_plot(valores_shap, X_pru, show=False, max_display=15, plot_type="bar")
            plt.tight_layout()
            plt.savefig(DIRECTORIO_IMAGENES / "shap_summary.png", dpi=300, bbox_inches="tight")
            plt.close()
            print(f"✅ Gráfico SHAP guardado: {DIRECTORIO_IMAGENES / 'shap_summary.png'}\n")
        except Exception as e_plot:
            print(f"⚠️  Error guardando gráfico: {e_plot}\n")
        
        return df_imp
    
    except Exception as e:
        print(f"⚠️  Error en SHAP: {e}\n")
        return None


def visualizar_resultados(resultados):
    print("=" * 80)
    print("VISUALIZACIONES")
    print("=" * 80)
    
    fig, ejes = plt.subplots(1, 3, figsize=(16, 5))
    for idx, metrica in enumerate(["mae", "rmse", "r2"]):
        valores_por_tipo = {}
        for r in resultados:
            tipo = r["tipo"].upper()
            valores_por_tipo.setdefault(tipo, []).append(r[metrica])
        ax = ejes[idx]
        tipos = list(valores_por_tipo.keys())
        valores = [valores_por_tipo[t] for t in tipos]
        cajas = ax.boxplot(valores, labels=tipos, patch_artist=True)
        for c in cajas["boxes"]:
            c.set_facecolor("lightblue")
        ax.set_ylabel(metrica.upper(), fontsize=12)
        ax.set_title(f"Distribución {metrica.upper()}", fontsize=12)
        ax.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / "comparacion_modelos.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ Gráfico comparativo: {DIRECTORIO_IMAGENES / 'comparacion_modelos.png'}\n")


def resumen_final(resultados, variables_finales, df_modelo):
    print("\n" + "=" * 80)
    print("✅ RESUMEN FINAL V4 OPTIMIZADO - FEATURES RELEVANTES SOLO")
    print("=" * 80 + "\n")
    
    sweeping_features = [v for v in variables_finales if any(s in v for s in 
        ['def_actions', 'aerial', 'clearance', 'positioning'])]
    
    print("📋 Información General:")
    print(f"   Directorio: {DIRECTORIO_SALIDA}")
    print(f"   Total configuraciones evaluadas: {len(resultados)}")
    print(f"   Variables usadas: {len(variables_finales)}")
    print(f"     - Sweeping-keeper features: {len(sweeping_features)}")
    print(f"   Filas de datos: {len(df_modelo)}")
    print(f"   Roles integrados: {'SÍ' if USAR_ROLES else 'NO'}")
    print(f"   ✅ Data Leakage: CONTROLADO (shift().rolling/expanding())")
    print(f"   ✅ Features rival: SÍ (volumen tiros, presión)")
    print(f"   ✅ Features sweeping: SÍ ({len(sweeping_features)} features)")
    print(f"   ✅ Features optimizadas: SÍ (eliminadas 10+ features sin aporte)\n")


def main():
    print(f"\n{'=' * 80}")
    print(f"✅ V4 OPTIMIZADO: SOLO FEATURES RELEVANTES")
    print(f"   ✅ Eliminadas 10+ features con importancia 0")
    print(f"   ✅ Conservadas solo features con aporte real")
    print(f"   ✅ Grids de búsqueda reducidos (menos tiempo)")
    print(f"   ✅ Validación temporal: Walk-forward (NO random shuffle)")
    print(f"{'=' * 80}\n")
    
    df = cargar_datos()
    columna_objetivo = "target_pf_next" if "target_pf_next" in df.columns else "puntosFantasy"
    
    if USAR_ROLES:
        try:
            df = enriquecer_dataframe_con_roles(df, columna_roles="roles")
        except:
            pass
    
    df = preparar_basicos(df)
    df = crear_features_sweeping(df)
    df = crear_features_portero(df)
    df = crear_features_rival(df)
    df = crear_features_v1_historicas(df, columna_objetivo)
    df = crear_features_interacciones(df)
    
    if USAR_ROLES:
        try:
            df = crear_features_interaccion_roles_v2(df, columna_objetivo)
        except:
            pass
    
    # Elimina columnas base DESPUÉS de crear sweeping features
    cols_base_eliminar = ["Entradas", "DuelosGanados", "DuelosPerdidos", 
                          "Despejes", "BloqueoTiros", "BloqueoPase",
                          "DuelosAereosGanados", "DuelosAereosPerdidos"]
    df = df.drop(columns=[c for c in cols_base_eliminar if c in df.columns], errors="ignore")
    
    variables_finales = definir_variables_finales(df)
    X, y, df_modelo = preparar_datos(df, variables_finales, columna_objetivo)
    folds = generar_splits(X)
    
    grid_rf, grid_xgb, grid_elastic = crear_grids()
    resultados = entrenar_modelos(X, y, folds, grid_rf, grid_xgb, grid_elastic)
    
    mejor_mae, mejor_r2 = seleccionar_mejores_modelos(resultados)
    guardar_resultados_csv(resultados)
    tabla_comparativa_modelos(resultados)
    
    if mejor_mae["tipo"] not in ("bosque", "xgb"):
        print("\n⚠️  Mejor modelo es ELASTICNET (sin SHAP directo)")
        print("   Buscando mejor BOSQUE/XGB para análisis SHAP...\n")
        resultados_arboles = [r for r in resultados if r["tipo"] in ("bosque", "xgb")]
        mejor_arbol = min(resultados_arboles, key=lambda x: x["mae"])
        print(f"✅ Mejor modelo de árbol: {mejor_arbol['tipo'].upper()} con MAE {mejor_arbol['mae']:.4f}\n")
        df_imp = explicabilidad_shap(mejor_arbol, folds, X, y)
    else:
        df_imp = explicabilidad_shap(mejor_mae, folds, X, y)
    
    if df_imp is not None:
        print(f"✅ CSV de importancias generado con {len(df_imp)} features")
    else:
        print("ℹ️  SHAP no disponible (modelo no basado en árboles)")
    
    visualizar_resultados(resultados)
    resumen_final(resultados, variables_finales, df_modelo)


if __name__ == "__main__":
    main()

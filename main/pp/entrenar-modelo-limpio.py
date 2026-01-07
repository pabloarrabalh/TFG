"""
ENTRENAR MODELO LIMPIO - SIN DATA LEAKAGE
Solo features disponibles ANTES del partido
"""

import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from itertools import product

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from xgboost import XGBRegressor

# Carpeta de salida para modelos
output_dir = Path("modelos")
output_dir.mkdir(exist_ok=True)

print("Número de porteros:")
df_check = pd.read_csv("players_with_features_exp3_CORREGIDO.csv")
df_pt_check = df_check[df_check["posicion"] == "PT"]
print(len(df_pt_check))

print("\n" + "="*80)
print("ENTRENANDO MODELOS LIMPIOS - SOLO PORTEROS - SIN DATA LEAKAGE")
print("="*80 + "\n")

# ============================================================
# CARGAR DATOS (SOLO PORTEROS)
# ============================================================

search_paths = [
    Path.cwd(),
    Path.cwd() / "main" / "pp",
    Path.cwd() / "main",
    Path.cwd() / "data" / "temporada_25_26",
    Path.cwd() / "data",
    Path.cwd().parent,
    Path.cwd().parent / "main" / "pp",
]

csv_path = None
for path in search_paths:
    full_path = path / "players_with_features_exp3_CORREGIDO.csv"
    if full_path.exists():
        csv_path = str(full_path)
        break

if not csv_path:
    print("❌ No se encontró players_with_features_exp3_CORREGIDO.csv")
    exit(1)

print(f"📂 Cargando solo porteros desde: {csv_path}")
df = pd.read_csv(csv_path)
df = df[df["posicion"] == "PT"].copy()
print(f"✅ Cargado: {df.shape[0]} filas de porteros, {df.shape[1]} columnas\n")

# ============================================================
# DEFINICIÓN DE FEATURES POR VENTANA
# ============================================================

features_comunes = [
    # Contexto partido / apuestas
    "local",
    "posicion_equipo",
    "posicion_rival",
    "p_home",
    "p_draw",
    "p_away",
    "p_win_propio",
    "p_loss_propio",
    "p_draw_match",

    # Fuerza relativa clasificación
    "pts_diff",
    "is_top4_propio",
    "is_top4_rival",
    "is_bottom3_rival",

    # Features “mixtas” portero x rival
    "ratio_paradas_dificiles",
    "xg_rival_x_savepct",
    "xg_rival_x_gc_per90",
    "gf_rival_last5_x_gc_per90",
    "goal_diff_rival_x_pf_var",

    # Roles / calidad portero
    "score_porterias_cero",
    "score_save_pct",
    "rol_x_xg_rival",
    "elite_keeper",
    "is_top5_porterias_cero",
    "is_top5_save_pct",
    "score_pc_boost",
    "score_sp_boost",
    "rol_x_xg_rival_boost",
    "ataque_top_rival_x_elite",
    "is_top5_en_algo",
]

features_window5 = [
    # Racha fantasy portero
    "pf_last5_mean",
    "gc_last5_std",
    "psxg_last5_std",
    "savepct_last5_mean",
    "clean_last5_ratio",
    "titular_last5_ratio",
    "psxg_gc_diff_last5_mean",
    "form_vs_class_keeper",
    "saves_last5_mean",
    "psxg_per90_last5",
    "gc_per90_last5",

    # Racha equipo propio
    "goal_diff_last5_team",

    # Racha rival
    "goal_diff_last5_rival",
    "xg_last5_mean_rival",
    "shots_on_target_ratio_rival",
]

features_window3 = [
    "pf_last3_mean",
    "gc_last3_std",
    "psxg_last3_std",
    "savepct_last3_mean",
    "clean_last3_ratio",
    "titular_last3_ratio",
    "psxg_gc_diff_last3_mean",
    "form_vs_class_keeper_3",
    "saves_last3_mean",
    "psxg_per90_last3",
    "gc_per90_last3",

    "goal_diff_last3_team",

    "goal_diff_last3_rival",
    "xg_last3_mean_rival",
    "shots_on_target_ratio_rival_last3",
]

features_window8 = [
    "pf_last8_mean",
    "gc_last8_std",
    "psxg_last8_std",
    "savepct_last8_mean",
    "clean_last8_ratio",
    "titular_last8_ratio",
    "psxg_gc_diff_last8_mean",
    "form_vs_class_keeper_8",
    "saves_last8_mean",
    "psxg_per90_last8",
    "gc_per90_last8",

    "goal_diff_last8_team",

    "goal_diff_last8_rival",
    "xg_last8_mean_rival",
    "shots_on_target_ratio_rival_last8",
]

def get_features_for_window(window: int):
    if window == 3:
        base_window_feats = features_window3
    elif window == 8:
        base_window_feats = features_window8
    else:
        base_window_feats = features_window5
    return features_comunes + base_window_feats

# ============================================================
# DEFINICIÓN DE GRIDS (COMÚN A TODAS LAS VENTANAS)
# ============================================================

n_estimators_list = [200, 400, 800]
max_depth_list = [6, 8, 10, 12]
min_samples_leaf_list = [5, 10, 20]
max_features_list = [0.3, 0.4, 0.5]

rf_configs = []
for n_est, depth, leaf, mf in product(
    n_estimators_list,
    max_depth_list,
    min_samples_leaf_list,
    max_features_list
):
    name = f"rf_ne{n_est}_d{depth}_l{leaf}_mf{int(mf*10)}"
    rf_configs.append({
        "name": name,
        "n_estimators": n_est,
        "max_depth": depth,
        "min_samples_leaf": leaf,
        "max_features": mf,
    })

xgb_depth_list = [2, 3, 4, 5]
xgb_n_estimators_list = [400, 800, 1200]
xgb_lr_list = [0.015, 0.025, 0.04]

xgb_configs = []
for depth, n_est, lr in product(
    xgb_depth_list,
    xgb_n_estimators_list,
    xgb_lr_list
):
    name = f"xgb_d{depth}_ne{n_est}_lr{int(lr*1000)}"
    xgb_configs.append({
        "name": name,
        "max_depth": depth,
        "n_estimators": n_est,
        "learning_rate": lr,
    })

# ============================================================
# BUCLE POR VENTANA (3,5,8) + ENTRENAMIENTO RF/XGB
# ============================================================

resultados_mae = []
resultados_r2 = []

for window in [3, 5, 8]:
    print("\n" + "="*80)
    print(f"ENTRENANDO PARA VENTANA {window} PARTIDOS")
    print("="*80)

    # Features según ventana
    features_validas = get_features_for_window(window)
    features_disponibles = [f for f in features_validas if f in df.columns]
    print(f"✅ Features válidas ventana {window}: {len(features_disponibles)}")

    # ============================================================
    # PREPARAR DATOS
    # ============================================================

    df_filtrado = df[features_disponibles + ["puntosFantasy"]].dropna()
    print(f"   Filas sin NaN (ventana {window}): {len(df_filtrado)}")

    if len(df_filtrado) < 100:
        print(f"❌ Muy pocas filas para ventana {window}, se omite.")
        continue

    X = df_filtrado[features_disponibles].copy()
    y = df_filtrado["puntosFantasy"].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42
    )

    print(f"   X_train: {X_train.shape}")
    print(f"   X_test:  {X_test.shape}\n")

    # ============================================================
    # RF BASE (POR VENTANA)
    # ============================================================

    print(f"⏳ Entrenando RF_base ventana {window}...")
    modelo_limpio = RandomForestRegressor(
        n_estimators=300,
        max_features=0.5,
        max_depth=8,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1
    )
    modelo_limpio.fit(X_train, y_train)

    y_pred_test_base = modelo_limpio.predict(X_test)
    mae_test_base = mean_absolute_error(y_test, np.round(y_pred_test_base))
    r2_test_base = r2_score(y_test, y_pred_test_base)

    print(f"[ventana {window}] RF_base MAE: {mae_test_base:.4f} | R2: {r2_test_base:.4f}")

    # ============================================================
    # LOG DE IMPORTANCIAS RF (POR VENTANA)
    # ============================================================

    log_path = f"rf_feature_importances_porteros_win{window}.txt"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"RandomForest feature importances por configuración (porteros) - ventana {window}\n\n")

    # ============================================================
    # GRID RANDOM FOREST (POR VENTANA)
    # ============================================================

    mejor_rf_grid = None
    mejor_mae_rf_grid = np.inf

    for cfg in rf_configs:
        name_win = f"win{window}_" + cfg["name"]
        print(f"\n⏳ Entrenando {name_win} (RandomForest, PT)...")
        modelo_rf = RandomForestRegressor(
            n_estimators=cfg["n_estimators"],
            max_depth=cfg["max_depth"],
            min_samples_leaf=cfg["min_samples_leaf"],
            max_features=cfg["max_features"],
            random_state=42,
            n_jobs=-1,
        )
        modelo_rf.fit(X_train, y_train)
        y_pred_test_rf = modelo_rf.predict(X_test)
        y_pred_test_rf_round = np.round(y_pred_test_rf)

        mae_test_rf = mean_absolute_error(y_test, y_pred_test_rf_round)
        r2_test_rf = r2_score(y_test, y_pred_test_rf)

        print(f"[ventana {window}] MAE Test {name_win}: {mae_test_rf:.4f} | R2: {r2_test_rf:.4f}")

        resultados_mae.append({
            "name": name_win,
            "mae": mae_test_rf,
            "r2": r2_test_rf,
            "model": modelo_rf,
            "tipo": "rf",
            "window": window,
        })
        resultados_r2.append({
            "name": name_win,
            "mae": mae_test_rf,
            "r2": r2_test_rf,
            "model": modelo_rf,
            "tipo": "rf",
            "window": window,
        })

        importancias = modelo_rf.feature_importances_
        ranking = sorted(
            zip(importancias, features_disponibles),
            reverse=True
        )

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"Modelo: {name_win}\n")
            f.write(
                f"  n_estimators={cfg['n_estimators']}, "
                f"max_depth={cfg['max_depth']}, "
                f"min_samples_leaf={cfg['min_samples_leaf']}, "
                f"max_features={cfg['max_features']}\n"
            )
            f.write(f"  MAE_test={mae_test_rf:.4f}  R2_test={r2_test_rf:.4f}\n")
            f.write("  Top 10 features:\n")
            for imp, name in ranking[:10]:
                f.write(f"    {name}: {imp:.4f}\n")
            f.write("\n")

        if mae_test_rf < mejor_mae_rf_grid:
            mejor_mae_rf_grid = mae_test_rf
            mejor_rf_grid = modelo_rf

    # ============================================================
    # GRID XGBOOST (POR VENTANA)
    # ============================================================

    mejor_xgb = None
    mejor_mae_xgb = np.inf

    print("\n" + "-"*80)
    print(f"GRID XGBOOST (PORTEROS) - VENTANA {window}")
    print("-"*80)

    for cfg in xgb_configs:
        name_win = f"win{window}_" + cfg["name"]
        print(f"\n⏳ Entrenando {name_win} (XGBoost, PT)...")
        modelo_xgb = XGBRegressor(
            n_estimators=cfg["n_estimators"],
            learning_rate=cfg["learning_rate"],
            max_depth=cfg["max_depth"],
            subsample=0.9,
            colsample_bytree=0.9,
            min_child_weight=3,
            gamma=0.0,
            reg_lambda=1.0,
            reg_alpha=0.0,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1
        )
        modelo_xgb.fit(X_train, y_train)
        y_pred_test_xgb = modelo_xgb.predict(X_test)
        y_pred_test_xgb_round = np.round(y_pred_test_xgb)

        mae_test_xgb = mean_absolute_error(y_test, y_pred_test_xgb_round)
        r2_test_xgb = r2_score(y_test, y_pred_test_xgb)

        print(f"[ventana {window}] MAE Test {name_win}: {mae_test_xgb:.4f} | R2: {r2_test_xgb:.4f}")

        resultados_mae.append({
            "name": name_win,
            "mae": mae_test_xgb,
            "r2": r2_test_xgb,
            "model": modelo_xgb,
            "tipo": "xgb",
            "window": window,
        })
        resultados_r2.append({
            "name": name_win,
            "mae": mae_test_xgb,
            "r2": r2_test_xgb,
            "model": modelo_xgb,
            "tipo": "xgb",
            "window": window,
        })

        if mae_test_xgb < mejor_mae_xgb:
            mejor_mae_xgb = mae_test_xgb
            mejor_xgb = modelo_xgb

# ============================================================
# COMPARATIVA FINAL GLOBAL (PORTEROS)
# ============================================================

print("\n" + "="*80)
print("RESULTADOS MEJORES MODELOS (PORTEROS) - GLOBAL (VENTANAS 3,5,8)")
print("="*80)

# Top 3 por MAE (global)
top3_mae = sorted(resultados_mae, key=lambda d: d["mae"])[:3]

print("\nTop 3 modelos globales por MAE:")
for res in top3_mae:
    print(f"- win{res['window']} {res['tipo'].upper()} {res['name']}: MAE={res['mae']:.4f}, R2={res['r2']:.4f}")
    filename = output_dir / f"best_mae_win{res['window']}_{res['tipo']}_{res['name']}_mae{res['mae']:.4f}_r2{res['r2']:.4f}.pkl"
    with open(filename, "wb") as f:
        pickle.dump(res["model"], f)

# Top 3 por R2 (global)
top3_r2 = sorted(resultados_r2, key=lambda d: d["r2"], reverse=True)[:3]

print("\nTop 3 modelos globales por R2:")
for res in top3_r2:
    print(f"- win{res['window']} {res['tipo'].upper()} {res['name']}: MAE={res['mae']:.4f}, R2={res['r2']:.4f}")
    filename = output_dir / f"best_r2_win{res['window']}_{res['tipo']}_{res['name']}_mae{res['mae']:.4f}_r2{res['r2']:.4f}.pkl"
    with open(filename, "wb") as f:
        pickle.dump(res["model"], f)

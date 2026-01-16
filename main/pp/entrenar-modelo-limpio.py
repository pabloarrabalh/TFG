"""
ENTRENAR MODELO LIMPIO - SIN DATA LEAKAGE
Solo features disponibles ANTES del partido
"""

import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from itertools import product
from sklearn.linear_model import ElasticNet
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    r2_score,
    root_mean_squared_error,
)
from xgboost import XGBRegressor
import shap
import matplotlib.pyplot as plt


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
# ORDEN TEMPORAL + PF_MEDIA_HISTORICA (SIN LEAKAGE)
# ============================================================

sort_cols = []
for c in ["temporada", "jornada", "fecha_partido"]:
    if c in df.columns:
        sort_cols.append(c)

df = df.sort_values(sort_cols).reset_index(drop=True)

if "puntosFantasy" in df.columns:
    df["pf_media_historica"] = (
        df.groupby("player")["puntosFantasy"]
          .transform(lambda s: s.shift().expanding().mean())
    )
else:
    df["pf_media_historica"] = np.nan


# =========================
# FEATURES EXTRA PORTEROS
# =========================

df["bombardeo_partido"] = (
    df["shots_on_target_rival_partido"].clip(lower=0) *
    (1 - df["Goles_en_contra"].clip(lower=0))
)

df["saves_partido"] = (
    df["shots_on_target_rival_partido"].clip(lower=0) -
    df["Goles_en_contra"].clip(lower=0)
).clip(lower=0)

df["paradas_partido"] = df["saves_partido"]

df["shots_on_target_hist_raw"] = (
    df.groupby("player")["shots_on_target_rival_partido"]
      .transform(lambda s: s.shift().expanding().sum())
)

df["paradas_hist_raw"] = (
    df.groupby("player")["paradas_partido"]
      .transform(lambda s: s.shift().expanding().sum())
)

# savepct_hist rolling 5
df["shots_on_target_hist"] = (
    df.groupby("player")["shots_on_target_rival_partido"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).sum())
)

df["paradas_hist"] = (
    df.groupby("player")["paradas_partido"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).sum())
)

df["savepct_hist"] = np.where(
    df["shots_on_target_hist"] > 0,
    df["paradas_hist"] / df["shots_on_target_hist"],
    np.nan
)

df["clean_sheet_flag"] = (df["Goles_en_contra"] == 0).astype(int)


def rolling_feat(col, window, agg, new_name):
    df[new_name] = (
        df.groupby("player")[col]
          .transform(lambda s: getattr(s.shift().rolling(window, min_periods=1), agg)())
    )

rolling_feat("bombardeo_partido", 3, "mean", "bombardeo_last3_mean")
rolling_feat("bombardeo_partido", 5, "mean", "bombardeo_last5_mean")

rolling_feat("saves_partido", 3, "mean", "saves_last3_mean_extra")
rolling_feat("saves_partido", 5, "mean", "saves_last5_mean_extra")

rolling_feat("clean_sheet_flag", 3, "mean", "clean_last3_ratio_extra")
rolling_feat("clean_sheet_flag", 5, "mean", "clean_last5_ratio_extra")

df["partido_muy_desequilibrado"] = (df["ah_line_match"].abs() >= 1.5).astype(int)


# =========================
# FEATURES AVANZADAS PORTERO X RIVAL
# =========================

df["goles_ev_prt"] = (df["PSxG"] - df["Goles_en_contra"]).clip(lower=0)
df["ratio_paradas_dificiles"] = np.where(
    df["shots_on_target_rival_partido"] > 0,
    df["goles_ev_prt"] / df["shots_on_target_rival_partido"],
    0
)

df["xg_rival_x_savepct"] = df["xg_last5_mean_rival"] * df["savepct_hist"]
df["gf_rival_last5_x_gc_per90"] = df["gf_last5_mean_rival"] * df["gc_per90_last5"]


# =========================
# ROLES / CALIDAD PORTERO
# =========================

df["score_porterias_cero"] = (1 - df["gc_per90_last5"]).clip(lower=0)
df["score_save_pct"] = df["savepct_hist"]

q_pc = df["score_porterias_cero"].quantile(0.6)
q_sp = df["score_save_pct"].quantile(0.6)

df["elite_keeper"] = (
    (df["score_porterias_cero"] >= q_pc) &
    (df["score_save_pct"] >= q_sp)
).astype(int)

df["is_top5_porterias_cero"] = (df["score_porterias_cero"] >= q_pc).astype(int)
df["is_top5_save_pct"] = (df["score_save_pct"] >= q_sp).astype(int)
df["is_top5_en_algo"] = (
    (df["is_top5_porterias_cero"] == 1) |
    (df["is_top5_save_pct"] == 1)
).astype(int)

df["score_pc_boost"] = df["score_porterias_cero"] * (df["ataque_top_rival"].fillna(0) + 1)
df["score_sp_boost"] = df["score_save_pct"] * (df["ataque_top_rival"].fillna(0) + 1)

df["rol_x_xg_rival"] = (
    df[["score_porterias_cero", "score_save_pct"]].mean(axis=1) *
    df["xg_last5_mean_rival"]
)
df["rol_x_xg_rival_boost"] = df["rol_x_xg_rival"] * (df["ataque_top_rival"].fillna(0) + 1)

df["ataque_top_rival_x_elite"] = df["ataque_top_rival"].fillna(0) * df["elite_keeper"]


# =========================
# RACHAS PORTERO (3 PARTIDOS) SIN LEAKAGE
# =========================

df["pf_last3_mean"] = (
    df.groupby("player")["puntosFantasy"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

df["savepct_last3_mean"] = (
    df.groupby("player")["savepct_hist"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

df["clean_last3_ratio"] = (
    df.groupby("player")["clean_sheet_flag"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

df["es_titular_partido"] = (df["Min_partido"] > 0).astype(int)
df["titular_last3_ratio"] = (
    df.groupby("player")["es_titular_partido"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

df["psxg_gc_diff"] = df["PSxG"] - df["Goles_en_contra"]
df["psxg_gc_diff_last3_mean"] = (
    df.groupby("player")["psxg_gc_diff"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

df["saves_last3_mean"] = (
    df.groupby("player")["saves_partido"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

df["form_vs_class_keeper_3"] = df["pf_last3_mean"] - df["pf_media_historica"]


# =========================
# RACHAS PORTERO (5 PARTIDOS) SIN LEAKAGE
# =========================

df["pf_last5_mean"] = (
    df.groupby("player")["puntosFantasy"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["savepct_last5_mean"] = (
    df.groupby("player")["savepct_hist"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["clean_last5_ratio"] = (
    df.groupby("player")["clean_sheet_flag"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["titular_last5_ratio"] = (
    df.groupby("player")["es_titular_partido"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["psxg_gc_diff_last5_mean"] = (
    df.groupby("player")["psxg_gc_diff"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["saves_last5_mean"] = (
    df.groupby("player")["saves_partido"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["form_vs_class_keeper"] = df["pf_last5_mean"] - df["pf_media_historica"]


# ==============================================================================
# NUEVAS FEATURES DERIVADAS (3 Y 5 PARTIDOS)
# ==============================================================================

# 1. Calidad media del tiro del rival (xG por disparo) last5
df["rival_xg_per_shot_last5"] = np.where(
    df["shots_last5_mean_rival"] > 0,
    df["xg_last5_mean_rival"] / df["shots_last5_mean_rival"],
    0
)

# 1b. Versión last3 coherente con tus columnas last3
df["rival_xg_per_shot_last3"] = np.where(
    df["shots_last3_mean_rival"] > 0,
    df["xg_last3_mean_rival"] / df["shots_last3_mean_rival"],
    0
)

# 2. Puntería del Rival (ratio tiros a puerta) last5
df["rival_sot_ratio_last5"] = np.where(
    df["shots_last5_mean_rival"] > 0,
    df["shots_on_target_last5_mean_rival"] / df["shots_last5_mean_rival"],
    0
)

# 2b. Versión last3
df["rival_sot_ratio_last3"] = np.where(
    df["shots_last3_mean_rival"] > 0,
    df["shots_on_target_last3_mean_rival"] / df["shots_last3_mean_rival"],
    0
)

# 3. Forma REAL del portero (goles evitados) rolling last5 y last3
df["goles_evitados_partido"] = df["PSxG"] - df["Goles_en_contra"]

df["form_goles_evitados_last5"] = (
    df.groupby("player")["goles_evitados_partido"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["form_goles_evitados_last3"] = (
    df.groupby("player")["goles_evitados_partido"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

# 4. Potencial de puntos por paradas (last5 y last3)
df["save_pct_rolling5"] = (
    df.groupby("player")["Porcentaje_paradas"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["save_pct_rolling3"] = (
    df.groupby("player")["Porcentaje_paradas"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

df["potencial_paradas_match_last5"] = (
    df["shots_on_target_last5_mean_rival"] * df["save_pct_rolling5"]
)

df["potencial_paradas_match_last3"] = (
    df["shots_on_target_last3_mean_rival"] * df["save_pct_rolling3"]
)

# 5. Dominio aéreo last5 y last3
df["dominio_aereo_last5"] = (
    df.groupby("player")["DuelosAereosGanadosPct"]
      .transform(lambda s: s.shift().rolling(5, min_periods=1).mean())
)

df["dominio_aereo_last3"] = (
    df.groupby("player")["DuelosAereosGanadosPct"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

# 6. Riesgo de goleada (xG contra propio x xG rival) last5 y last3
df["riesgo_goleada_last5"] = (
    df["xg_contra_last5_mean_team"] * df["xg_last5_mean_rival"]
)

df["riesgo_goleada_last3"] = (
    df["xg_contra_last3_mean_team"] * df["xg_last3_mean_rival"]
)


# --- Ajuste apuestas: balancear win/loss ---

df["p_loss_soft"] = np.sqrt(df["p_loss_propio"].clip(0, 1))

if "p_win_propio" in df.columns:
    df["p_win_minus_loss"] = (
        df["p_win_propio"].clip(0, 1) - df["p_loss_propio"].clip(0, 1)
    )
else:
    df["p_win_minus_loss"] = np.nan


# ============================================================
# DEFINICIÓN DE FEATURES POR VENTANA
# ============================================================
features_comunes = [
    "local",
    "p_win_minus_loss",
    "partido_muy_desequilibrado",

    "xg_rival_x_savepct",
    "gf_rival_last5_x_gc_per90",

    "score_porterias_cero",
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

features_window3 = [
    "pf_last3_mean",
    "savepct_last3_mean",
    "clean_last3_ratio",
    "clean_last3_ratio_extra",
    "titular_last3_ratio",
    "psxg_gc_diff_last3_mean",
    "form_vs_class_keeper_3",
    "saves_last3_mean",
    "saves_last3_mean_extra",
    "psxg_per90_last3",
    "gc_per90_last3",
    "xg_last3_mean_rival",
    "shots_on_target_ratio_rival_last3",
    "bombardeo_last3_mean",

    # nuevas derivadas ventana 3
    "rival_xg_per_shot_last3",
    "rival_sot_ratio_last3",
    "form_goles_evitados_last3",
    "potencial_paradas_match_last3",
    "dominio_aereo_last3",
    "riesgo_goleada_last3",
]

features_window5 = [
    "pf_last5_mean",
    "savepct_last5_mean",
    "clean_last5_ratio",
    "clean_last5_ratio_extra",
    "titular_last5_ratio",
    "psxg_gc_diff_last5_mean",
    "form_vs_class_keeper",
    "saves_last5_mean",
    "saves_last5_mean_extra",
    "psxg_per90_last5",
    "gc_per90_last5",
    "xg_last5_mean_rival",
    "shots_on_target_ratio_rival",
    "bombardeo_last5_mean",

    # nuevas derivadas ventana 5
    "rival_xg_per_shot_last5",
    "rival_sot_ratio_last5",
    "form_goles_evitados_last5",
    "potencial_paradas_match_last5",
    "dominio_aereo_last5",
    "riesgo_goleada_last5",
]


def get_features_for_window(window: int):
    if window == 3:
        base_window_feats = features_window3
    elif window == 5:
        base_window_feats = features_window5
    else:
        base_window_feats = []
    return features_comunes + base_window_feats


# ============================================================
# DEFINICIÓN DE GRIDS (COMÚN A TODAS LAS VENTANAS)
# ============================================================

n_estimators_list = [200, 400, 600]
max_depth_list = [6, 8, 10, 12, 14]
min_samples_leaf_list = [3, 5, 10, 15]
max_features_list = [0.3, 0.4, 0.5, 0.6]

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

xgb_depth_list = [2, 3, 4, 5, 6]
xgb_n_estimators_list = [200, 400, 600, 800, 1000, 1200]
xgb_lr_list = [0.001, 0.015, 0.002, 0.025, 0.04]

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

elastic_alphas = [0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
elastic_l1_ratios = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9]

elastic_configs = []
for alpha, l1 in product(elastic_alphas, elastic_l1_ratios):
    name = f"elastic_a{alpha}_l1{l1}"
    elastic_configs.append({
        "name": name,
        "alpha": alpha,
        "l1_ratio": l1,
    })


# ============================================================
# BUCLE POR VENTANA + ENTRENAMIENTO RF/XGB/ELASTIC
# ============================================================

resultados_mae = []
resultados_r2 = []

for window in [3, 5]:
    print("\n" + "="*80)
    print(f"ENTRENANDO PARA VENTANA {window} PARTIDOS")
    print("="*80)

    features_validas = get_features_for_window(window)
    features_disponibles = [f for f in features_validas if f in df.columns]
    print(f"✅ Features válidas ventana {window}: {len(features_disponibles)}")

    feature_cols_win3 = [f for f in get_features_for_window(3) if f in df.columns]
    feature_cols_win5 = [f for f in get_features_for_window(5) if f in df.columns]

    with open("feature_cols_win3.pkl", "wb") as f:
        pickle.dump(feature_cols_win3, f)

    with open("feature_cols_win5.pkl", "wb") as f:
        pickle.dump(feature_cols_win5, f)

    log_feats_path = Path(f"features_porteros_win{window}.txt")

    all_feats = list(dict.fromkeys(features_validas))
    available = [f for f in all_feats if f in df.columns]
    missing = [f for f in all_feats if f not in df.columns]

    with open(log_feats_path, "w", encoding="utf-8") as f:
        f.write(f"VENTANA {window}\n\n")
        f.write("✅ FEATURES USADAS (existen en df):\n")
        for feat in available:
            f.write(f"  - {feat}\n")

        f.write("\n❌ FEATURES DESCARTADAS:\n")
        for feat in missing:
            f.write(
                f"  - {feat} | motivo: columna no presente en "
                "players_with_features_exp3_CORREGIDO.csv\n"
            )

    df_subset = df[features_disponibles + ["puntosFantasy"]].copy()

    nan_log_path = Path(f"nan_report_porteros_win{window}.txt")
    na_counts = df_subset.isna().sum().sort_values(ascending=False)

    with open(nan_log_path, "w", encoding="utf-8") as f:
        f.write(f"Nulos por columna (ventana {window}):\n")
        f.write(na_counts.to_string())
        f.write("\n")

    df_filtrado = df_subset.fillna(0)

    if len(df_filtrado) < 100:
        print(f"❌ Muy pocas filas para ventana {window}, se omite.")
        continue

    X = df_filtrado[features_disponibles].copy()
    y = df_filtrado["puntosFantasy"].copy()

    split_point = int(len(X) * 0.8)

    X_train = X.iloc[:split_point].copy()
    X_test  = X.iloc[split_point:].copy()
    y_train = y.iloc[:split_point].copy()
    y_test  = y.iloc[split_point:].copy()

    print(f"✅ Temporal split ventana {window}:")
    print(f"   Train: {X_train.shape}, Test: {X_test.shape}")

    # RF base
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
    y_pred_test_base_round = np.round(y_pred_test_base)

    mae_test_base = mean_absolute_error(y_test, y_pred_test_base_round)
    rmse_test_base = root_mean_squared_error(y_test, y_pred_test_base)
    r2_test_base = r2_score(y_test, y_pred_test_base)

    print(
        f"[ventana {window}] RF_base MAE: {mae_test_base:.4f} | "
        f"RMSE: {rmse_test_base:.4f} | R2: {r2_test_base:.4f}"
    )

    # GRID RF
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
        rmse_test_rf = root_mean_squared_error(y_test, y_pred_test_rf)
        r2_test_rf = r2_score(y_test, y_pred_test_rf)

        print(
            f"[ventana {window}] MAE Test {name_win}: {mae_test_rf:.4f} | "
            f"RMSE: {rmse_test_rf:.4f} | R2: {r2_test_rf:.4f}"
        )

        resultados_mae.append({
            "name": name_win,
            "mae": mae_test_rf,
            "rmse": rmse_test_rf,
            "r2": r2_test_rf,
            "model": modelo_rf,
            "tipo": "rf",
            "window": window,
        })
        resultados_r2.append({
            "name": name_win,
            "mae": mae_test_rf,
            "rmse": rmse_test_rf,
            "r2": r2_test_rf,
            "model": modelo_rf,
            "tipo": "rf",
            "window": window,
        })

        if mae_test_rf < mejor_mae_rf_grid:
            mejor_mae_rf_grid = mae_test_rf
            mejor_rf_grid = modelo_rf

    # GRID XGBOOST
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
        rmse_test_xgb = root_mean_squared_error(y_test, y_pred_test_xgb)
        r2_test_xgb = r2_score(y_test, y_pred_test_xgb)

        print(
            f"[ventana {window}] MAE Test {name_win}: {mae_test_xgb:.4f} | "
            f"RMSE: {rmse_test_xgb:.4f} | R2: {r2_test_xgb:.4f}"
        )

        resultados_mae.append({
            "name": name_win,
            "mae": mae_test_xgb,
            "rmse": rmse_test_xgb,
            "r2": r2_test_xgb,
            "model": modelo_xgb,
            "tipo": "xgb",
            "window": window,
        })
        resultados_r2.append({
            "name": name_win,
            "mae": mae_test_xgb,
            "rmse": rmse_test_xgb,
            "r2": r2_test_xgb,
            "model": modelo_xgb,
            "tipo": "xgb",
            "window": window,
        })

        if mae_test_xgb < mejor_mae_xgb:
            mejor_mae_xgb = mae_test_xgb
            mejor_xgb = modelo_xgb

    # GRID ELASTICNET
    mejor_elastic = None
    mejor_mae_elastic = np.inf

    print("\n" + "-"*80)
    print(f"GRID ELASTICNET (PORTEROS) - VENTANA {window}")
    print("-"*80)

    for cfg in elastic_configs:
        name_win = f"win{window}_" + cfg["name"]
        print(f"\n⏳ Entrenando {name_win} (ElasticNet, PT)...")

        modelo_elastic = Pipeline([
            ("scaler", StandardScaler()),
            ("reg", ElasticNet(
                alpha=cfg["alpha"],
                l1_ratio=cfg["l1_ratio"],
                random_state=42,
                max_iter=10000,
            )),
        ])

        modelo_elastic.fit(X_train, y_train)
        y_pred_test_elastic = modelo_elastic.predict(X_test)
        y_pred_test_elastic_round = np.round(y_pred_test_elastic)

        mae_test_elastic = mean_absolute_error(y_test, y_pred_test_elastic_round)
        rmse_test_elastic = root_mean_squared_error(y_test, y_pred_test_elastic)
        r2_test_elastic = r2_score(y_test, y_pred_test_elastic)

        print(
            f"[ventana {window}] MAE Test {name_win}: {mae_test_elastic:.4f} | "
            f"RMSE: {rmse_test_elastic:.4f} | R2: {r2_test_elastic:.4f}"
        )

        resultados_mae.append({
            "name": name_win,
            "mae": mae_test_elastic,
            "rmse": rmse_test_elastic,
            "r2": r2_test_elastic,
            "model": modelo_elastic,
            "tipo": "elastic",
            "window": window,
        })
        resultados_r2.append({
            "name": name_win,
            "mae": mae_test_elastic,
            "rmse": rmse_test_elastic,
            "r2": r2_test_elastic,
            "model": modelo_elastic,
            "tipo": "elastic",
            "window": window,
        })

        if mae_test_elastic < mejor_mae_elastic:
            mejor_mae_elastic = mae_test_elastic
            mejor_elastic = modelo_elastic


# ============================================================
# COMPARATIVA FINAL GLOBAL (PORTEROS) Y GUARDADO DE 2 MODELOS
# ============================================================

print("\n" + "="*80)
print("RESULTADOS MEJORES MODELOS (PORTEROS) - GLOBAL (VENTANAS 3,5)")
print("="*80)

best_mae_entry = min(resultados_mae, key=lambda d: d["mae"])
print("\n" + "#"*80)
print("##### MEJOR MODELO GLOBAL POR MAE #####")
print("#"*80)
print(
    f"- win{best_mae_entry['window']} {best_mae_entry['tipo'].upper()} {best_mae_entry['name']}: "
    f"MAE={best_mae_entry['mae']:.4f}, RMSE={best_mae_entry['rmse']:.4f}, R2={best_mae_entry['r2']:.4f}"
)
best_mae_filename = output_dir / (
    f"best_global_mae_win{best_mae_entry['window']}_{best_mae_entry['tipo']}_{best_mae_entry['name']}"
    f"_mae{best_mae_entry['mae']:.4f}_rmse{best_mae_entry['rmse']:.4f}_r2{best_mae_entry['r2']:.4f}.pkl"
)
with open(best_mae_filename, "wb") as f:
    pickle.dump(best_mae_entry["model"], f)
print(f"✅ Modelo global por MAE guardado en: {best_mae_filename}")

best_r2_entry = max(resultados_r2, key=lambda d: d["r2"])
print("\n" + "#"*80)
print("##### MEJOR MODELO GLOBAL POR R2 #####")
print("#"*80)
print(
    f"- win{best_r2_entry['window']} {best_r2_entry['tipo'].upper()} {best_r2_entry['name']}: "
    f"MAE={best_r2_entry['mae']:.4f}, RMSE={best_r2_entry['rmse']:.4f}, R2={best_r2_entry['r2']:.4f}"
)
best_r2_filename = output_dir / (
    f"best_global_r2_win{best_r2_entry['window']}_{best_r2_entry['tipo']}_{best_r2_entry['name']}"
    f"_mae{best_r2_entry['mae']:.4f}_rmse{best_r2_entry['rmse']:.4f}_r2{best_r2_entry['r2']:.4f}.pkl"
)
with open(best_r2_filename, "wb") as f:
    pickle.dump(best_r2_entry["model"], f)
print(f"✅ Modelo global por R2 guardado en: {best_r2_filename}")


# ============================================================
# EXPLICABILIDAD GLOBAL SHAP (PORTEROS) + XAI AVANZADO
# ============================================================

print("\n" + "="*80)
print("🎯 CALCULANDO EXPLAINER SHAP GLOBAL (TreeExplainer)")
print("="*80 + "\n")

mejor_modelo_mae = best_mae_entry["model"]
mejor_window = best_mae_entry["window"]

print(f"Usando mejor modelo global (ventana {mejor_window}) para SHAP")

features_validas_mejor = get_features_for_window(mejor_window)
features_disponibles_mejor = [f for f in features_validas_mejor if f in df.columns]

df_subset_mejor = df[features_disponibles_mejor + ["puntosFantasy"]].copy()
df_filtrado_mejor = df_subset_mejor.fillna(0)

X_mejor = df_filtrado_mejor[features_disponibles_mejor].copy()
y_mejor = df_filtrado_mejor["puntosFantasy"].copy()

split_point_mejor = int(len(X_mejor) * 0.8)
X_train_mejor = X_mejor.iloc[:split_point_mejor].copy()
X_test_mejor  = X_mejor.iloc[split_point_mejor:].copy()

print("⏳ Calculando SHAP values para el conjunto de test del mejor modelo...")
explainer_shap = shap.TreeExplainer(mejor_modelo_mae)
shap_values_global = explainer_shap.shap_values(X_test_mejor)

explainer_path = "explainer_shap.pkl"
with open(explainer_path, "wb") as f:
    pickle.dump(explainer_shap, f)
print(f"✅ Explainer guardado: {explainer_path}")

shap_values_path = "shap_values_test.pkl"
with open(shap_values_path, "wb") as f:
    pickle.dump(shap_values_global, f)
print(f"✅ SHAP values guardados: {shap_values_path}")

feature_cols_path = f"feature_cols_win{mejor_window}.pkl"
with open(feature_cols_path, "wb") as f:
    pickle.dump(features_disponibles_mejor, f)
print(f"✅ Feature cols guardados: {feature_cols_path}")

importances_shap = np.abs(shap_values_global).mean(axis=0)
importances_df = pd.DataFrame({
    "feature": features_disponibles_mejor,
    "shap_importance": importances_shap
}).sort_values("shap_importance", ascending=False)

print("\n📊 Top 15 features por importancia SHAP:")
print(importances_df.head(15).to_string(index=False))

importances_df.to_csv(f"feature_importances_shap_win{mejor_window}.csv", index=False)
print(f"\n✅ Feature importances guardadas\n")

print("\n" + "="*80)
print("🔍 XAI AVANZADO: Dirección, Gráficos y Explicación Local")
print("="*80 + "\n")

# 1. Dirección (correlación feature vs SHAP)
correlation_list = []
for feat in features_disponibles_mejor:
    feat_values = X_test_mejor[feat].values
    col_idx = list(X_test_mejor.columns).index(feat)
    shap_col = shap_values_global[:, col_idx]

    if np.std(feat_values) == 0 or np.std(shap_col) == 0:
        corr = 0
    else:
        corr = np.corrcoef(feat_values, shap_col)[0, 1]

    correlation_list.append(corr)

importances_df["shap_direction"] = [
    correlation_list[features_disponibles_mejor.index(f)]
    for f in importances_df["feature"]
]
importances_df["impacto"] = np.where(
    importances_df["shap_direction"] > 0,
    "Positivo (+)",
    "Negativo (-)"
)

print("\n📊 Top 10 Features con dirección de impacto:")
print(importances_df[["feature", "shap_importance", "impacto"]].head(10).to_string(index=False))

csv_advanced_path = f"feature_importances_shap_advanced_win{mejor_window}.csv"
importances_df.to_csv(csv_advanced_path, index=False)
print(f"✅ CSV Avanzado guardado: {csv_advanced_path}")

# 2. Summary plot (beeswarm)
plt.figure(figsize=(12, 10))
shap.summary_plot(shap_values_global, X_test_mejor, show=False, max_display=15)
plot_filename = output_dir / f"shap_summary_win{mejor_window}.png"
plt.savefig(plot_filename, bbox_inches="tight", dpi=300)
plt.close()
print(f"✅ Gráfico Summary Plot guardado en: {plot_filename}")

# 3. Dependence plots top 3
top_3_features = importances_df["feature"].head(3).tolist()
for feat in top_3_features:
    plt.figure(figsize=(8, 6))
    shap.dependence_plot(
        feat,
        shap_values_global,
        X_test_mejor,
        display_features=X_test_mejor,
        show=False,
        interaction_index=None
    )
    plt.title(f"Dependencia SHAP: {feat}")
    plt.tight_layout()
    dep_filename = output_dir / f"shap_dependence_{feat}_win{mejor_window}.png"
    plt.savefig(dep_filename, dpi=150)
    plt.close()
    print(f"✅ Gráfico Dependencia guardado para: {feat}")

# 4. Explicación local (caso con mayor predicción)
idx_max_pred = mejor_modelo_mae.predict(X_test_mejor).argmax()
row_data = X_test_mejor.iloc[idx_max_pred]
shap_vals_row = shap_values_global[idx_max_pred]
base_value = explainer_shap.expected_value
if isinstance(base_value, np.ndarray):
    base_value = base_value[0]

predicted_value = base_value + shap_vals_row.sum()

print("\n" + "-"*50)
print(f"🕵️‍♂️ ANÁLISIS DEL CASO CON MAYOR PREDICCIÓN (Índice {idx_max_pred})")
print("-" * 50)
print(f"Base Value (Media global): {base_value:.4f}")
print(f"Predicción Final:          {predicted_value:.4f}")
print("\nDesglose de contribuciones (Top 5 que más sumaron):")

contributions = pd.DataFrame({
    "feature": features_disponibles_mejor,
    "valor_real": row_data.values,
    "aporte_shap": shap_vals_row
}).sort_values("aporte_shap", ascending=False)

print(contributions.head(5).to_string(index=False))

print("\nDesglose de contribuciones (Top 3 que restaron):")
print(contributions.tail(3).sort_values("aporte_shap").to_string(index=False))

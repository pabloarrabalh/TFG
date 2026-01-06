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
from sklearn.metrics import mean_absolute_error

from xgboost import XGBRegressor

print("\n" + "="*80)
print("ENTRENANDO MODELOS LIMPIOS - SIN DATA LEAKAGE")
print("="*80 + "\n")

# ============================================================
# CARGAR DATOS
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

print(f"📂 Cargando: {csv_path}")
df = pd.read_csv(csv_path)
print(f"✅ Cargado: {df.shape[0]} filas, {df.shape[1]} columnas\n")

# ============================================================
# FEATURES VÁLIDAS (SIN DATA LEAKAGE)
# ============================================================

features_validas = [
    "local",
    "posicion_equipo",
    "posicion_rival",
    "p_home",
    "p_draw",
    "p_away",
    "p_win_propio",
    "p_loss_propio",
    "p_draw_match",
    "pf_last5_mean",
    "pf_last5_std",
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
    "pf_spike_last5",
    "gf_last5_mean_team",
    "gc_last5_mean_team",
    "goal_diff_last5_team",
    "xg_last5_mean_team",
    "xg_contra_last5_mean_team",
    "gf_last5_mean_rival",
    "gc_last5_mean_rival",
    "goal_diff_last5_rival",
    "xg_last5_mean_rival",
    "xg_contra_last5_mean_rival",
    "shots_last5_mean_rival",
    "shots_on_target_last5_mean_rival",
    "shots_on_target_ratio_rival",
    "pts_diff",
    "gf_diff",
    "gc_diff",
    "is_top4_propio",
    "is_top4_rival",
    "is_bottom3_rival",
    "ratio_paradas_dificiles",
    "xg_rival_x_savepct",
    "xg_rival_x_gc_per90",
    "gf_rival_last5_x_gc_per90",
    "goal_diff_rival_x_pf_var",
    "score_porterias_cero",
    "score_save_pct",
    "score_porterias_cero_strong",
    "score_save_pct_strong",
    "rol_x_xg_rival",
    "elite_keeper",
    "is_top5_porterias_cero",
    "is_top5_save_pct",
    "score_pc_boost",
    "score_sp_boost",
    "rol_x_xg_rival_boost",
    "ataque_top_rival_x_elite",
    "rol_pos_porterias_cero",
    "rol_val_porterias_cero",
    "rol_pos_paradas",
    "rol_val_paradas",
    "rol_pos_save_pct",
    "rol_val_save_pct",
    "is_top5_en_algo",
]

features_disponibles = [f for f in features_validas if f in df.columns]
print(f"✅ Features válidas encontradas: {len(features_disponibles)}")
print(f"   (Eliminadas: {len(features_validas) - len(features_disponibles)} que no existen)")

# ============================================================
# PREPARAR DATOS
# ============================================================

print(f"\n📊 Preparando datos...")

df_filtrado = df[
    (df["puntosFantasy"] >= -10) &
    (df["puntosFantasy"] <= 30)
].copy()

print(f"   Filas tras filtro PF [-10, 30]: {len(df_filtrado)}")

df_filtrado = df_filtrado[features_disponibles + ["puntosFantasy"]].dropna()
print(f"   Filas sin NaN: {len(df_filtrado)}")

if len(df_filtrado) < 100:
    print(f"❌ Muy pocas filas! ({len(df_filtrado)})")
    exit(1)

X = df_filtrado[features_disponibles].copy()
y = df_filtrado["puntosFantasy"].copy()

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42
)

print(f"   X_train: {X_train.shape}")
print(f"   X_test:  {X_test.shape}")

# ============================================================
# RF BASE (TU MODELO BUENO)
# ============================================================

print(f"\n⏳ Entrenando Random Forest base (sin data leakage)...")

modelo_limpio = RandomForestRegressor(
    n_estimators=300,
    max_features=0.5,
    max_depth=8,
    min_samples_leaf=10,
    random_state=42,
    n_jobs=-1
)
modelo_limpio.fit(X_train, y_train)

y_pred_train_base = modelo_limpio.predict(X_train)
y_pred_test_base = modelo_limpio.predict(X_test)

mae_train_base = mean_absolute_error(y_train, np.round(y_pred_train_base))
mae_test_base = mean_absolute_error(y_test, np.round(y_pred_test_base))

print(f"MAE Train RF_base: {mae_train_base:.4f}")
print(f"MAE Test  RF_base: {mae_test_base:.4f}")

# ============================================================
# LOG DE IMPORTANCIAS RF
# ============================================================

log_path = "rf_feature_importances.txt"
with open(log_path, "w", encoding="utf-8") as f:
    f.write("RandomForest feature importances por configuración\n\n")

# ============================================================
# GRID RANDOM FOREST MASIVO
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

print(f"\nTotal configuraciones RF: {len(rf_configs)}")  # 3*4*3*3 = 108

mejor_rf_grid = None
mejor_mae_rf_grid = np.inf

print("\n" + "-"*80)
print("GRID RANDOM FOREST")
print("-"*80)

for cfg in rf_configs:
    print(f"\n⏳ Entrenando {cfg['name']} (RandomForest)...")
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
    mae_test_rf = mean_absolute_error(y_test, np.round(y_pred_test_rf))
    print(f"MAE Test {cfg['name']}: {mae_test_rf:.4f}")

    # Guardar modelo
    filename = f"modelo_porteros_{cfg['name']}_mae{mae_test_rf:.4f}.pkl"
    with open(filename, "wb") as f:
        pickle.dump(modelo_rf, f)

    # Log de hiperparámetros + top-10 features
    importancias = modelo_rf.feature_importances_
    ranking = sorted(
        zip(importancias, features_disponibles),
        reverse=True
    )

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"Modelo: {cfg['name']}\n")
        f.write(
            f"  n_estimators={cfg['n_estimators']}, "
            f"max_depth={cfg['max_depth']}, "
            f"min_samples_leaf={cfg['min_samples_leaf']}, "
            f"max_features={cfg['max_features']}\n"
        )
        f.write(f"  MAE_test={mae_test_rf:.4f}\n")
        f.write("  Top 10 features:\n")
        for imp, name in ranking[:10]:
            f.write(f"    {name}: {imp:.4f}\n")
        f.write("\n")

    if mae_test_rf < mejor_mae_rf_grid:
        mejor_mae_rf_grid = mae_test_rf
        mejor_rf_grid = modelo_rf

# ============================================================
# GRID XGBOOST (COMO ANTES)
# ============================================================

print("\n" + "-"*80)
print("GRID XGBOOST")
print("-"*80)

xgb_configs = [
    {"name": "xgb_depth2", "max_depth": 2, "n_estimators": 600,  "learning_rate": 0.03},
    {"name": "xgb_depth3", "max_depth": 3, "n_estimators": 600,  "learning_rate": 0.03},
    {"name": "xgb_depth4", "max_depth": 4, "n_estimators": 600,  "learning_rate": 0.03},
    {"name": "xgb_best",   "max_depth": 4, "n_estimators": 1200, "learning_rate": 0.02},
]

mejor_xgb = None
mejor_mae_xgb = np.inf

for cfg in xgb_configs:
    print(f"\n⏳ Entrenando {cfg['name']} (XGBoost)...")
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
    mae_test_xgb = mean_absolute_error(y_test, np.round(y_pred_test_xgb))
    print(f"MAE Test {cfg['name']}: {mae_test_xgb:.4f}")

    filename = f"modelo_porteros_{cfg['name']}_mae{mae_test_xgb:.4f}.pkl"
    with open(filename, "wb") as f:
        pickle.dump(modelo_xgb, f)

    if mae_test_xgb < mejor_mae_xgb:
        mejor_mae_xgb = mae_test_xgb
        mejor_xgb = modelo_xgb

# ============================================================
# COMPARATIVA FINAL
# ============================================================

print("\n" + "="*80)
print("RESULTADOS MEJORES MODELOS")
print("="*80)
print(f"RF_base (tuyo)     - MAE Test: {mae_test_base:.4f}")
print(f"Mejor RF grid      - MAE Test: {mejor_mae_rf_grid:.4f}")
print(f"Mejor XGB          - MAE Test: {mejor_mae_xgb:.4f}")

# Elegimos seguir usando tu RF base como modelo_limpio
modelo_final = modelo_limpio

# ============================================================
# GUARDAR MODELO LIMPIO + FEATURES
# ============================================================

print(f"\n{'='*80}")
print(f"GUARDANDO MODELO LIMPIO (RF_base)")
print(f"{'='*80}\n")

with open("modelo_porteros_limpio.pkl", "wb") as f:
    pickle.dump(modelo_final, f)
print(f"✅ Modelo: modelo_porteros_limpio.pkl ({len(features_disponibles)} features)")

with open("feature_cols_limpio.pkl", "wb") as f:
    pickle.dump(features_disponibles, f)
print(f"✅ Features: feature_cols_limpio.pkl")

print(f"\n{'='*80}")
print("✅ LISTO PARA PREDECIR")
print(f"{'='*80}")

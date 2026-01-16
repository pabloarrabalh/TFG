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
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error,
    r2_score,
    root_mean_squared_error,
)
from xgboost import XGBRegressor

# Carpeta de salida para modelos
output_dir = Path("modelos")
output_dir.mkdir(exist_ok=True)

print("Número de porteros:")
df_check = pd.read_csv("players_with_features_exp3_CORREGIDO.csv")
df_pt_check = df_check[df_check["posicion"] == "PT"]
print(len(df_pt_check))  # [file:34]

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
print(f"✅ Cargado: {df.shape[0]} filas de porteros, {df.shape[1]} columnas\n")  # [file:34]

# ============================================================
# ORDEN TEMPORAL + PF_MEDIA_HISTORICA (SIN LEAKAGE)
# ============================================================

# Usamos columnas temporales existentes: temporada, jornada, fecha_partido
sort_cols = []
for c in ["temporada", "jornada", "fecha_partido"]:
    if c in df.columns:
        sort_cols.append(c)

df = df.sort_values(sort_cols).reset_index(drop=True)

# pf_media_historica: media de puntosFantasy previa por jugador (player)
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

# 1) Bombardeo partido (solo info del propio partido)
df["bombardeo_partido"] = (
    df["shots_on_target_rival_partido"].clip(lower=0) *
    (1 - df["Goles_en_contra"].clip(lower=0))
)

# 2) Saves partido
df["saves_partido"] = (
    df["shots_on_target_rival_partido"].clip(lower=0) -
    df["Goles_en_contra"].clip(lower=0)
).clip(lower=0)

# 2bis) Porcentaje de paradas histórico (solo partidos anteriores)
df["paradas_partido"] = df["saves_partido"]

df["shots_on_target_hist"] = (
    df.groupby("player")["shots_on_target_rival_partido"]
      .transform(lambda s: s.shift().expanding().sum())
)

df["paradas_hist"] = (
    df.groupby("player")["paradas_partido"]
      .transform(lambda s: s.shift().expanding().sum())
)

df["savepct_hist"] = np.where(
    df["shots_on_target_hist"] > 0,
    df["paradas_hist"] / df["shots_on_target_hist"],
    np.nan
)

# 3) Clean sheet flag
df["clean_sheet_flag"] = (df["Goles_en_contra"] == 0).astype(int)

# 4) Rolling por portero sin leakage (shift + rolling)
def rolling_feat(col, window, agg, new_name):
    df[new_name] = (
        df.groupby("player")[col]
          .transform(lambda s: getattr(s.shift().rolling(window, min_periods=1), agg)())
    )

# Bombardeo medio
rolling_feat("bombardeo_partido", 3, "mean", "bombardeo_last3_mean")
rolling_feat("bombardeo_partido", 5, "mean", "bombardeo_last5_mean")

# Saves medios extra
rolling_feat("saves_partido", 3, "mean", "saves_last3_mean_extra")
rolling_feat("saves_partido", 5, "mean", "saves_last5_mean_extra")

# Ratio de clean sheets extra
rolling_feat("clean_sheet_flag", 3, "mean", "clean_last3_ratio_extra")
rolling_feat("clean_sheet_flag", 5, "mean", "clean_last5_ratio_extra")

# 5) Partido muy desequilibrado (solo info de cuotas pre-partido)
df["partido_muy_desequilibrado"] = (df["ah_line_match"].abs() >= 1.5).astype(int)


# =========================
# FEATURES AVANZADAS PORTERO X RIVAL
# =========================

# 1) ratio_paradas_dificiles (se usa solo para análisis, no como feature directa)
df["goles_ev_prt"] = (df["PSxG"] - df["Goles_en_contra"]).clip(lower=0)
df["ratio_paradas_dificiles"] = np.where(
    df["shots_on_target_rival_partido"] > 0,
    df["goles_ev_prt"] / df["shots_on_target_rival_partido"],
    0
)

# 2) xg_rival_x_savepct (usa histórico)
df["xg_rival_x_savepct"] = df["xg_last5_mean_rival"] * df["savepct_hist"]

# 3) xg_rival_x_gc_per90
df["xg_rival_x_gc_per90"] = df["xg_last5_mean_rival"] * df["gc_per90_last5"]

# 4) gf_rival_last5_x_gc_per90
df["gf_rival_last5_x_gc_per90"] = df["gf_last5_mean_rival"] * df["gc_per90_last5"]


# =========================
# ROLES / CALIDAD PORTERO
# =========================

# Portero “de porterías a cero” vs “de paradas”
df["score_porterias_cero"] = (1 - df["gc_per90_last5"]).clip(lower=0)
df["score_save_pct"] = df["savepct_hist"]

# Clasificación en percentiles globales
q_pc = df["score_porterias_cero"].quantile(0.8)
q_sp = df["score_save_pct"].quantile(0.8)

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

# Boosts y rol_x_xg_rival
df["score_pc_boost"] = df["score_porterias_cero"] * (df["ataque_top_rival"].fillna(0) + 1)
df["score_sp_boost"] = df["score_save_pct"] * (df["ataque_top_rival"].fillna(0) + 1)

df["rol_x_xg_rival"] = (
    df[["score_porterias_cero", "score_save_pct"]].mean(axis=1) *
    df["xg_last5_mean_rival"]
)
df["rol_x_xg_rival_boost"] = df["rol_x_xg_rival"] * (df["ataque_top_rival"].fillna(0) + 1)

# Interacción ataque top rival x elite
df["ataque_top_rival_x_elite"] = df["ataque_top_rival"].fillna(0) * df["elite_keeper"]

# =========================
# RACHAS PORTERO (3 PARTIDOS) SIN LEAKAGE
# =========================

# 1) pf_last3_mean: media PF últimos 3
df["pf_last3_mean"] = (
    df.groupby("player")["puntosFantasy"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

# 2) savepct_last3_mean: media % paradas históricos últimos 3
df["savepct_last3_mean"] = (
    df.groupby("player")["savepct_hist"]
      .transform(lambda s: s.rolling(3, min_periods=1).mean())
)

# 3) clean_last3_ratio
df["clean_last3_ratio"] = (
    df.groupby("player")["clean_sheet_flag"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

# 4) titular_last3_ratio
df["es_titular_partido"] = (df["Min_partido"] > 0).astype(int)
df["titular_last3_ratio"] = (
    df.groupby("player")["es_titular_partido"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

# 5) psxg_gc_diff_last3_mean
df["psxg_gc_diff"] = df["PSxG"] - df["Goles_en_contra"]
df["psxg_gc_diff_last3_mean"] = (
    df.groupby("player")["psxg_gc_diff"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

# 6) saves_last3_mean
df["saves_last3_mean"] = (
    df.groupby("player")["saves_partido"]
      .transform(lambda s: s.shift().rolling(3, min_periods=1).mean())
)

# 7) form_vs_class_keeper_3
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
      .transform(lambda s: s.rolling(5, min_periods=1).mean())
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

# --- Ajuste apuestas: balancear win/loss ---

# 1) Versión suavizada de p_loss (que no dispare tanto)
df["p_loss_soft"] = np.sqrt(df["p_loss_propio"].clip(0, 1))

# 2) Diferencial de probabilidad: muy alta victoria => menos tiros esperados
#    (si no tienes p_win_propio, puedes crearlo a partir de cuotas antes)
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
    # Contexto partido / apuestas (pre‑match)
    "local",
    #"p_loss_soft",          # en vez de p_loss_propio
    "p_win_minus_loss",
    "partido_muy_desequilibrado",

    # Fuerza relativa clasificación (pre‑match)
    #"is_top4_rival",
    #"is_bottom3_rival",

    # Mixtas portero x rival (rolling/pre‑match)
    "xg_rival_x_savepct",
    "xg_rival_x_gc_per90",
    "gf_rival_last5_x_gc_per90",

    # Roles / calidad portero (derivan de rolling históricos)
    "score_porterias_cero",
    #"score_save_pct",
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
max_depth_list = [ 6, 8, 10, 12, 14]
min_samples_leaf_list = [3, 5, 10, 15,]
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
# BUCLE POR VENTANA + ENTRENAMIENTO RF/XGB
# ============================================================
from pathlib import Path
import pandas as pd

def log_filas_problematicas_porteros(
    df: pd.DataFrame,
    feature_cols: list,
    log_path: str,
):
    """
    Loguea filas donde alguna feature tiene NaN.
    - Para jornadas 1 y 2: resumen por temporada y jornada -> "temporada X | jornada 1: N porteros"
    - A partir de la jornada 3: listado detallado como antes.
    Se asume que df ya solo contiene porteros.
    """
    cols_id = [
        "player",
        "Equipo_propio",
        "Equipo_rival",
        "temporada",
        "jornada",
        "fecha_partido",
    ]
    cols_id = [c for c in cols_id if c in df.columns]

    cols_existentes = [c for c in feature_cols if c in df.columns]
    if not cols_existentes:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("No hay features de esta ventana en el df\n")
        return

    feature_na = df[cols_existentes].isna()
    mask_fila_mal = feature_na.any(axis=1)

    df_bad = df.loc[mask_fila_mal, cols_id + cols_existentes].copy()
    if df_bad.empty:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("No hay filas problemáticas (sin NaN en features)\n")
        return

    log_file = Path(log_path)
    with open(log_file, "w", encoding="utf-8") as f:
        # ============================
        # RESUMEN JORNADAS 1 Y 2
        # ============================
        if {"jornada", "player", "temporada"}.issubset(df_bad.columns):
            f.write("RESUMEN NULOS JORNADAS 1 Y 2 (por temporada y jornada)\n\n")
            df_j1_2 = df_bad[df_bad["jornada"].isin([1, 2])].copy()

            if df_j1_2.empty:
                f.write("No hay porteros con NaN en jornadas 1 y 2.\n\n")
            else:
                resumen = (
                    df_j1_2
                    .groupby(["temporada", "jornada"])["player"]
                    .nunique()
                    .reset_index(name="n_porteros")
                )
                for _, row in resumen.iterrows():
                    f.write(
                        f"temporada {row['temporada']} | "
                        f"jornada {int(row['jornada'])}: "
                        f"{int(row['n_porteros'])} porteros con NaN\n"
                    )
                f.write("\n")

            # Para el detalle, nos quedamos solo con jornadas >= 3
            df_bad_detalle = df_bad[~df_bad["jornada"].isin([1, 2])].copy()
        else:
            df_bad_detalle = df_bad

        # ============================
        # DETALLE JORNADAS >= 3
        # ============================
        if df_bad_detalle.empty:
            f.write("No hay filas problemáticas a partir de la jornada 3.\n")
            return

        def columnas_con_nan(row):
            return [col for col in cols_existentes if pd.isna(row[col])]

        df_bad_detalle["cols_nan"] = df_bad_detalle.apply(columnas_con_nan, axis=1)

        f.write("FILAS PROBLEMÁTICAS (jornadas >= 3)\n\n")
        for _, row in df_bad_detalle.iterrows():
            ident_parts = []
            if "temporada" in row:
                ident_parts.append(f"temporada={row['temporada']}")
            if "jornada" in row:
                ident_parts.append(
                    f"jornada={int(row['jornada']) if pd.notna(row['jornada']) else 'NA'}"
                )
            if "fecha_partido" in row:
                ident_parts.append(f"fecha={row['fecha_partido']}")
            if "player" in row:
                ident_parts.append(f"player={row['player']}")
            if "Equipo_propio" in row:
                ident_parts.append(f"equipo={row['Equipo_propio']}")
            if "Equipo_rival" in row:
                ident_parts.append(f"rival={row['Equipo_rival']}")

            f.write(" | ".join(ident_parts) + "\n")
            f.write(f"  cols_nan: {row['cols_nan']}\n")
            f.write("-" * 80 + "\n")

resultados_mae = []
resultados_r2 = []

resultados_mae = []
resultados_r2 = []

for window in [3, 5]:
    print("\n" + "="*80)
    print(f"ENTRENANDO PARA VENTANA {window} PARTIDOS")
    print("="*80)

    # 1) Features según ventana
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

    all_feats = list(dict.fromkeys(features_validas))  # mantiene orden
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

    # 2) Subset con target (solo para NaN y entrenamiento)
    df_subset = df[features_disponibles + ["puntosFantasy"]].copy()

    # 3) Log de NaN por columna
    nan_log_path = Path(f"nan_report_porteros_win{window}.txt")
    na_counts = df_subset.isna().sum().sort_values(ascending=False)

    with open(nan_log_path, "w", encoding="utf-8") as f:
        f.write(f"Nulos por columna (ventana {window}):\n")
        f.write(na_counts.to_string())
        f.write("\n")

    umbral = 10
    problematicas = na_counts[na_counts > umbral]
    with open(nan_log_path, "a", encoding="utf-8") as f:
        f.write(f"\nColumnas con más de {umbral} NaN (ventana {window}):\n")
        f.write(problematicas.to_string())
        f.write("\n")

    # 3bis) Máscara de filas con NaN en alguna feature de esta ventana
    mask_fila_mal = df_subset[features_disponibles].isna().any(axis=1)

    # Log de filas problemáticas usando df completo (tiene player, temporada, etc.)
    log_filas_problematicas_porteros(
        df[mask_fila_mal],  # df original, ya filtrado a PT al inicio del script
        feature_cols=features_disponibles,
        log_path=f"nan_report_porteros_win{window}_filas.txt",
    )
    print("NaN antes de imputar:", df_subset[features_disponibles].isna().sum().sum())

    # 4) Imputar NaN con 0 una sola vez para entrenar
    df_filtrado = df_subset.fillna(0)

    if len(df_filtrado) < 100:
        print(f"❌ Muy pocas filas para ventana {window}, se omite.")
        continue

    # 5) X, y y split
    X = df_filtrado[features_disponibles].copy()
    y = df_filtrado["puntosFantasy"].copy()

    # Split temporal: primeras filas (jornadas iniciales) = train, últimas = test
    split_point = int(len(X) * 0.8)

    X_train = X.iloc[:split_point].copy()
    X_test  = X.iloc[split_point:].copy()
    y_train = y.iloc[:split_point].copy()
    y_test  = y.iloc[split_point:].copy()

    print(f"✅ Temporal split ventana {window}:")
    print(f"   Train: {X_train.shape}, Test: {X_test.shape}")

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
    y_pred_test_base_round = np.round(y_pred_test_base)

    mae_test_base = mean_absolute_error(y_test, y_pred_test_base_round)
    rmse_test_base = root_mean_squared_error(y_test, y_pred_test_base)
    r2_test_base = r2_score(y_test, y_pred_test_base)

    print(
        f"[ventana {window}] RF_base MAE: {mae_test_base:.4f} | "
        f"RMSE: {rmse_test_base:.4f} | R2: {r2_test_base:.4f}"
    )

    # ============================================================
    # LOG DE IMPORTANCIAS RF (POR VENTANA)
    # ============================================================

    log_path_imp = f"rf_feature_importances_porteros_win{window}.txt"
    with open(log_path_imp, "w", encoding="utf-8") as f:
        f.write(
            "RandomForest feature importances por configuración "
            f"(porteros) - ventana {window}\n\n"
        )

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

        importancias = modelo_rf.feature_importances_
        ranking = sorted(
            zip(importancias, features_disponibles),
            reverse=True
        )

        with open(log_path_imp, "a", encoding="utf-8") as f:
            f.write(f"Modelo: {name_win}\n")
            f.write(
                f"  n_estimators={cfg['n_estimators']}, "
                f"max_depth={cfg['max_depth']}, "
                f"min_samples_leaf={cfg['min_samples_leaf']}, "
                f"max_features={cfg['max_features']}\n"
            )
            f.write(
                f"  MAE_test={mae_test_rf:.4f}  "
                f"RMSE_test={rmse_test_rf:.4f}  "
                f"R2_test={r2_test_rf:.4f}\n"
            )
            f.write("  Top 10 features:\n")
            for imp, fname in ranking[:10]:
                f.write(f"    {fname}: {imp:.4f}\n")
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

    # ============================================================
    # GRID ELASTICNET (POR VENTANA)
    # ============================================================

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
# COMPARATIVA FINAL GLOBAL (PORTEROS)
# ============================================================

print("\n" + "="*80)
print("RESULTADOS MEJORES MODELOS (PORTEROS) - GLOBAL (VENTANAS 3,5)")
print("="*80)

# Top 3 por MAE (global)
top3_mae = sorted(resultados_mae, key=lambda d: d["mae"])[:3]

print("\n" + "#"*80)
print("##### TOP 3 MODELOS GLOBALES POR MAE #####")
print("#"*80)
for res in top3_mae:
    print(
        f"- win{res['window']} {res['tipo'].upper()} {res['name']}: "
        f"MAE={res['mae']:.4f}, RMSE={res['rmse']:.4f}, R2={res['r2']:.4f}"
    )
    filename = output_dir / (
        f"best_mae_win{res['window']}_{res['tipo']}_{res['name']}"
        f"_mae{res['mae']:.4f}_rmse{res['rmse']:.4f}_r2{res['r2']:.4f}.pkl"
    )
    with open(filename, "wb") as f:
        pickle.dump(res["model"], f)

# Top 3 por R2 (global)
top3_r2 = sorted(resultados_r2, key=lambda d: d["r2"], reverse=True)[:3]

print("\n" + "#"*80)
print("##### TOP 3 MODELOS GLOBALES POR R2 #####")
print("#"*80)
for res in top3_r2:
    print(
        f"- win{res['window']} {res['tipo'].upper()} {res['name']}: "
        f"MAE={res['mae']:.4f}, RMSE={res['rmse']:.4f}, R2={res['r2']:.4f}"
    )
    filename = output_dir / (
        f"best_r2_win{res['window']}_{res['tipo']}_{res['name']}"
        f"_mae{res['mae']:.4f}_rmse{res['rmse']:.4f}_r2{res['r2']:.4f}.pkl"
    )
    with open(filename, "wb") as f:
        pickle.dump(res["model"], f)

# ============================================================
# EXPLICABILIDAD GLOBAL SHAP (PORTEROS)
# ============================================================

import shap

print("\n" + "="*80)
print("🎯 CALCULANDO EXPLAINER SHAP GLOBAL (TreeExplainer)")
print("="*80 + "\n")

# Usar el MEJOR modelo por MAE (de todos los probados)
mejor_modelo_mae = top3_mae[0]["model"]
mejor_window = top3_mae[0]["window"]

print(f"Usando mejor modelo global (ventana {mejor_window}) para SHAP")

# OJO: aquí X_test y features_disponibles son los de la última ventana.
# Para que cuadre, volvemos a construir X_test para esa ventana.

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

# Guardar explainer
explainer_path = "explainer_shap.pkl"
with open(explainer_path, "wb") as f:
    pickle.dump(explainer_shap, f)
print(f"✅ Explainer guardado: {explainer_path}")

# Guardar SHAP values
shap_values_path = "shap_values_test.pkl"
with open(shap_values_path, "wb") as f:
    pickle.dump(shap_values_global, f)
print(f"✅ SHAP values guardados: {shap_values_path}")

# Guardar feature_cols de la ventana del mejor modelo (para predictor)
feature_cols_path = f"feature_cols_win{mejor_window}.pkl"
with open(feature_cols_path, "wb") as f:
    pickle.dump(features_disponibles_mejor, f)
print(f"✅ Feature cols guardados: {feature_cols_path}")

# Feature importances global SHAP
importances_shap = np.abs(shap_values_global).mean(axis=0)
importances_df = pd.DataFrame({
    "feature": features_disponibles_mejor,
    "shap_importance": importances_shap
}).sort_values("shap_importance", ascending=False)

print("\n📊 Top 15 features por importancia SHAP:")
print(importances_df.head(15).to_string(index=False))

importances_df.to_csv(f"feature_importances_shap_win{mejor_window}.csv", index=False)
print(f"\n✅ Feature importances guardadas\n")

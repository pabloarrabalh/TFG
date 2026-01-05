"""
ENTRENAR MODELO LIMPIO - SIN DATA LEAKAGE
Solo features disponibles ANTES del partido
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import pickle
from pathlib import Path

print("\n" + "="*80)
print("ENTRENANDO MODELO LIMPIO - SIN DATA LEAKAGE")
print("="*80 + "\n")

# ============================================================
# CARGAR DATOS
# ============================================================

# Buscar CSV
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

# Features que SÍ podemos usar (disponibles ANTES del partido)
features_validas = [
    # Clasificación de jornada anterior
    "local",
    "posicion_equipo",
    "pj",
    "pg",
    "pe",
    "pp",
    "gf",
    "gc",
    "dg",
    "pts",
    "posicion_rival",
    "pj_rival",
    "pg_rival",
    "pe_rival",
    "pp_rival",
    "gf_rival",
    "gc_rival",
    "dg_rival",
    "pts_rival",
    
    # Cuotas
    "p_home",
    "p_draw",
    "p_away",
    "p_over25",
    "ah_line",
    "p_win_propio",
    "p_loss_propio",
    "p_draw_match",
    "p_over25_match",
    "ah_line_match",
    
    # Rachas del portero (últimos 5 partidos PASADOS)
    "pf_last5_mean",
    "pf_last5_sum",
    "pf_last5_std",
    "pf_last5_max",
    "pf_last5_min",
    "min_last5_mean",
    "min_last5_sum",
    "gc_last5_mean",
    "gc_last5_std",
    "gc_last5_sum",
    "psxg_last5_mean",
    "psxg_last5_std",
    "psxg_last5_sum",
    "savepct_last5_mean",
    "clean_last5_sum",
    "clean_last5_ratio",
    "yellow_last5_sum",
    "red_last5_sum",
    "titular_last5_ratio",
    "psxg_gc_diff_last5_mean",
    "form_vs_class_keeper",
    "saves_last5_mean",
    "psxg_per90_last5",
    "gc_per90_last5",
    "pf_spike_last5",
    
    # Rachas de equipos (últimos 5 partidos PASADOS)
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
    
    # Diferencias y comparativas
    "pts_diff",
    "gf_diff",
    "gc_diff",
    "is_top4_propio",
    "is_top4_rival",
    "is_bottom3_rival",
    
    # Flags
    "ataque_top_rival",
    "defensa_floja_propia",
    "ataque_top_y_defensa_floja",
    
    # Interacciones
    "ratio_paradas_dificiles",
    "xg_rival_x_savepct",
    "xg_rival_x_gc_per90",
    "gf_rival_last5_x_gc_per90",
    "goal_diff_rival_x_pf_var",
    
    # Roles
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

# Filtrar solo las que existan en el CSV
features_disponibles = [f for f in features_validas if f in df.columns]

print(f"✅ Features válidas encontradas: {len(features_disponibles)}")
print(f"   (Eliminadas: {len(features_validas) - len(features_disponibles)} que no existen)")

# Mostrar features ELIMINADAS (que eran data leakage)
features_malas = [
    "Asist_partido", "xG_partido", "xAG", "Tiros", "TiroFallado_partido",
    "TiroPuerta_partido", "Pases_Totales", "Pases_Completados_Pct", "Entradas",
    "Duelos", "DuelosGanados", "DuelosPerdidos", "Bloqueos", "BloqueoTiros",
    "BloqueoPase", "Despejes", "Regates", "RegatesCompletados", "RegatesFallidos",
    "Conducciones", "DistanciaConduccion", "MetrosAvanzadosConduccion",
    "ConduccionesProgresivas", "DuelosAereosGanados", "DuelosAereosPerdidos",
    "DuelosAereosGanadosPct", "shots_propio_partido", "shots_rival_partido",
    "shots_on_target_propio_partido", "shots_on_target_rival_partido",
    "pf_last3_mean", "min_last3_mean", "goles_last3_sum", "xg_team_partido",
    "xg_rival_partido", "jornada_anterior", "score_porterias_cero_strong",
    "score_save_pct_strong", "pf_last3_mean", "min_last3_mean",
    "goles_last3_sum", "goal_per_shot_rival", "goal_attack_vs_defense"
]

features_malas_en_csv = [f for f in features_malas if f in df.columns]
print(f"❌ Features de DATA LEAKAGE eliminadas: {len(features_malas_en_csv)}")

# ============================================================
# PREPARAR DATOS
# ============================================================

print(f"\n📊 Preparando datos...")

# Filtrar porteros (últimos 5 partidos, filtro de PF)
df_filtrado = df[
    (df["puntosFantasy"] >= -10) & 
    (df["puntosFantasy"] <= 30)
].copy()

print(f"   Filas tras filtro PF [-10, 30]: {len(df_filtrado)}")

# Eliminar NaN en features
df_filtrado = df_filtrado[features_disponibles + ["puntosFantasy"]].dropna()

print(f"   Filas sin NaN: {len(df_filtrado)}")

if len(df_filtrado) < 100:
    print(f"❌ Muy pocas filas! ({len(df_filtrado)})")
    exit(1)

# Split train/test
X = df_filtrado[features_disponibles].copy()
y = df_filtrado["puntosFantasy"].copy()

X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=0.2, 
    random_state=42
)

print(f"   X_train: {X_train.shape}")
print(f"   X_test: {X_test.shape}")

# ============================================================
# ENTRENAR MODELO LIMPIO
# ============================================================

print(f"\n⏳ Entrenando Random Forest (sin data leakage)...")

modelo_limpio = RandomForestRegressor(
    n_estimators=200,
    max_depth=15,
    min_samples_split=10,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1
)

modelo_limpio.fit(X_train, y_train)

# ============================================================
# EVALUAR
# ============================================================

y_pred_train = modelo_limpio.predict(X_train)
y_pred_test = modelo_limpio.predict(X_test)

mae_train = mean_absolute_error(y_train, np.round(y_pred_train))
mae_test = mean_absolute_error(y_test, np.round(y_pred_test))

print(f"\n{'='*80}")
print(f"RESULTADOS")
print(f"{'='*80}")
print(f"MAE Train: {mae_train:.4f}")
print(f"MAE Test:  {mae_test:.4f}")

# Feature importance
feature_importance = pd.DataFrame({
    'feature': features_disponibles,
    'importance': modelo_limpio.feature_importances_
}).sort_values('importance', ascending=False)

print(f"\nTop 15 features:")
for i, row in feature_importance.head(15).iterrows():
    print(f"  {row['feature']:40s} {row['importance']:.6f}")

# ============================================================
# GUARDAR MODELO LIMPIO
# ============================================================

print(f"\n{'='*80}")
print(f"GUARDANDO MODELO LIMPIO")
print(f"{'='*80}\n")

# Guardar modelo
with open("modelo_porteros_limpio.pkl", 'wb') as f:
    pickle.dump(modelo_limpio, f)
print(f"✅ Modelo: modelo_porteros_limpio.pkl ({len(features_disponibles)} features)")

# Guardar features
with open("feature_cols_limpio.pkl", 'wb') as f:
    pickle.dump(features_disponibles, f)
print(f"✅ Features: feature_cols_limpio.pkl")

print(f"\n{'='*80}")
print(f"✅ LISTO PARA PREDECIR")
print(f"{'='*80}")
print(f"\nAhora usa:")
print(f"  python predictor-v4.py")

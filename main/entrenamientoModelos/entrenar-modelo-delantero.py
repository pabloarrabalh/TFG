import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.utils.parallel")
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from functools import reduce
import operator
import json
import pickle

from xgboost import XGBRegressor
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import GridSearchCV, ParameterGrid, cross_val_score
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from role_enricher import enriquecer_dataframe_con_roles, crear_features_interaccion_roles
from feature_improvements import eliminar_features_ruido, crear_features_fantasy_mediocampista, seleccionar_features_por_correlacion

DIRECTORIO_SALIDA = Path("csv/csvGenerados/entrenamiento/delantero")
DIRECTORIO_IMAGENES = DIRECTORIO_SALIDA / "imagenes"
DIRECTORIO_MODELOS = DIRECTORIO_SALIDA / "modelos"
DIRECTORIO_CSVS = DIRECTORIO_SALIDA / "csvs"

for d in [DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS]:
    d.mkdir(parents=True, exist_ok=True)

CONFIG = {
    'archivo': "csv/csvGenerados/players_with_features.csv",
    'ventana_corta': 3,
    'ventana_larga': 5,
    'columna_objetivo': "puntos_fantasy",
    'test_size': 0.2
}


def crear_features_temporales(df, columna, ventana_corta=3, ventana_larga=5, 
                              default_value=0, crear_lag=True, crear_std=False, 
                              crear_volatility=False, prefix="", verbose=False):
    if columna not in df.columns:
        return df
    
    nombre_base = prefix if prefix else columna
    df[columna] = pd.to_numeric(df[columna], errors='coerce').fillna(default_value)
    features_nuevos = []
    nuevas_cols = {}

    for ventana, nombre_ventana in [(ventana_corta, "3"), (ventana_larga, "5")]:
        col_roll = f"{nombre_base}_roll{nombre_ventana}"
        col_ewma = f"{nombre_base}_ewma{nombre_ventana}"
        
        nuevas_cols[col_roll] = df.groupby("player")[columna].transform(lambda x: x.shift().rolling(ventana, min_periods=1).mean())
        nuevas_cols[col_ewma] = df.groupby("player")[columna].transform(lambda x: x.shift().ewm(span=ventana, adjust=False).mean())
        
        features_nuevos.extend([col_roll, col_ewma])
    
    if crear_lag:
        nuevas_cols[f"{nombre_base}_lag1"] = df.groupby("player")[columna].transform(lambda x: x.shift(1))
        features_nuevos.append(f"{nombre_base}_lag1")
    
    if crear_std:
        col_std = f"{nombre_base}_std5"
        nuevas_cols[col_std] = df.groupby("player")[columna].transform(lambda x: x.shift().rolling(5, min_periods=1).std())
        features_nuevos.append(col_std)
    
    if crear_volatility:
        col_vol = f"{nombre_base}_volatility5"
        nuevas_cols[col_vol] = df.groupby("player")[columna].transform(lambda x: x.shift().rolling(5, min_periods=1).std() / (x.shift().rolling(5, min_periods=1).mean() + 0.1))
        features_nuevos.append(col_vol)
    
    if nuevas_cols:
        df = pd.concat([df, pd.DataFrame(nuevas_cols, index=df.index)], axis=1)
    
    if verbose:
        print(f"   ✅ {columna}: {len(features_nuevos)} features temporales")
    
    return df


def extraer_feature_importance(modelo, X_ent, feature_names):
    try:
        if hasattr(modelo, 'feature_importances_'):
            fi = pd.DataFrame({
                'feature': feature_names,
                'importance': modelo.feature_importances_
            }).sort_values('importance', ascending=False)
            return fi
        else:
            return None
    except:
        return None


def convertir_racha_a_numerico(racha):
    """Convierte racha de string (ej: 'WDLWW') a ratio de victorias"""
    if pd.isna(racha) or not isinstance(racha, str):
        return 0.0
    victorias = racha.count("W")
    total = len(racha)
    return (victorias / total if total > 0 else 0.0)


def visualizar_feature_importance(fi, titulo, nombre, top_n=20):
    if fi is None or len(fi) == 0:
        return
    
    df_top = fi.head(top_n)
    fig, ax = plt.subplots(figsize=(12, max(8, top_n * 0.4)))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(df_top)))
    ax.barh(range(len(df_top)), df_top['importance'].values, color=colors)
    ax.set_yticks(range(len(df_top)))
    ax.set_yticklabels(df_top['feature'].values, fontsize=9)
    ax.set_xlabel('Importancia', fontsize=11, fontweight='bold')
    ax.set_title(titulo, fontsize=12, fontweight='bold', pad=15)
    ax.invert_yaxis()
    for i, v in enumerate(df_top['importance'].values):
        ax.text(v, i, f' {v:.4f}', va='center', fontsize=8)
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(DIRECTORIO_IMAGENES / nombre, dpi=150, bbox_inches='tight')
    plt.close()


def cargar_datos():
    print(f"📂 Cargando: {CONFIG['archivo']}")
    try:
        df = pd.read_csv(CONFIG['archivo'], low_memory=False)
    except:
        df = pd.read_csv(CONFIG['archivo'], encoding='latin-1', low_memory=False)
    
    print(f"ℹ️  Total registros: {len(df)}")
    print(f"ℹ️  Total columnas: {len(df.columns)}")
    
    # Filtrar solo delanteros (posición ST)
    posicion_cols = [col for col in df.columns if 'posicion' in col.lower()]
    print(f"ℹ️  Columnas de posición encontradas: {posicion_cols}")
    
    if len(posicion_cols) > 0:
        # Prefer 'DT' as forward label in dataset; fallback to 'ST' if DT not present
        posiciones_existentes = df['posicion'].dropna().unique().tolist()
        if 'DT' in posiciones_existentes:
            df_delanteros = df[df['posicion'] == 'DT'].copy()
        else:
            df_delanteros = df[df['posicion'] == 'ST'].copy()
    else:
        print("❌ No se encontraron columnas de posición")
        df_delanteros = df.copy()
    
    print(f"✅ {df_delanteros.shape[0]} delanteros (ST) cargados\n")
    return df_delanteros


def diagnosticar_y_limpiar(df):
    filas_inicio = len(df)
    
    print("\n1️⃣ Verificando columnas necesarias...")
    cols_necesarias = ['player', CONFIG['columna_objetivo'], 'min_partido']
    cols_faltantes = [c for c in cols_necesarias if c not in df.columns]
    if cols_faltantes:
        print(f"   ⚠️ Columnas faltantes: {cols_faltantes}")
    else:
        print("   ✅ Todas las columnas necesarias presentes")
    
    print("\n2️⃣ Ordenando por jugador + jornada...")
    if 'jornada' in df.columns:
        df = df.sort_values(['player', 'jornada']).reset_index(drop=True)
    else:
        df = df.sort_values('player').reset_index(drop=True)
    print("   ✅ Datos ordenados temporalmente")
    
    print("\n3️⃣ Eliminando registros con <10 minutos...")
    muy_poco_antes = (df['min_partido'] < 10).sum()
    df = df[df['min_partido'] >= 10].copy()
    print(f"   ✅ Eliminados {muy_poco_antes} registros")
    
    print("\n4️⃣ Filtrando delanteros con <5 partidos...")
    jugs_validos = df.groupby('player').size() >= 5
    jugs_validos = jugs_validos[jugs_validos].index
    antes_jugs = len(df)
    df = df[df['player'].isin(jugs_validos)]
    print(f"   ✅ Eliminados {antes_jugs - len(df)} registros")
    
    print("\n5️⃣ Eliminando outliers extremos...")
    outliers_pf = (df[CONFIG['columna_objetivo']] > 30).sum()
    df = df[df[CONFIG['columna_objetivo']] <= 30].copy()
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
    a_eliminar = [
        "posicion", "Equipo_propio", "Equipo_rival",
        "TiroFallado_partido", "TiroPuerta_partido",
        "jornada", "jornada_anterior", "Date", "home", "away",
        "target_pf_next",
    ]
    a_eliminar = [c for c in a_eliminar if c in df.columns]
    df = df.drop(columns=a_eliminar, errors="ignore")
    
    if "racha5partidos" in df.columns:
        df["racha5partidos"] = df["racha5partidos"].apply(convertir_racha_a_numerico)
    
    if "racha5partidos_rival" in df.columns:
        df["racha5partidos_rival"] = df["racha5partidos_rival"].apply(convertir_racha_a_numerico)
    
    print("✅ Limpieza completada\n")
    return df


def cargar_y_procesar_odds(df):
    """Carga odds desde live_odds_cache.csv e integra 5 features de mercado."""
    print("[CHART] Integrando ODDS de mercado...")
    
    try:
        odds_df = pd.read_csv('csv/csvDescargados/live_odds_cache.csv')
        print(f"  [OK] live_odds_cache.csv: {odds_df.shape}")
        
        if 'jornada' not in odds_df.columns or 'jornada' not in df.columns:
            print("  [WARN] No existe columna 'jornada'")
            df['odds_prob_win'] = 0.33
            df['odds_prob_loss'] = 0.33
            df['odds_expected_goals_against'] = 0.33
            df['odds_is_favored'] = 0
            df['odds_market_confidence'] = 0.33
            return df
        
        def normalizar_equipo(nombre):
            if pd.isna(nombre):
                return None
            nombre = str(nombre).lower().strip()
            mapeos = {
                'ath bilbao': 'athletic bilbao',
                'ath madrid': 'atletico madrid',
                'vallecano': 'rayo',
                'ca osasuna': 'osasuna',
            }
            return mapeos.get(nombre, nombre)
        
        df['equipo_propio_norm'] = df['equipo_propio'].apply(normalizar_equipo)
        df['equipo_rival_norm'] = df['equipo_rival'].apply(normalizar_equipo)
        odds_df['home_norm'] = odds_df['home'].apply(normalizar_equipo)
        odds_df['away_norm'] = odds_df['away'].apply(normalizar_equipo)
        
        df['odds_prob_win'] = 0.33
        df['odds_prob_loss'] = 0.33
        df['odds_expected_goals_against'] = 0.33
        df['odds_is_favored'] = 0
        df['odds_market_confidence'] = 0.33
        
        if 'local' not in df.columns:
            print("  [WARN] No existe columna 'local'")
            return df
        
        local_count = 0
        local_mask = df['local'] == 1
        for idx in df[local_mask].index:
            jornada = df.loc[idx, 'jornada']
            equipo = df.loc[idx, 'equipo_propio_norm']
            
            match = odds_df[(odds_df['jornada'] == jornada) & (odds_df['home_norm'] == equipo)]
            if not match.empty:
                p_win = match.iloc[0]['p_home']
                p_loss = match.iloc[0]['p_away']
                
                df.loc[idx, 'odds_prob_win'] = p_win
                df.loc[idx, 'odds_prob_loss'] = p_loss
                df.loc[idx, 'odds_expected_goals_against'] = p_loss * 2.5
                df.loc[idx, 'odds_is_favored'] = 1 if p_win > p_loss else 0
                df.loc[idx, 'odds_market_confidence'] = max(p_win, match.iloc[0].get('p_draw', 0.33), p_loss) - min(p_win, match.iloc[0].get('p_draw', 0.33), p_loss)
                local_count += 1
        
        away_count = 0
        away_mask = df['local'] == 0
        for idx in df[away_mask].index:
            jornada = df.loc[idx, 'jornada']
            equipo = df.loc[idx, 'equipo_rival_norm']
            
            match = odds_df[(odds_df['jornada'] == jornada) & (odds_df['away_norm'] == equipo)]
            if not match.empty:
                p_win = match.iloc[0]['p_away']
                p_loss = match.iloc[0]['p_home']
                
                df.loc[idx, 'odds_prob_win'] = p_win
                df.loc[idx, 'odds_prob_loss'] = p_loss
                df.loc[idx, 'odds_expected_goals_against'] = p_loss * 2.5
                df.loc[idx, 'odds_is_favored'] = 1 if p_win > p_loss else 0
                df.loc[idx, 'odds_market_confidence'] = max(p_win, match.iloc[0].get('p_draw', 0.33), p_loss) - min(p_win, match.iloc[0].get('p_draw', 0.33), p_loss)
                away_count += 1
        
        print(f"  [OK] Matched {local_count} local + {away_count} away = {local_count + away_count} records\n")
        
        df = df.drop(columns=['equipo_propio_norm', 'equipo_rival_norm'], errors='ignore')
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        df['odds_prob_win'] = 0.33
        df['odds_prob_loss'] = 0.33
        df['odds_expected_goals_against'] = 0.33
        df['odds_is_favored'] = 0
        df['odds_market_confidence'] = 0.33
    
    return df


def crear_features_delanteros_basicos(df):
    """Features delanteros: Goles, xG, Tiros, Regates, Pases clave"""
    print("=" * 80)
    print("FEATURES DELANTEROS (OFENSIVOS)")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    st_specs = [
        ("gol_partido", 0, "goals"),
        ("xg_partido", 0, "xg"),
        ("tiros", 0, "shots"),
        ("tiro_puerta_partido", 0, "shots_on_target"),
        ("regates", 0, "dribbles"),
        ("regates_completados", 0, "succ_dribbles"),
        ("conducciones_progresivas", 0, "prog_dribbles"),
        ("metros_avanzados_conduccion", 0, "prog_dist"),
        ("pases_clave", 0, "key_passes"),
        ("entradas", 0, "tackles"),
    ]
    
    for col, default, prefix in st_specs:
        df = crear_features_temporales(df, col, vc, vl, default_value=default, prefix=prefix, verbose=True)
    
    return df


def crear_features_form(df):
    print("=" * 80)
    print("FEATURES FORM (PUNTOS FANTASY)")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    if CONFIG['columna_objetivo'] in df.columns:
        df = crear_features_temporales(df, CONFIG['columna_objetivo'], vc, vl, crear_lag=True, prefix="pf", verbose=True)
    
    return df


def crear_features_disponibilidad(df):
    print("=" * 80)
    print("FEATURES DISPONIBILIDAD")
    print("=" * 80)
    
    vc, vl = CONFIG['ventana_corta'], CONFIG['ventana_larga']
    
    df["min_partido"] = pd.to_numeric(df["min_partido"], errors='coerce').fillna(45)
    df["minutes_pct_temp"] = (df["min_partido"] / 90).fillna(0).clip(0, 1)
    
    df = crear_features_temporales(df, "minutes_pct_temp", vc, vl, crear_lag=False, default_value=0, prefix="minutes_pct", verbose=True)
    
    if "titular" in df.columns:
        df["starter_temp"] = df["titular"].astype(float)
        df = crear_features_temporales(df, "starter_temp", vc, vl, crear_lag=False, default_value=0, prefix="starter_pct", verbose=True)
    
    df = df.drop(columns=["minutes_pct_temp"])
    return df


def crear_features_contexto(df):
    print("=" * 80)
    print("FEATURES CONTEXTO")
    print("=" * 80)
    
    if "local" in df.columns:
        df["is_home"] = (df["local"] == 1).astype(int)
    else:
        df["is_home"] = 0
    
    print("✅ Home/Away (is_home)\n")
    return df


def crear_features_rival(df):
    print("=" * 80)
    print("FEATURES RIVAL (HISTÓRICOS CON SHIFT - SIN LEAKAGE)")
    print("=" * 80)
    
    vl = CONFIG['ventana_larga']
    
    rival_specs = [
        ("gf_rival", 0, "opp_gf"),
        ("gc_rival", 0, "opp_gc"),
        ("racha5partidos_rival", 0, "opp_form"),
    ]
    
    for col, default, prefix in rival_specs:
        if col in df.columns:
            if col == "racha5partidos_rival":
                print(f"   Converting {col} to numeric (ratio victorias)...")
                df[col] = df[col].apply(convertir_racha_a_numerico)
            
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df[f'{col}_shifted'] = df[col].shift()
            
            df[f'{prefix}_roll3'] = df[f'{col}_shifted'].rolling(3, min_periods=1).mean()
            df[f'{prefix}_ewma3'] = df[f'{col}_shifted'].ewm(span=3, adjust=False).mean()
            
            df[f'{prefix}_roll5'] = df[f'{col}_shifted'].rolling(5, min_periods=1).mean()
            df[f'{prefix}_ewma5'] = df[f'{col}_shifted'].ewm(span=5, adjust=False).mean()
            
            df = df.drop(columns=[f'{col}_shifted'], errors='ignore')
            
            print(f"   ✅ {col} → {prefix}_roll3/5 + ewma3/5 (GLOBAL shift, sin groupby)")
    
    print()
    return df


def crear_features_avanzados(df):
    """Features avanzados para delanteros - Eficiencia ofensiva"""
    print("=" * 80)
    print("FEATURES AVANZADOS (DELANTEROS)")
    print("=" * 80)
    
    df = df.copy()
    nuevos_features = []
    
    # Eficiencia de tiro: xG vs Goles
    if "xg_roll5" in df.columns and "goals_roll5" in df.columns:
        df["shot_efficiency"] = (df["goals_roll5"] / (df["xg_roll5"] + 0.1)).fillna(0)
        nuevos_features.append("shot_efficiency")
    
    # Precisión de tiro: Tiros a puerta / Total tiros
    if "shots_on_target_roll5" in df.columns and "shots_roll5" in df.columns:
        df["shot_accuracy"] = (df["shots_on_target_roll5"] / (df["shots_roll5"] + 0.1)).fillna(0)
        nuevos_features.append("shot_accuracy")
    
    # Amenaza ofensiva: Tiros + Regates
    if "shots_roll5" in df.columns and "succ_dribbles_roll5" in df.columns:
        df["offensive_threat"] = df["shots_roll5"] + df["succ_dribbles_roll5"]
        nuevos_features.append("offensive_threat")
    
    # Creatividad: Pases clave / Partidos
    if "key_passes_roll5" in df.columns:
        df["creativity_index"] = df["key_passes_roll5"]
        nuevos_features.append("creativity_index")
    
    # Disponibilidad ofensiva: Minutos x Amenaza
    if "minutes_pct_roll5" in df.columns and "shots_roll5" in df.columns:
        df["availability_threat"] = df["minutes_pct_roll5"] * df["shots_roll5"]
        nuevos_features.append("availability_threat")
    
    # Forma delantero: Goles + xG
    if "goals_roll5" in df.columns and "xg_roll5" in df.columns:
        df["offensive_form"] = df["goals_roll5"] + df["xg_roll5"]
        nuevos_features.append("offensive_form")
    
    # Regates ofensivos: Regates completados para avanzar
    if "prog_dribbles_roll5" in df.columns:
        df["progressive_pressure"] = df["prog_dribbles_roll5"]
        nuevos_features.append("progressive_pressure")
    
    # Productividad: Goles / Tiros
    if "goals_roll5" in df.columns and "shots_roll5" in df.columns:
        df["goal_productivity"] = (df["goals_roll5"] / (df["shots_roll5"] + 0.1)).fillna(0)
        nuevos_features.append("goal_productivity")
    
    df = df.fillna(0).replace([np.inf, -np.inf], 0)
    print(f"   {len(nuevos_features)} features avanzados agregados\n")
    
    return df


def integrar_roles(df):
    print("=" * 80)
    print("ROLES FBREF")
    print("=" * 80)
    df = enriquecer_dataframe_con_roles(df, position="FW", columna_roles="roles")
    df = crear_features_interaccion_roles(df, position="FW", columna_objetivo=CONFIG['columna_objetivo'])
    print(" Roles OK\n")
    return df


def aplicar_mejoras(df):
    print("=" * 80)
    print("MEJORAS")
    print("=" * 80)
    antes = len(df.columns)
    df = eliminar_features_ruido(df, position="FW", verbose=True)
    print(f"Sin ruido: {antes}  {len(df.columns)}")
    
    antes = len(df.columns)
    df = crear_features_fantasy_mediocampista(df, verbose=True)
    print(f"Finales: {antes}  {len(df.columns)}\n")
    return df


def aplicar_feature_selection(X, y):
    print("=" * 80)
    print(" SELECCIÓN FEATURES (THRESHOLD 0.02 - MAS AGRESIVO)")
    print("=" * 80 + "\n")
    
    resultado = seleccionar_features_por_correlacion(X, y, target_name=CONFIG['columna_objetivo'], threshold=0.02, verbose=True)
    print(f"[DEBUG] seleccionar_features_por_correlacion returned type: {type(resultado)}")

    if isinstance(resultado, tuple) and len(resultado) == 2:
        features_validos, df_corr = resultado
    else:
        try:
            df_corr = resultado if isinstance(resultado, pd.DataFrame) else pd.DataFrame(resultado)
        except Exception:
            df_corr = pd.DataFrame(columns=['feature', 'spearman', 'p_value', 'abs_spearman'])

        if 'abs_spearman' in df_corr.columns:
            features_validos = df_corr[df_corr['abs_spearman'] >= 0.02]['feature'].tolist()
        else:
            features_validos = []

    df_corr.to_csv(DIRECTORIO_CSVS / "feature_correlations_detailed.csv", index=False)
    print(f"\n✅ {len(features_validos)} features seleccionados por correlación\n")
    return features_validos


def definir_variables_finales(df):
    print("=" * 80)
    print(" VARIABLES FINALES (DELANTERO)")
    print("=" * 80 + "\n")
    
    variables = [
        # ATAQUE (CORE)
        "goals_roll5", "goals_ewma5",
        "xg_roll5", "xg_ewma5",
        "shots_roll5", "shots_ewma5",
        "shots_on_target_roll5", "shots_on_target_ewma5",
        
        # MOVIMIENTO OFENSIVO
        "dribbles_roll5", "dribbles_ewma5",
        "succ_dribbles_roll5", "succ_dribbles_ewma5",
        "prog_dribbles_roll5", "prog_dribbles_ewma5",
        "prog_dist_roll5", "prog_dist_ewma5",
        
        # CREATIVIDAD
        "key_passes_roll5", "key_passes_ewma5",
        
        # FORMA (FANTASY)
        "pf_roll5", "pf_ewma5",
        
        # DISPONIBILIDAD
        "minutes_pct_roll5", "minutes_pct_ewma5",
        "starter_pct_roll3", "starter_pct_ewma3",
        
        # CONTEXTO
        "is_home",
        
        # ODDS (MERCADO)
        "odds_prob_win", "odds_prob_loss", "odds_expected_goals_against",
        "odds_is_favored", "odds_market_confidence",
        
        # RIVAL (HISTÓRICOS)
        "opp_gf_roll5", "opp_gf_ewma5",
        "opp_gc_roll5", "opp_gc_ewma5",
        "opp_form_roll5", "opp_form_ewma5",
        
        # ROLES
        "num_roles", "score_roles", "tiene_rol_destacado",
        
        # FEATURES AVANZADOS
        "shot_efficiency", "shot_accuracy", "offensive_threat",
        "creativity_index", "availability_threat", "offensive_form",
        "progressive_pressure", "goal_productivity",
    ]
    
    variables_finales = [v for v in variables if v in df.columns]
    
    print(f"Total variables finales: {len(variables_finales)}\n")
    return variables_finales


def entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables):
    print("=" * 80)
    print(" GRIDSEARCH TRAINING (Delantero)")
    print("=" * 80 + "\n")
    
    resultados = []
    
    # 1. Random Forest
    print(" Random Forest...")
    rf_params = {
        'n_estimators': [200, 300, 400, 500],
        'max_depth': [10, 20, 30, None],
        'min_samples_split': [2, 3, 5, 7],
        'min_samples_leaf': [1, 2, 3, 4, 5],
        'max_features': ['sqrt', 'log2', None]
    }
    rf_num_configs = reduce(operator.mul, [len(v) for v in rf_params.values()])
    print(f"   {rf_num_configs} configs")
    
    rf_gs = GridSearchCV(RandomForestRegressor(random_state=42, n_jobs=-1), rf_params, cv=5, 
                         scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    rf_gs.fit(X_train, y_train)
    rf_best = rf_gs.best_estimator_
    pred_rf = rf_best.predict(X_test)
    mae_rf = mean_absolute_error(y_test, pred_rf)
    rmse_rf = root_mean_squared_error(y_test, pred_rf)
    spearman_rf = spearmanr(y_test, pred_rf)[0]

    print(f"   MAE: {mae_rf:.4f}, RMSE: {rmse_rf:.4f}, Spearman: {spearman_rf:.4f}\n")
    resultados.append({'Model': 'RF', 'MAE': mae_rf, 'RMSE': rmse_rf, 'Spearman': spearman_rf})

    fi_rf = extraer_feature_importance(rf_best, X_train, variables)
    if fi_rf is not None:
        fi_rf.to_csv(DIRECTORIO_CSVS / "feature_importance_rf.csv", index=False)
        visualizar_feature_importance(fi_rf, "Random Forest - Top 20", "01_feature_importance_rf.png", 20)

    # 2. XGBoost
    print(" XGBoost...")
    xgb_params = {
        'max_depth': [5, 7],
        'learning_rate': [0.1, 0.15],
        'n_estimators': [300, 500],
        'subsample': [0.7, 0.9],
        'colsample_bytree': [0.7, 0.9],
        'gamma': [0.25, 0.5],
        'min_child_weight': [1, 3, 5],
        'reg_alpha': [0.05, 0.1],
        'reg_lambda': [1.0, 2.0]
    }
    xgb_num_configs = reduce(operator.mul, [len(v) for v in xgb_params.values()])
    print(f"   {xgb_num_configs} configs")
    
    xgb_gs = GridSearchCV(XGBRegressor(random_state=42, n_jobs=-1), xgb_params, cv=5, 
                          scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    xgb_gs.fit(X_train, y_train)
    xgb_best = xgb_gs.best_estimator_
    pred_xgb = xgb_best.predict(X_test)
    mae_xgb = mean_absolute_error(y_test, pred_xgb)
    rmse_xgb = root_mean_squared_error(y_test, pred_xgb)
    spearman_xgb = spearmanr(y_test, pred_xgb)[0]

    print(f"   MAE: {mae_xgb:.4f}, RMSE: {rmse_xgb:.4f}, Spearman: {spearman_xgb:.4f}\n")
    resultados.append({'Model': 'XGB', 'MAE': mae_xgb, 'RMSE': rmse_xgb, 'Spearman': spearman_xgb})

    fi_xgb = extraer_feature_importance(xgb_best, X_train, variables)
    if fi_xgb is not None:
        fi_xgb.to_csv(DIRECTORIO_CSVS / "feature_importance_xgb.csv", index=False)
        visualizar_feature_importance(fi_xgb, "XGBoost - Top 20", "02_feature_importance_xgb.png", 20)

    # 3. Ridge
    print(" Ridge...")
    ridge_pipeline = Pipeline([('scaler', StandardScaler()), ('regresor', Ridge())])
    ridge_params = {'regresor__alpha': [0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2000.0]}
    ridge_num_configs = len(ridge_params['regresor__alpha'])
    print(f"   {ridge_num_configs} configs")
    
    ridge_gs = GridSearchCV(ridge_pipeline, ridge_params, cv=5, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    ridge_gs.fit(X_train, y_train)
    ridge_best = ridge_gs.best_estimator_
    pred_ridge = ridge_best.predict(X_test)
    mae_ridge = mean_absolute_error(y_test, pred_ridge)
    rmse_ridge = root_mean_squared_error(y_test, pred_ridge)
    spearman_ridge = spearmanr(y_test, pred_ridge)[0]
    
    print(f"   MAE: {mae_ridge:.4f}, RMSE: {rmse_ridge:.4f}, Spearman: {spearman_ridge:.4f}\n")
    resultados.append({'Model': 'Ridge', 'MAE': mae_ridge, 'RMSE': rmse_ridge, 'Spearman': spearman_ridge})

    fi_ridge = extraer_feature_importance(ridge_best, X_train, variables)
    if fi_ridge is not None:
        fi_ridge.to_csv(DIRECTORIO_CSVS / "feature_importance_ridge.csv", index=False)
        visualizar_feature_importance(fi_ridge, "Ridge - Top 20", "03_feature_importance_ridge.png", 20)
    
    # 4. ElasticNet
    print(" ElasticNet...")
    elastic_pipeline = Pipeline([('scaler', StandardScaler()), ('regresor', ElasticNet(random_state=42))])
    elastic_params = {
        'regresor__alpha': [0.0001, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
        'regresor__l1_ratio': [0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0],
        'regresor__max_iter': [5000, 10000, 15000],
        'regresor__tol': [1e-3, 1e-4, 1e-5]
    }
    elastic_num_configs = reduce(operator.mul, [len(v) for v in elastic_params.values()])
    print(f"   {elastic_num_configs} configs")
    
    elastic_gs = GridSearchCV(elastic_pipeline, elastic_params, cv=5, scoring='neg_mean_absolute_error', n_jobs=-1, verbose=1)
    elastic_gs.fit(X_train, y_train)
    elastic_best = elastic_gs.best_estimator_
    pred_elastic = elastic_best.predict(X_test)
    mae_elastic = mean_absolute_error(y_test, pred_elastic)
    rmse_elastic = root_mean_squared_error(y_test, pred_elastic)
    spearman_elastic = spearmanr(y_test, pred_elastic)[0]
    
    print(f"   MAE: {mae_elastic:.4f}, RMSE: {rmse_elastic:.4f}, Spearman: {spearman_elastic:.4f}\n")
    resultados.append({'Model': 'ElasticNet', 'MAE': mae_elastic, 'RMSE': rmse_elastic, 'Spearman': spearman_elastic})

    fi_elastic = extraer_feature_importance(elastic_best, X_train, variables)
    if fi_elastic is not None:
        fi_elastic.to_csv(DIRECTORIO_CSVS / "feature_importance_elastic.csv", index=False)
        visualizar_feature_importance(fi_elastic, "ElasticNet - Top 20", "04_feature_importance_elastic.png", 20)

    df_resultados = pd.DataFrame(resultados).sort_values('MAE')
    print("\n" + "=" * 80)
    print("RANKING MODELOS POR MAE")
    print("=" * 80)
    print(df_resultados.to_string(index=False))
    df_resultados.to_csv(DIRECTORIO_CSVS / "resultados_gridsearch_delantero.csv", index=False)
    
    print(f"\n✅ Modelos guardados en {DIRECTORIO_MODELOS}")
    print(f"✅ Mejor modelo: {df_resultados.iloc[0]['Model']} (MAE: {df_resultados.iloc[0]['MAE']:.4f})\n")
    
    models_dict = {'RF': rf_best, 'XGB': xgb_best, 'Ridge': ridge_best, 'ElasticNet': elastic_best}
    for name, model in models_dict.items():
        with open(DIRECTORIO_MODELOS / f"best_model_delantero_{name.lower()}.pkl", "wb") as f:
            pickle.dump(model, f)
            
    return df_resultados


def main():
    print("\n" + "=" * 80)
    print(" ENTRENA MODELO DE PREDICCIÓN: DELANTEROS (ST)")
    print("=" * 80 + "\n")
    
    # 1. Cargar datos
    df = cargar_datos()
    
    # 2. Diagnosticar y limpiar
    df = diagnosticar_y_limpiar(df)
    
    # 3. Cargar y procesar odds (ANTES de borrar jornada)
    df = cargar_y_procesar_odds(df)
    
    # 4. Preparar básicos (borra jornada DESPUÉS de odds)
    df = preparar_basicos(df)
    
    # 5. Crear features delanteros
    df = crear_features_delanteros_basicos(df)
    
    # 6. Features form, disponibilidad, contexto
    df = crear_features_form(df)
    df = crear_features_disponibilidad(df)
    df = crear_features_contexto(df)
    df = crear_features_rival(df)
    
    # 7. Features avanzados
    df = crear_features_avanzados(df)
    
    # 8. Roles
    df = integrar_roles(df)
    
    # 9. Aplicar mejoras
    df = aplicar_mejoras(df)
    
    # 10. Preparar variables finales
    variables_finales = definir_variables_finales(df)
    
    # Verificar que existan todas las variables
    variables_finales = [v for v in variables_finales if v in df.columns]
    print(f"Variables finales disponibles: {len(variables_finales)}\n")
    
    # 11. Split train/test
    print("=" * 80)
    print(" SPLIT TRAIN/TEST")
    print("=" * 80 + "\n")
    
    X = df[variables_finales].fillna(0)
    y = df[CONFIG['columna_objetivo']].fillna(0)
    
    split_idx = int(len(X) * (1 - CONFIG['test_size']))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    print(f"Train: {len(X_train)} muestras")
    print(f"Test: {len(X_test)} muestras")
    print(f"Features: {len(variables_finales)}\n")
    
    # 12. Application feature selection
    variables_finales = aplicar_feature_selection(X_train, y_train)
    X_train = X_train[variables_finales]
    X_test = X_test[variables_finales]
    
    # 13. Entrenar modelos
    entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables_finales)
    
    print("\n" + "=" * 80)
    print(" ✅ ENTRENAMIENTO COMPLETADO EXITOSAMENTE")
    print("=" * 80)


if __name__ == "__main__":
    main()

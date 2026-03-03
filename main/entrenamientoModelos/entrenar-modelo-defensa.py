import warnings
warnings.filterwarnings("ignore", message=".*sklearn.utils.parallel.delayed.*", category=UserWarning)
import pickle
import json
from pathlib import Path
from functools import reduce
import operator
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from role_enricher import enriquecer_dataframe_con_roles, crear_features_interaccion_roles
from feature_improvements import eliminar_features_ruido, crear_features_fantasy_defensivos, seleccionar_features_por_correlacion

DIRECTORIO_SALIDA = Path("csv/csvGenerados/entrenamiento/defensa")
DIRECTORIO_IMAGENES = DIRECTORIO_SALIDA / "imagenes"
DIRECTORIO_MODELOS = DIRECTORIO_SALIDA / "modelos"
DIRECTORIO_CSVS = DIRECTORIO_SALIDA / "csvs"

for d in [DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS, DIRECTORIO_CSVS]:
    d.mkdir(parents=True, exist_ok=True)

CONFIG = {
    'archivo': "csv/csvGenerados/players_with_features.csv",
    'ventana_corta': 3,
    'ventana_larga': 5,
    'ventana_extra': 7,
    'columna_objetivo': "puntos_fantasy",
    'test_size': 0.2
}


def crear_features_temporales(df, columna, ventana_corta=3, ventana_larga=5, ventana_extra=7, 
                              default_value=0, crear_lag=True, crear_std=False, 
                              crear_volatility=False, prefix="", verbose=False):
    if columna not in df.columns:
        if verbose: print(f"[WARN] {columna} no existe")
        return df, []
    
    nombre_base = prefix if prefix else columna
    df[columna] = pd.to_numeric(df[columna], errors='coerce').fillna(default_value)
    features_nuevos = []
    nuevas_cols = {}

    for ventana, nombre_ventana in [(ventana_corta, "3"), (ventana_larga, "5"), (ventana_extra, "7")]:
        col_roll = f"{nombre_base}_roll{nombre_ventana}"
        nuevas_cols[col_roll] = df.groupby("player")[columna].transform(
            lambda x: x.shift().rolling(ventana, min_periods=1).mean()
        ).fillna(default_value)
        features_nuevos.append(col_roll)
        
        col_ewma = f"{nombre_base}_ewma{nombre_ventana}"
        nuevas_cols[col_ewma] = df.groupby("player")[columna].transform(
            lambda x: x.shift().ewm(span=ventana, adjust=False).mean()
        ).fillna(default_value)
        features_nuevos.append(col_ewma)
    
    if crear_lag:
        nuevas_cols[f"{nombre_base}_lag1"] = df.groupby("player")[columna].shift(1).fillna(default_value)
        nuevas_cols[f"{nombre_base}_lag2"] = df.groupby("player")[columna].shift(2).fillna(default_value)
        features_nuevos.extend([f"{nombre_base}_lag1", f"{nombre_base}_lag2"])
    
    if crear_std:
        nuevas_cols[f"{nombre_base}_std3"] = df.groupby("player")[columna].transform(
            lambda x: x.shift().rolling(ventana_corta, min_periods=1).std()
        ).fillna(default_value)
        features_nuevos.append(f"{nombre_base}_std3")
    
    if crear_volatility:
        mean_temp = df.groupby("player")[columna].transform(
            lambda x: x.shift().rolling(ventana_corta, min_periods=1).mean()
        ).fillna(1)
        std_temp = df.groupby("player")[columna].transform(
            lambda x: x.shift().rolling(ventana_corta, min_periods=1).std()
        ).fillna(default_value)
        nuevas_cols[f"{nombre_base}_volatility3"] = (std_temp / (mean_temp + 1e-6)).fillna(default_value).replace([np.inf, -np.inf], default_value)
        features_nuevos.append(f"{nombre_base}_volatility3")
    
    if nuevas_cols:
        df_nuevas = pd.DataFrame(nuevas_cols, index=df.index)
        df = pd.concat([df, df_nuevas], axis=1)
    
    if verbose:
        print(f"   {nombre_base}: {len(features_nuevos)} features")
    
    return df, features_nuevos


def extraer_feature_importance(modelo, X_ent, feature_names):
    try:
        importances = modelo.named_steps['regresor'].coef_ if hasattr(modelo, 'named_steps') else modelo.feature_importances_
        if not hasattr(importances, '__iter__'):
            return None
        df_fi = pd.DataFrame({'feature': feature_names, 'importance': np.abs(importances)})
        df_fi = df_fi.sort_values('importance', ascending=False)
        return df_fi.reset_index(drop=True)
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
        df = pd.read_csv(CONFIG['archivo'])
    except:
        df = pd.read_csv(CONFIG['archivo'], encoding='latin-1')
    
    print(f"ℹ️  Total registros: {len(df)}")
    print(f"ℹ️  Total columnas: {len(df.columns)}")
    
    # Filtrar solo defensas (posición DF)
    posicion_cols = [col for col in df.columns if 'posicion' in col.lower()]
    print(f"ℹ️  Columnas de posición encontradas: {posicion_cols}")
    
    if len(posicion_cols) > 0:
        df_defensas = df[df[posicion_cols[0]].str.upper() == "DF"].copy()
    else:
        print("⚠️  No hay columnas de posición, usando todo el dataset")
        df_defensas = df
    
    print(f"✅ {df_defensas.shape[0]} defensas (DF) cargadas\n")
    return df_defensas


def diagnosticar_y_limpiar(df):
    filas_inicio = len(df)
    
    print("\n1️⃣ Verificando columnas necesarias...")
    cols_necesarias = ['player', CONFIG['columna_objetivo'], 'min_partido']
    cols_faltantes = [c for c in cols_necesarias if c not in df.columns]
    if cols_faltantes:
        print(f"⚠️  Faltan: {cols_faltantes}")
    else:
        print("✅ Todas las columnas necesarias presentes")
    
    print("\n2️⃣ Ordenando por jugador + jornada...")
    if 'jornada' in df.columns:
        df = df.sort_values(['player', 'jornada'])
    else:
        print("⚠️  No hay columna jornada")
    print("   ✅ Datos ordenados temporalmente")
    
    print("\n3️⃣ Eliminando registros con <10 minutos...")
    muy_poco_antes = (df['min_partido'] < 10).sum()
    df = df[df['min_partido'] >= 10].copy()
    print(f"   ✅ Eliminados {muy_poco_antes} registros")
    
    print("\n4️⃣ Filtrando defensas con <5 partidos...")
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
        "Regates", "RegatesCompletados", "RegatesFallidos",
        "Conducciones", "DistanciaConduccion", "MetrosAvanzadosConduccion",
        "ConduccionesProgresivas",
        "jornada", "jornada_anterior", "Date", "home", "away",
        "Gol_partido", "Asist_partido", "xG_partido", "xAG", "Tiros", "target_pf_next",
    ]
    a_eliminar = [c for c in a_eliminar if c in df.columns]
    df = df.drop(columns=a_eliminar, errors="ignore")
    
    if "racha5partidos" in df.columns:
        df["racha_propio_ratio"] = df["racha5partidos"].apply(
            lambda x: x.count("W") / len(x) if isinstance(x, str) and len(x) > 0 else 0.0
        )
    
    if "racha5partidos_rival" in df.columns:
        df["racha_rival_ratio"] = df["racha5partidos_rival"].apply(
            lambda x: x.count("W") / len(x) if isinstance(x, str) and len(x) > 0 else 0.0
        )
    
    print("✅ Limpieza completada\n")
    return df


def cargar_y_procesar_odds(df):
    """Carga odds desde live_odds_cache.csv e integra 5 features de mercado."""
    print("[CHART] Integrando ODDS de mercado...")
    
    try:
        odds_df = pd.read_csv('csv/csvDescargados/live_odds_cache.csv')
        print(f"  [OK] live_odds_cache.csv: {odds_df.shape}")
        
        if 'jornada' not in odds_df.columns:
            print("  [WARN] No existe columna 'jornada' en odds_df, abortando integración de odds")
            df['odds_prob_win'] = 0.33
            df['odds_prob_loss'] = 0.33
            df['odds_expected_goals_against'] = 0.33
            df['odds_is_favored'] = 0
            df['odds_market_confidence'] = 0.33
            return df
        
        if 'jornada' not in df.columns:
            print("  [WARN] No existe columna 'jornada' en df principal, abortando integración de odds")
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
            df = df.drop(columns=['equipo_propio_norm', 'equipo_rival_norm'], errors='ignore')
            return df
        
        # Procesar odds: usar merge en lugar de loops con .loc[] (más eficiente y evita conflictos)
        local_count = 0
        away_count = 0
        
        # Para locales
        local_df = df[df['local'] == 1].copy()
        local_merged = local_df.merge(
            odds_df[['jornada', 'home_norm', 'p_home', 'p_away', 'p_draw']],
            left_on=['jornada', 'equipo_propio_norm'],
            right_on=['jornada', 'home_norm'],
            how='left'
        )
        
        # Asignar valores para locales
        mask_local = local_merged['p_home'].notna()
        df.loc[local_df[mask_local].index, 'odds_prob_win'] = local_merged.loc[mask_local, 'p_home'].values
        df.loc[local_df[mask_local].index, 'odds_prob_loss'] = local_merged.loc[mask_local, 'p_away'].values
        df.loc[local_df[mask_local].index, 'odds_expected_goals_against'] = (local_merged.loc[mask_local, 'p_away'].values * 2.5)
        df.loc[local_df[mask_local].index, 'odds_is_favored'] = (local_merged.loc[mask_local, 'p_home'] > local_merged.loc[mask_local, 'p_away']).astype(int).values
        
        # odds_market_confidence para locales
        for i, row in local_merged[mask_local].iterrows():
            probs = [row['p_home'], row['p_draw'], row['p_away']]
            df.loc[i, 'odds_market_confidence'] = max(probs) - min(probs)
        local_count = mask_local.sum()
        
        # Para visitantes
        away_df = df[df['local'] == 0].copy()
        away_merged = away_df.merge(
            odds_df[['jornada', 'away_norm', 'p_home', 'p_away', 'p_draw']],
            left_on=['jornada', 'equipo_rival_norm'],
            right_on=['jornada', 'away_norm'],
            how='left'
        )
        
        # Asignar valores para visitantes
        mask_away = away_merged['p_away'].notna()
        df.loc[away_df[mask_away].index, 'odds_prob_win'] = away_merged.loc[mask_away, 'p_away'].values
        df.loc[away_df[mask_away].index, 'odds_prob_loss'] = away_merged.loc[mask_away, 'p_home'].values
        df.loc[away_df[mask_away].index, 'odds_expected_goals_against'] = (away_merged.loc[mask_away, 'p_home'].values * 2.5)
        df.loc[away_df[mask_away].index, 'odds_is_favored'] = (away_merged.loc[mask_away, 'p_away'] > away_merged.loc[mask_away, 'p_home']).astype(int).values
        
        # odds_market_confidence para visitantes
        for i, row in away_merged[mask_away].iterrows():
            probs = [row['p_home'], row['p_draw'], row['p_away']]
            df.loc[i, 'odds_market_confidence'] = max(probs) - min(probs)
        away_count = mask_away.sum()
                
                df.loc[idx, 'odds_prob_win'] = p_win
                df.loc[idx, 'odds_prob_loss'] = p_loss
                df.loc[idx, 'odds_expected_goals_against'] = p_loss * 2.5
                df.loc[idx, 'odds_is_favored'] = 1 if p_win > p_loss else 0
                df.loc[idx, 'odds_market_confidence'] = max(p_win, match.iloc[0]['p_draw'], p_loss) - min(p_win, match.iloc[0]['p_draw'], p_loss)
                away_count += 1
        
        df = df.drop(columns=['equipo_propio_norm', 'equipo_rival_norm'], errors='ignore')
        
        print(f"  [OK] {local_count} registros locales con odds encontrados")
        print(f"  [OK] {away_count} registros visitantes con odds encontrados")
        print(f"  [OK] FEATURES ODDS INTEGRADOS: odds_prob_win, odds_prob_loss, odds_xga, odds_is_favored, odds_market_confidence\n")
        return df
        
    except Exception as e:
        print(f"  [ERROR] Detalle del error: {type(e).__name__}: {e}")
        if 'odds_prob_win' not in df.columns:
            df['odds_prob_win'] = 0.33
            df['odds_prob_loss'] = 0.33
            df['odds_expected_goals_against'] = 0.33
            df['odds_is_favored'] = 0
            df['odds_market_confidence'] = 0.33
        return df


def crear_features_defensivos_basicos(df):
    """Features defensivos: Tackles, Interceptions, Clearances, Duels"""
    print("=" * 80)
    print("FEATURES DEFENSIVOS")
    print("=" * 80)
    
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']
    
    # Features defensivos detectados del CSV - columnas con minúsculas
    df_specs = [
        ("entradas", 0, "tackles"),
        ("intercepciones", 0, "intercepts"),
        ("despejes", 0, "clearances"),
        ("duelos", 0, "duels"),
        ("duelos_ganados", 0, "duels_won"),
        ("duelos_perdidos", 0, "duels_lost"),
        ("duelos_aereos", 0, "aerial_duels"),
        ("duelos_aereos_ganados", 0, "aerial_won"),
        ("duelos_aereos_perdidos", 0, "aerial_lost"),
        ("bloques", 0, "blocks"),
    ]
    
    for col, default, prefix in df_specs:
        if col in df.columns:
            df, _ = crear_features_temporales(df, col, vc, vl, ve, crear_lag=True, default_value=default, prefix=prefix, verbose=True)
    
    return df


def crear_features_form(df):
    print("=" * 80)
    print("FEATURES FORM (PUNTOS FANTASY)")
    print("=" * 80)
    
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']
    
    if CONFIG['columna_objetivo'] in df.columns:
        df, _ = crear_features_temporales(df, CONFIG['columna_objetivo'], vc, vl, ve, crear_lag=True, 
                                          default_value=1.0, prefix="pf", verbose=True)
    
    return df


def crear_features_disponibilidad(df):
    print("=" * 80)
    print("FEATURES DISPONIBILIDAD")
    print("=" * 80)
    
    vc, vl, ve = CONFIG['ventana_corta'], CONFIG['ventana_larga'], CONFIG['ventana_extra']
    
    df["min_partido"] = pd.to_numeric(df["min_partido"], errors='coerce').fillna(45)
    df["minutes_pct_temp"] = (df["min_partido"] / 90).fillna(0).clip(0, 1)
    
    df, _ = crear_features_temporales(df, "minutes_pct_temp", vc, vl, ve, crear_lag=False, default_value=0, prefix="minutes_pct", verbose=True)
    
    if "titular" in df.columns:
        df["starter_pct"] = (df["titular"] == "Si").astype(int)
        df, _ = crear_features_temporales(df, "starter_pct", vc, vl, ve, crear_lag=False, default_value=0, prefix="starter_pct", verbose=True)
    
    df = df.drop(columns=["minutes_pct_temp"])
    return df


def crear_features_contexto(df):
    print("=" * 80)
    print("FEATURES CONTEXTO")
    print("=" * 80)
    
    if "local" in df.columns:
        df["is_home"] = (df["local"] == "Si").astype(int)
    else:
        df["is_home"] = 0
    
    print("✅ Home/Away (is_home)\n")
    return df


def crear_features_rival(df):
    print("=" * 80)
    print("FEATURES RIVAL (HISTÓRICOS CON SHIFT - SIN LEAKAGE)")
    print("=" * 80)

    # Calcular opp_form desde GF/GC reales (no desde racha de victorias)
    # Normalizado a [0, 1]: 0.5 neutro, >0.5 rival en buena forma, <0.5 rival en mala forma
    if "gf_rival" in df.columns and "gc_rival" in df.columns:
        gf = pd.to_numeric(df["gf_rival"], errors='coerce').fillna(0)
        gc = pd.to_numeric(df["gc_rival"], errors='coerce').fillna(0)
        total = (gf + gc).clip(lower=1)
        df["opp_form_raw"] = np.clip(((gf - gc) / total + 1) / 2, 0.0, 1.0)
        print("   Calculando opp_form desde GF/GC reales del rival")
    else:
        print("   ERROR: sin columnas gf_rival/gc_rival en el CSV")
        df["opp_form_raw"] = 0.5

    # SAFE: datos del rival en partidos ANTERIORES (shift evita leakage)
    rival_specs = [
        ("gf_rival",     0.0, "opp_gf"),
        ("gc_rival",     0.0, "opp_gc"),
        ("opp_form_raw", 0.5, "opp_form"),
    ]

    for col, default, prefix in rival_specs:
        if col not in df.columns:
            continue

        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(default)

        if df[col].nunique() <= 1:
            print(f"   AVISO: {col} es constante ({df[col].iloc[0]:.3f})")

        if "equipo_propio" in df.columns:
            df[f'{col}_shifted'] = df.groupby('equipo_propio')[col].shift(1)
        else:
            df[f'{col}_shifted'] = df[col].shift(1)

        df[f'{col}_shifted'] = df[f'{col}_shifted'].fillna(default)

        df[f'{prefix}_roll3'] = df[f'{col}_shifted'].rolling(3, min_periods=1).mean()
        df[f'{prefix}_ewma3'] = df[f'{col}_shifted'].ewm(span=3, adjust=False).mean()

        df[f'{prefix}_roll5'] = df[f'{col}_shifted'].rolling(5, min_periods=1).mean()
        df[f'{prefix}_ewma5'] = df[f'{col}_shifted'].ewm(span=5, adjust=False).mean()

        df[f'{prefix}_roll7'] = df[f'{col}_shifted'].rolling(7, min_periods=1).mean()
        df[f'{prefix}_ewma7'] = df[f'{col}_shifted'].ewm(span=7, adjust=False).mean()

        df = df.drop(columns=[f'{col}_shifted'], errors='ignore')

        print(f"   OK {col} → {prefix}_roll3/5/7 + ewma3/5/7 (shift por equipo, sin leakage)")

    print()
    return df


def crear_features_probabilisticas(df):
    """Features probabilísticas del mercado de apuestas (si existen)"""
    print("=" * 80)
    print("FEATURES PROBABILÍSTICAS")
    print("=" * 80)
    
    if "p_win_propio" in df.columns:
        df["p_win_propio"] = pd.to_numeric(df["p_win_propio"], errors='coerce').fillna(0.5)
        print("✅ p_win_propio")
    
    if "p_loss_propio" in df.columns:
        df["p_loss_propio"] = pd.to_numeric(df["p_loss_propio"], errors='coerce').fillna(0.3)
        print("✅ p_loss_propio")
    
    print()
    return df


def crear_features_avanzados(df):
    """Features avanzados AGRESIVOS específicos para defensas"""
    print("=" * 80)
    print("FEATURES AVANZADOS (DEFENSIVOS)")
    print("=" * 80)
    
    df = df.copy()
    nuevos_features = []
    
    # Eficiencia defensiva: tackles + interceptions por duelo
    if "tackles_roll5" in df.columns and "duels_roll5" in df.columns:
        df["defensive_efficiency"] = (df["tackles_roll5"] + df.get("intercepts_roll5", 0)) / (df["duels_roll5"] + 1)
        nuevos_features.append("defensive_efficiency")
    
    # Actividad defensiva total (tackles + intercepts + clearances pesados)
    if "tackles_roll5" in df.columns or "intercepts_roll5" in df.columns:
        tackles = df.get("tackles_roll5", 0)
        intercepts = df.get("intercepts_roll5", 0)
        clearances = df.get("clearances_roll5", 0)
        df["defensive_activity"] = tackles + intercepts + (clearances * 0.7)
        nuevos_features.append("defensive_activity")
    
    # Tasa de victorias en duelos
    if "duels_won_roll5" in df.columns and "duels_roll5" in df.columns:
        df["duel_win_rate"] = df["duels_won_roll5"] / (df["duels_roll5"] + 1e-6)
        df["duel_win_rate"] = df["duel_win_rate"].clip(0, 1).fillna(0)
        nuevos_features.append("duel_win_rate")
    
    # Tasa de victorias en duelos aéreos
    if "aerial_won_roll5" in df.columns and "aerial_duels_roll5" in df.columns:
        df["aerial_duel_win_rate"] = df["aerial_won_roll5"] / (df["aerial_duels_roll5"] + 1e-6)
        df["aerial_duel_win_rate"] = df["aerial_duel_win_rate"].clip(0, 1).fillna(0)
        nuevos_features.append("aerial_duel_win_rate")
    
    # Forma defensiva normalizada
    if "pf_roll5" in df.columns and "pf_roll3" in df.columns:
        df["form_ratio"] = (df["pf_roll3"] + 0.1) / (df["pf_roll5"] + 0.1)
        df["form_ratio"] = df["form_ratio"].clip(0.5, 2.0).fillna(1.0)
        nuevos_features.append("form_ratio")
    
    # Minutos x Forma
    if "minutes_pct_ewma5" in df.columns and "pf_roll5" in df.columns:
        df["minutes_form_combo"] = (df["minutes_pct_ewma5"] * df["pf_roll5"] / 10).fillna(0)
        nuevos_features.append("minutes_form_combo")
    
    # Presión defensiva: Tackles + bloques por 90 minutos normalizados
    if "tackles_roll5" in df.columns:
        blocks = df.get("blocks_roll5", 0)
        df["defensive_pressure"] = (df["tackles_roll5"] + blocks * 0.8) / 5  # normalizado a ventana
        nuevos_features.append("defensive_pressure")
    
    # Competitividad en tierra: Ganancia/pérdida de duelos terrestres
    if "duels_won_roll5" in df.columns and "duels_lost_roll5" in df.columns:
        df["duel_balance"] = (df["duels_won_roll5"] - df.get("duels_lost_roll5", 0))
        nuevos_features.append("duel_balance")
    
    # Competitividad aérea: Ganancia/pérdida de duelos aéreos
    if "aerial_won_roll5" in df.columns and "aerial_lost_roll5" in df.columns:
        df["aerial_balance"] = (df["aerial_won_roll5"] - df.get("aerial_lost_roll5", 0))
        nuevos_features.append("aerial_balance")
    
    # Feature multiplicativo: Actividad x Forma
    if "defensive_activity" in df.columns and "pf_roll5" in df.columns:
        df["defensive_form_power"] = (df["defensive_activity"] / 10 * df["pf_roll5"] / 10).fillna(0)
        nuevos_features.append("defensive_form_power")
    
    # Consistencia defensiva: Tackles con variabilidad baja = consistencia
    if "tackles_roll5" in df.columns and "tackles_ewma5" in df.columns:
        df["tackles_variance_diff"] = (df["tackles_roll5"] - df["tackles_ewma5"]).abs()
        df["defensive_consistency"] = 1 / (df["tackles_variance_diff"] + 1)
        nuevos_features.append("defensive_consistency")
    
    # Disponibilidad x Disponibilidad anterior = momentum
    if "minutes_pct_roll5" in df.columns and "minutes_pct_roll3" in df.columns:
        df["availability_momentum"] = (df["minutes_pct_roll3"] / (df["minutes_pct_roll5"] + 0.1)).clip(0.5, 2.0).fillna(1.0)
        nuevos_features.append("availability_momentum")
    
    df = df.fillna(0).replace([np.inf, -np.inf], 0)
    print(f"   ✅ {len(nuevos_features)} features avanzados AGRESIVOS agregados\n")
    
    return df


def integrar_roles(df):
    print("=" * 80)
    print("ROLES (FBRef)")
    print("=" * 80)
    
    df = enriquecer_dataframe_con_roles(df, position="DF", columna_roles="roles")
    df = crear_features_interaccion_roles(df, position="DF", columna_objetivo=CONFIG['columna_objetivo'])
    print()
    return df


def aplicar_mejoras(df):
    print("=" * 80)
    print("MEJORAS DE FEATURES")
    print("=" * 80)
    
    antes = len(df.columns)
    df = eliminar_features_ruido(df, position="DF", verbose=True)
    print(f"Sin ruido: {antes} → {len(df.columns)}")
    
    antes = len(df.columns)
    df = crear_features_fantasy_defensivos(df, verbose=True)
    print(f"Finales: {antes} → {len(df.columns)}\n")
    
    return df


def aplicar_feature_selection(X, y):
    print("=" * 80)
    print(" SELECCIÓN FEATURES (THRESHOLD 0.02)")
    print("=" * 80 + "\n")
    
    features_validos, df_corr = seleccionar_features_por_correlacion(X, y, target_name=CONFIG['columna_objetivo'], threshold=0.02, verbose=True)
    
    df_corr.to_csv(DIRECTORIO_CSVS / "feature_correlations_detailed.csv", index=False)
    print(f" Features seleccionados: {len(features_validos)}\n")
    return X[features_validos], df_corr


def definir_variables_finales(df):
    print("=" * 80)
    print("VARIABLES FINALES (DEFENSAS - SIN DATA LEAKAGE)")
    print("=" * 80)
    
    variables = [
        # ============================================================
        # DEFENSIVE STATS (VENTANA 5 - HISTÓRICOS, SIN LEAKAGE)
        # ============================================================
        "tackles_roll5", "tackles_ewma5",
        "intercepts_roll5", "intercepts_ewma5",
        "clearances_roll5", "clearances_ewma5",
        "duels_roll5", "duels_ewma5",
        "duels_won_roll5", "duels_won_ewma5",
        "duels_lost_roll5", "duels_lost_ewma5",
        "aerial_duels_roll5", "aerial_duels_ewma5",
        "aerial_won_roll5", "aerial_won_ewma5",
        "aerial_lost_roll5", "aerial_lost_ewma5",
        "blocks_roll5", "blocks_ewma5",
        
        # ============================================================
        # FORM (VENTANA 5 - HISTÓRICO CON SHIFT)
        # ============================================================
        "pf_roll5", "pf_ewma5",
        
        # ============================================================
        # AVAILABILITY (VENTANA 5 - HISTÓRICO)
        # ============================================================
        "minutes_pct_roll5", "minutes_pct_ewma5",
        "starter_pct_roll5", "starter_pct_ewma5",
        
        # ============================================================
        # CONTEXT & ODDS (MERCADO PRE-PARTIDO)
        # ============================================================
        "is_home",
        "odds_prob_win",
        "odds_prob_loss",
        "odds_expected_goals_against",
        "odds_is_favored",
        "odds_market_confidence",
        
        # ============================================================
        # RIVAL STATS (HISTÓRICOS - PARTIDOS ANTERIORES + SHIFT)
        # ============================================================
        "opp_gf_roll5", "opp_gf_ewma5",          # Goles a favor del rival (pasado)
        "opp_gc_roll5", "opp_gc_ewma5",          # Goles en contra del rival (pasado)
        "opp_form_roll5", "opp_form_ewma5",      # Forma del rival (pasado)
        
        # ============================================================
        # ROLES INTERACTION (FBRef - DF SPECIFIC, HISTÓRICO)
        # ============================================================
        "elite_entradas_interact", 
        "elite_intercepciones_interact", 
        "elite_despejes_interact",
        "num_roles_criticos",      # Solo este feature de roles
        
        # ============================================================
        # FANTASY FEATURES (DEFENSIVOS - HISTÓRICOS SIN LEAKAGE)
        # ============================================================
        # ✅ SOLO: def_actions_ewma5 (usa shift + ewm)
        # ❌ REMOVIDOS: defensive_actions_total, def_actions_per_90 (sin shift previo = LEAKAGE)
        "def_actions_ewma5",
        
        # ============================================================
        # ADVANCED FEATURES (DEFENSIVOS AGRESIVOS - SIN LEAKAGE)
        # ============================================================
        "defensive_efficiency", 
        "defensive_activity", 
        "duel_win_rate",
        "aerial_duel_win_rate",
        "form_ratio", 
        "minutes_form_combo",
        "defensive_pressure",
        "duel_balance",
        "aerial_balance",
        "defensive_form_power",
        "defensive_consistency",
        "availability_momentum",
    ]
    
    variables = [v for v in variables if v in df.columns]
    
    print(f" {len(variables)} variables (SIN DATA LEAKAGE - RIVAL HISTÓRICO)\n")
    return variables


def entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables):
    resultados_finales = {}
    lista_resultados = []
    
    print(" Random Forest...")
    rf_params = {
        'n_estimators': [200, 300, 400],
        'max_depth': [10, 20, 30, ],
        'min_samples_split': [2, 3, 5, 7],
        'min_samples_leaf': [ 2, 3, 4, 5],
        'max_features': ['sqrt', 'log2']
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
    resultados_finales['RF'] = {'mae': mae_rf, 'rmse': rmse_rf, 'spearman': spearman_rf, 'modelo': rf_best, 'params': rf_gs.best_params_, 'cv_score': rf_gs.best_score_}
    lista_resultados.append({'Model': 'RF', 'MAE': mae_rf, 'RMSE': rmse_rf, 'Spearman': spearman_rf, 'Best_Params': str(rf_gs.best_params_)})
    
    fi_rf = extraer_feature_importance(rf_best, X_train, variables)
    if fi_rf is not None:
        fi_rf.to_csv(DIRECTORIO_CSVS / "feature_importance_rf.csv", index=False)
        visualizar_feature_importance(fi_rf, "Random Forest - Top 20", "01_feature_importance_rf.png", 20)
    
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
    resultados_finales['XGB'] = {'mae': mae_xgb, 'rmse': rmse_xgb, 'spearman': spearman_xgb, 'modelo': xgb_best, 'params': xgb_gs.best_params_, 'cv_score': xgb_gs.best_score_}
    lista_resultados.append({'Model': 'XGB', 'MAE': mae_xgb, 'RMSE': rmse_xgb, 'Spearman': spearman_xgb, 'Best_Params': str(xgb_gs.best_params_)})
    
    fi_xgb = extraer_feature_importance(xgb_best, X_train, variables)
    if fi_xgb is not None:
        fi_xgb.to_csv(DIRECTORIO_CSVS / "feature_importance_xgb.csv", index=False)
        visualizar_feature_importance(fi_xgb, "XGBoost - Top 20", "02_feature_importance_xgb.png", 20)
    
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
    resultados_finales['Ridge'] = {'mae': mae_ridge, 'rmse': rmse_ridge, 'spearman': spearman_ridge, 'modelo': ridge_best, 'params': ridge_gs.best_params_, 'cv_score': ridge_gs.best_score_}
    lista_resultados.append({'Model': 'Ridge', 'MAE': mae_ridge, 'RMSE': rmse_ridge, 'Spearman': spearman_ridge, 'Best_Params': str(ridge_gs.best_params_)})
    
    fi_ridge = extraer_feature_importance(ridge_best, X_train, variables)
    if fi_ridge is not None:
        fi_ridge.to_csv(DIRECTORIO_CSVS / "feature_importance_ridge.csv", index=False)
        visualizar_feature_importance(fi_ridge, "Ridge - Top 20", "03_feature_importance_ridge.png", 20)
    
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
    resultados_finales['ElasticNet'] = {'mae': mae_elastic, 'rmse': rmse_elastic, 'spearman': spearman_elastic, 'modelo': elastic_best, 'params': elastic_gs.best_params_, 'cv_score': elastic_gs.best_score_}
    lista_resultados.append({'Model': 'ElasticNet', 'MAE': mae_elastic, 'RMSE': rmse_elastic, 'Spearman': spearman_elastic, 'Best_Params': str(elastic_gs.best_params_)})
    
    fi_elastic = extraer_feature_importance(elastic_best, X_train, variables)
    if fi_elastic is not None:
        fi_elastic.to_csv(DIRECTORIO_CSVS / "feature_importance_elastic.csv", index=False)
        visualizar_feature_importance(fi_elastic, "ElasticNet - Top 20", "04_feature_importance_elastic.png", 20)
    
    pd.DataFrame(lista_resultados).to_csv(DIRECTORIO_CSVS / "resultados_gridsearch_mejorado.csv", index=False)
    print(f"Resultados guardados\n")
    return resultados_finales


def main():
    print("\n" + "=" * 80)
    print("ENTRENAMIENTO DEFENSAS - VERSIÓN MEJORADA")
    print("=" * 80 + "\n")
    
    df = cargar_datos()
    df = diagnosticar_y_limpiar(df)
    df = cargar_y_procesar_odds(df)
    df = preparar_basicos(df)
    
    print("=" * 80)
    print("INGENIERÍA DE FEATURES")
    print("=" * 80 + "\n")
    df = crear_features_defensivos_basicos(df)
    df = crear_features_form(df)
    df = crear_features_disponibilidad(df)
    df = crear_features_contexto(df)
    df = crear_features_rival(df)
    df = crear_features_probabilisticas(df)
    
    print("=" * 80)
    print("MEJORAS ADICIONALES")
    print("=" * 80 + "\n")
    df = integrar_roles(df)
    df = crear_features_avanzados(df)
    df = aplicar_mejoras(df)
    
    variables = definir_variables_finales(df)
    df_train = df.dropna(subset=[CONFIG['columna_objetivo']])
    df_train = df_train[df_train[CONFIG['columna_objetivo']] > 0]
    X = df_train[variables].fillna(0)
    y = df_train[CONFIG['columna_objetivo']]
    
    print(f"Antes: {X.shape[1]} features")
    X, corr_analysis = aplicar_feature_selection(X, y)
    variables = X.columns.tolist()
    print(f"Después: {X.shape[1]} features\n")
    
    split_idx = int(len(X) * (1 - CONFIG['test_size']))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Train: {len(X_train)}, Test: {len(X_test)}\n")
    
    print("=" * 80)
    print("ENTRENAMIENTO GRIDSEARCH")
    print("=" * 80 + "\n")
    
    resultados = entrenar_modelos_gridsearch(X_train, X_test, y_train, y_test, variables)
    
    mejor_modelo = min(resultados.items(), key=lambda x: x[1]['mae'])
    mejor_nombre = mejor_modelo[0]
    mejor_metrics = mejor_modelo[1]
    
    print("RANKING MODELOS:\n")
    for i, (nombre, metrics) in enumerate(sorted(resultados.items(), key=lambda x: x[1]['mae']), 1):
        print(f"{i}. {nombre:12s} MAE: {metrics['mae']:.4f} RMSE: {metrics['rmse']:.4f} Spearman: {metrics['spearman']:.4f}")
    
    print("\n" + "=" * 80)
    print(f" MEJOR: {mejor_nombre}")
    print("=" * 80)
    print(f"MAE: {mejor_metrics['mae']:.4f}")
    print(f"RMSE: {mejor_metrics['rmse']:.4f}")
    print(f"Spearman: {mejor_metrics['spearman']:.4f}")
    print(f"CV Score: {mejor_metrics['cv_score']:.4f}")
    print("\nHiperparámetros:")
    for k, v in mejor_metrics['params'].items():
        print(f"  {k}: {v}")
    
    with open(DIRECTORIO_MODELOS / f"best_model_{mejor_nombre}.pkl", 'wb') as f:
        pickle.dump(mejor_metrics['modelo'], f)
    
    with open(DIRECTORIO_MODELOS / f"best_model_params_{mejor_nombre}.json", 'w') as f:
        json.dump(mejor_metrics['params'], f, indent=2)
    
    print(f"\n Modelo guardado: {DIRECTORIO_MODELOS / f'best_model_{mejor_nombre}.pkl'}")
    print(f" Parámetros: {DIRECTORIO_MODELOS / f'best_model_params_{mejor_nombre}.json'}")
    
    # Guardar Random Forest si existe
    if 'RF' in resultados:
        rf_metrics = resultados['RF']
        with open(DIRECTORIO_MODELOS / "best_model_RF.pkl", 'wb') as f:
            pickle.dump(rf_metrics['modelo'], f)
        
        with open(DIRECTORIO_MODELOS / "best_model_params_RF.json", 'w') as f:
            json.dump(rf_metrics['params'], f, indent=2)
        
        print(f"\n[RF] Modelo Random Forest guardado: {DIRECTORIO_MODELOS / 'best_model_RF.pkl'}")
        print(f"[RF] MAE: {rf_metrics['mae']:.4f}, RMSE: {rf_metrics['rmse']:.4f}, Spearman: {rf_metrics['spearman']:.4f}")


if __name__ == "__main__":
    main()

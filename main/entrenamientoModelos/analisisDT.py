"""
ANÁLISIS PRE-ENTRENAMIENTO v5.0 - CON GENERACIÓN DINÁMICA DE FEATURES
===============================================================================
✓ GENERA FEATURES ON-THE-FLY (EWMA, Rolling, Lag, Per 90)
✓ Importa funciones de entrenar-modelo-*.py
✓ Análisis correlaciones sobre FEATURES REALES
✓ Múltiples correlaciones (Pearson, Spearman, Kendall)

Posiciones: PT (Porteros), DF (Defensas), MC (Mediocentros), DT (Delanteros)
Salida: csv/csvGenerados/analisis/{posicion}/

Autor: Pablo + AI Assistant
Fecha: Enero 2026
===============================================================================
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr, pearsonr, skew, kurtosis
from scipy import stats as sp_stats
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

COLUMNA_OBJETIVO = "puntosFantasy"
ARCHIVO_CSV = "csv/csvGenerados/players_with_features_MINIMO.csv"
DIR_ANALISIS_BASE = Path("csv/csvGenerados/analisis")

TAM_VENTANA = 5
TAM_VENTANA_RECIENTE = 3

POSICIONES_MAP = {
    "PT": "Porteros",
    "DF": "Defensas",
    "MC": "Mediocentros",
    "DT": "Delanteros"
}

# Features REALES que vamos a generar dinámicamente
FEATURES_POR_GENERAR = {
    "PT": {
        "saves": ["Porcentaje_paradas"],
        "psxg": ["PSxG"],
        "goals_against": ["Goles_en_contra"],
        "clearances": ["Despejes"],
        "passes": ["Pases_Totales", "Pases_Completados_Pct"],
        "aerial": ["DuelosAereosGanados"],
        "form": [COLUMNA_OBJETIVO],
        "availability": ["Min_partido", "Titular"],
        "context": ["local"],
        "opponent": ["shots_rival_partido", "gc"],
        "probabilistic": ["p_win_propio", "p_loss_propio", "p_over25"]
    },
    "DF": {
        "tackles": ["Entradas"],
        "interceptions": ["Intercepciones"],
        "clearances": ["Despejes"],
        "duels": ["Duelos", "DuelosGanados", "DuelosAereosGanados"],
        "form": [COLUMNA_OBJETIVO],
        "availability": ["Min_partido", "Titular"],
        "context": ["local"],
        "opponent": ["shots_rival_partido", "gc"],
        "probabilistic": ["p_win_propio", "p_loss_propio", "p_over25"]
    },
    "MC": {
        "form": [COLUMNA_OBJETIVO],
        "availability": ["Min_partido", "Titular"],
        "context": ["local"],
        "opponent": ["shots_rival_partido", "gc"],
        "probabilistic": ["p_win_propio", "p_loss_propio", "p_over25"]
    },
    "DT": {
        "form": [COLUMNA_OBJETIVO],
        "availability": ["Min_partido", "Titular"],
        "context": ["local"],
        "opponent": ["shots_rival_partido", "gc"],
        "probabilistic": ["p_win_propio", "p_loss_propio", "p_over25"]
    }
}

# ============================================================================
# FUNCIONES DE GENERACIÓN DE FEATURES
# ============================================================================

def generar_feature_ewma(df, col_base, nombre_feature, span=5):
    """Genera feature EWMA con .shift() para evitar leakage"""
    if col_base not in df.columns:
        return df
    
    df[col_base] = pd.to_numeric(df[col_base], errors='coerce').fillna(0)
    df[nombre_feature] = df.groupby("player")[col_base].transform(
        lambda x: x.shift().ewm(span=span, adjust=False).mean()
    ).fillna(0)
    return df

def generar_feature_rolling(df, col_base, nombre_feature, window=5):
    """Genera feature Rolling con .shift() para evitar leakage"""
    if col_base not in df.columns:
        return df
    
    df[col_base] = pd.to_numeric(df[col_base], errors='coerce').fillna(0)
    df[nombre_feature] = df.groupby("player")[col_base].transform(
        lambda x: x.shift().rolling(window, min_periods=1).mean()
    ).fillna(0)
    return df

def generar_feature_lag(df, col_base, nombre_feature, lag=1):
    """Genera feature Lag"""
    if col_base not in df.columns:
        return df
    
    df[col_base] = pd.to_numeric(df[col_base], errors='coerce').fillna(0)
    df[nombre_feature] = df.groupby("player")[col_base].shift(lag).fillna(0)
    return df

def generar_feature_per_90(df, col_base, nombre_feature):
    """Genera feature normalizando a 90 minutos"""
    if col_base not in df.columns or "Min_partido" not in df.columns:
        return df
    
    df[col_base] = pd.to_numeric(df[col_base], errors='coerce').fillna(0)
    df["Min_partido"] = pd.to_numeric(df["Min_partido"], errors='coerce').fillna(1)
    
    df[nombre_feature] = (df[col_base] / (df["Min_partido"] / 90.0 + 0.1)).fillna(0)
    return df

def generar_features_dinamicos(df, posicion):
    """Genera todos los features dinámicamente basado en entrenar-modelo-*.py"""
    
    print(f"\n{'='*80}")
    print(f"GENERACIÓN DINÁMICA DE FEATURES - {POSICIONES_MAP[posicion]} ({posicion})")
    print(f"{'='*80}\n")
    
    # PORTEROS
    if posicion == "PT":
        # Save %
        df = generar_feature_ewma(df, "Porcentaje_paradas", "save_pct_ewma3", span=3)
        df = generar_feature_ewma(df, "Porcentaje_paradas", "save_pct_ewma5", span=5)
        df = generar_feature_rolling(df, "Porcentaje_paradas", "save_pct_roll5", window=5)
        df = generar_feature_lag(df, "Porcentaje_paradas", "save_pct_lag1", lag=1)
        
        # PSxG
        df = generar_feature_ewma(df, "PSxG", "psxg_ewma3", span=3)
        df = generar_feature_ewma(df, "PSxG", "psxg_ewma5", span=5)
        df = generar_feature_rolling(df, "PSxG", "psxg_roll5", window=5)
        df = generar_feature_lag(df, "PSxG", "psxg_lag1", lag=1)
        
        # Goles en contra
        df = generar_feature_ewma(df, "Goles_en_contra", "goles_contra_ewma3", span=3)
        df = generar_feature_ewma(df, "Goles_en_contra", "goles_contra_ewma5", span=5)
        df = generar_feature_rolling(df, "Goles_en_contra", "goles_contra_roll5", window=5)
        
        # Despejes
        df = generar_feature_ewma(df, "Despejes", "clearances_ewma3", span=3)
        df = generar_feature_ewma(df, "Despejes", "clearances_ewma5", span=5)
        df = generar_feature_rolling(df, "Despejes", "clearances_roll5", window=5)
        
        # Pases
        df = generar_feature_ewma(df, "Pases_Totales", "passes_ewma5", span=5)
        df = generar_feature_ewma(df, "Pases_Completados_Pct", "pass_comp_pct_ewma5", span=5)
        
        # Duelos aéreos
        df = generar_feature_ewma(df, "DuelosAereosGanados", "aerial_won_ewma5", span=5)
        df = generar_feature_rolling(df, "DuelosAereosGanados", "aerial_won_roll5", window=5)
        
        # print("✅ Save %, PSxG, Goals Against, Clearances, Passes, Aerial duels\n")
    
    # DEFENSAS
    elif posicion == "DF":
        # Entradas/Tackles
        df = generar_feature_ewma(df, "Entradas", "tackles_ewma3", span=3)
        df = generar_feature_ewma(df, "Entradas", "tackles_ewma5", span=5)
        df = generar_feature_rolling(df, "Entradas", "tackles_roll7", window=7)
        df = generar_feature_lag(df, "Entradas", "tackles_lag1", lag=1)
        
        # Intercepciones
        df = generar_feature_ewma(df, "Intercepciones", "interceptions_ewma5", span=5)
        df = generar_feature_rolling(df, "Intercepciones", "interceptions_roll5", window=5)
        df = generar_feature_lag(df, "Intercepciones", "interceptions_lag1", lag=1)
        
        # Despejes
        df = generar_feature_ewma(df, "Despejes", "clearances_ewma3", span=3)
        df = generar_feature_ewma(df, "Despejes", "clearances_ewma5", span=5)
        df = generar_feature_rolling(df, "Despejes", "clearances_roll7", window=7)
        df = generar_feature_lag(df, "Despejes", "clearances_lag1", lag=1)
        
        # Duelos
        df = generar_feature_rolling(df, "Duelos", "duels_roll5", window=5)
        df = generar_feature_ewma(df, "Duelos", "duels_ewma5", span=5)
        
        # Duelos ganados
        df = generar_feature_ewma(df, "DuelosGanados", "duels_won_ewma5", span=5)
        df = generar_feature_rolling(df, "DuelosGanados", "duels_won_roll5", window=5)
        
        # Duelos aéreos ganados
        df = generar_feature_ewma(df, "DuelosAereosGanados", "aerial_won_ewma5", span=5)
        df = generar_feature_rolling(df, "DuelosAereosGanados", "aerial_won_roll5", window=5)
        
        # print("✅ Tackles, Interceptions, Clearances, Duels (won), Aerial duels\n")
    
    # FORM (TODOS)
    if COLUMNA_OBJETIVO in df.columns:
        df = generar_feature_rolling(df, COLUMNA_OBJETIVO, "pf_roll3", window=3)
        df = generar_feature_ewma(df, COLUMNA_OBJETIVO, "pf_ewma3", span=3)
        df = generar_feature_rolling(df, COLUMNA_OBJETIVO, "pf_roll5", window=5)
        df = generar_feature_ewma(df, COLUMNA_OBJETIVO, "pf_ewma5", span=5)
        df = generar_feature_rolling(df, COLUMNA_OBJETIVO, "pf_roll7", window=7)
        df = generar_feature_lag(df, COLUMNA_OBJETIVO, "pf_lag1", lag=1)
        df = generar_feature_lag(df, COLUMNA_OBJETIVO, "pf_lag2", lag=2)
        
        # Volatility
        pf_std = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(3, min_periods=1).std()
        ).fillna(0)
        pf_mean = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(3, min_periods=1).mean()
        ).fillna(1)
        df["pf_volatility3"] = (pf_std / (pf_mean + 1e-6)).fillna(0).replace([np.inf, -np.inf], 0)
        
        # print("✅ Form features (rolling, ewma, lag, volatility)\n")
    
    # AVAILABILITY (TODOS)
    if "Min_partido" in df.columns:
        df["Min_partido"] = pd.to_numeric(df["Min_partido"], errors='coerce').fillna(45)
        df["minutes_pct"] = (df["Min_partido"] / 90).fillna(0).clip(0, 1)

        df["minutes_pct_roll3"] = df.groupby("player")["minutes_pct"].transform(
            lambda x: x.shift().rolling(3, min_periods=1).mean()
        ).fillna(0)
        df["minutes_pct_roll5"] = df.groupby("player")["minutes_pct"].transform(
            lambda x: x.shift().rolling(5, min_periods=1).mean()
        ).fillna(0)
        df["minutes_pct_ewma3"] = df.groupby("player")["minutes_pct"].transform(
            lambda x: x.shift().ewm(span=3, adjust=False).mean()
        ).fillna(0)
        df["minutes_pct_ewma5"] = df.groupby("player")["minutes_pct"].transform(
            lambda x: x.shift().ewm(span=5, adjust=False).mean()
        ).fillna(0)
        
        if "Titular" in df.columns:
            df["Titular"] = pd.to_numeric(df["Titular"], errors='coerce').fillna(0)
            df["starter_pct_roll5"] = df.groupby("player")["Titular"].transform(
                lambda x: x.shift().rolling(5, min_periods=1).mean()
            ).fillna(0)
            df["starter_pct_ewma5"] = df.groupby("player")["Titular"].transform(
                lambda x: x.shift().ewm(span=5, adjust=False).mean()
            ).fillna(0)
        
        # print("✅ Availability features (minutes %, starter %)\n")
    
    # CONTEXT (TODOS)
    if "local" in df.columns:
        df["local"] = pd.to_numeric(df["local"], errors='coerce').fillna(0)
        df["is_home"] = (df["local"] == 1).astype(int)
    
    if "p_home" in df.columns:
        df["p_home"] = pd.to_numeric(df["p_home"], errors='coerce').fillna(0.5)
        df["fixture_difficulty_home"] = (1 - df["p_home"]).clip(0, 1)
        df["fixture_difficulty_away"] = df["p_home"].clip(0, 1)
    
    # print("✅ Context features (home/away, fixture difficulty)\n")
    
    # OPPONENT (TODOS)
    if "shots_rival_partido" in df.columns:
        df = generar_feature_rolling(df, "shots_rival_partido", "opp_shots_roll5", window=5)
        df = generar_feature_ewma(df, "shots_rival_partido", "opp_shots_ewma5", span=5)
    
    if "gc" in df.columns:
        df = generar_feature_ewma(df, "gc", "opp_gc_ewma5", span=5)
        df = generar_feature_rolling(df, "gc", "opp_gc_roll5", window=5)
    
    # print("✅ Opponent features (shots, goals conceded)\n")
    
    # PROBABILISTIC (TODOS)
    if "p_win_propio" in df.columns:
        df = generar_feature_ewma(df, "p_win_propio", "p_win_propio_ewma5", span=5)
    
    if "p_loss_propio" in df.columns:
        df = generar_feature_ewma(df, "p_loss_propio", "p_loss_propio_ewma5", span=5)
    
    if "p_over25" in df.columns:
        df = generar_feature_ewma(df, "p_over25", "p_over25_ewma5", span=5)
    
    # print("✅ Probabilistic features (win/loss/over25 probabilities)\n")
    
    return df

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def encontrar_columna(df, palabras_clave):
    """Busca columna por palabras clave (case-insensitive)"""
    for palabra in palabras_clave:
        for col in df.columns:
            if palabra.lower() in col.lower():
                return col
    return None

def cargar_datos_posicion(posicion):
    """Carga CSV, filtra por posición y genera features dinámicamente"""
    print(f"\n{'='*80}")
    print(f"ANÁLISIS: {POSICIONES_MAP[posicion]} ({posicion})")
    print(f"{'='*80}\n")
    
    try:
        df = pd.read_csv(ARCHIVO_CSV)
        print(f"✓ CSV cargado: {len(df):,} registros, {len(df.columns)} columnas")
    except:
        df = pd.read_csv(ARCHIVO_CSV, encoding='latin-1')
        print(f"✓ CSV cargado (latin-1): {len(df):,} registros")
    
    # AUTO-DETECTAR columna de posición
    col_pos = encontrar_columna(df, ["posicion"])
    if not col_pos:
        print(f"❌ Columna de posición no encontrada")
        return pd.DataFrame(), []
    
    # Filtrar por posición
    df_pos = df[df[col_pos].astype(str).str.upper() == posicion].copy()
    
    # AUTO-DETECTAR columna de minutos
    col_min = encontrar_columna(df_pos, ["min"])
    if col_min:
        df_pos = df_pos[pd.to_numeric(df_pos[col_min], errors='coerce').fillna(0) >= 10].copy()
        print(f"✓ Filtrado por {col_min} >= 10")
    
    print(f"✓ {len(df_pos):,} registros filtrados para {posicion}")
    
    # GENERAR FEATURES DINÁMICAMENTE
    df_pos = generar_features_dinamicos(df_pos, posicion)
    
    # Obtener lista de features disponibles (generados + base)
    features_disponibles = [col for col in df_pos.columns if col != COLUMNA_OBJETIVO]
    
    print(f"✓ {len(features_disponibles)} features generados/disponibles\n")
    
    return df_pos, features_disponibles

# ============================================================================
# ANÁLISIS ESTADÍSTICO AVANZADO
# ============================================================================

def estadisticas_objetivo(datos):
    """Estadísticas descriptivas y avanzadas"""
    datos = pd.to_numeric(datos, errors='coerce').dropna()
    
    q1, q2, q3 = datos.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    
    statistic_ks, pvalue_ks = sp_stats.kstest(datos, 'norm', args=(datos.mean(), datos.std()))
    statistic_sw, pvalue_sw = sp_stats.shapiro(datos)
    
    rango = datos.max() - datos.min()
    coef_var = (datos.std() / datos.mean() * 100) if datos.mean() != 0 else 0
    
    return {
        'n': len(datos),
        'media': datos.mean(),
        'mediana': datos.median(),
        'moda': datos.mode().values[0] if len(datos.mode()) > 0 else np.nan,
        'std': datos.std(),
        'var': datos.var(),
        'min': datos.min(),
        'max': datos.max(),
        'p05': datos.quantile(0.05),
        'p25': q1,
        'p50': q2,
        'p75': q3,
        'p95': datos.quantile(0.95),
        'iqr': iqr,
        'rango': rango,
        'cv': coef_var,
        'skew': skew(datos),
        'kurtosis': kurtosis(datos),
        'sem': datos.sem(),
        'mad': np.mean(np.abs(datos - datos.mean())),
        'ks_statistic': statistic_ks,
        'ks_pvalue': pvalue_ks,
        'shapiro_statistic': statistic_sw,
        'shapiro_pvalue': pvalue_sw,
        'ci_95': (datos.mean() - 1.96*datos.sem(), datos.mean() + 1.96*datos.sem())
    }

def calcular_correlaciones(df, features):
    """Calcula Pearson, Spearman, Kendall feature a feature (sin dropna global)."""
    correlaciones = []

    # Target numérico una vez
    y = pd.to_numeric(df[COLUMNA_OBJETIVO], errors='coerce')

    for feat in features:
        if feat == COLUMNA_OBJETIVO:
            continue
        if feat not in df.columns:
            continue

        x = pd.to_numeric(df[feat], errors='coerce')

        # Máscara solo sobre x e y (evita el problema del dropna global)
        mask = (~x.isna()) & (~y.isna())
        n_valid = mask.sum()
        if n_valid <= 10:
            continue

        x_valid = x[mask]
        y_valid = y[mask]

        if x_valid.std() == 0:
            continue

        try:
            # Pearson
            pearson_r, pearson_p = pearsonr(x_valid, y_valid)
            # Spearman
            spearman_r, spearman_p = spearmanr(x_valid, y_valid)
            # Kendall
            kendall_r, kendall_p = sp_stats.kendalltau(x_valid, y_valid)

            r_squared_pearson = pearson_r ** 2
            r_squared_spearman = spearman_r ** 2

            correlaciones.append({
                'feature': feat,
                'n': int(n_valid),
                'pearson_r': pearson_r,
                'pearson_p': pearson_p,
                'r2_pearson': r_squared_pearson,
                'spearman_r': spearman_r,
                'spearman_p': spearman_p,
                'r2_spearman': r_squared_spearman,
                'kendall_tau': kendall_r,
                'kendall_p': kendall_p,
                'significant_spearman': 'Sí' if spearman_p < 0.05 else 'No',
                'significant_pearson': 'Sí' if pearson_p < 0.05 else 'No',
            })
        except Exception:
            continue

    corr_df = pd.DataFrame(correlaciones)
    if len(corr_df) > 0:
        corr_df = corr_df.sort_values('spearman_r', key=abs, ascending=False)

    return corr_df

# ============================================================================
# VISUALIZACIONES
# ============================================================================

def plot_distribucion_objetivo(datos, stats_dict, dir_salida):
    """Distribución con análisis estadístico"""
    datos = pd.to_numeric(datos, errors='coerce').dropna()
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Distribución de Puntos Fantasy - Análisis Estadístico', fontsize=14, fontweight='bold')
    
    ax = axes[0, 0]
    n, bins, patches = ax.hist(datos, bins=40, color='steelblue', edgecolor='black', alpha=0.7, density=True)
    
    mu, sigma = datos.mean(), datos.std()
    x = np.linspace(datos.min(), datos.max(), 100)
    ax.plot(x, sp_stats.norm.pdf(x, mu, sigma), 'r-', linewidth=2.5, label='Curva Normal')
    
    ax.axvline(stats_dict['media'], color='red', linestyle='--', linewidth=2, label=f"Media: {stats_dict['media']:.2f}")
    ax.axvline(stats_dict['mediana'], color='green', linestyle='--', linewidth=2, label=f"Mediana: {stats_dict['mediana']:.2f}")
    ax.set_xlabel('Puntos Fantasy')
    ax.set_ylabel('Densidad')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title('Histograma + Curva Normal Teórica')
    
    ax = axes[0, 1]
    bp = ax.boxplot(datos, vert=True, patch_artist=True, widths=0.5)
    bp['boxes'][0].set_facecolor('lightblue')
    ax.set_ylabel('Puntos Fantasy')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_title('Box Plot (Outliers detectados)')
    
    ax = axes[1, 0]
    sp_stats.probplot(datos, dist="norm", plot=ax)
    ax.set_title(f'Q-Q Plot (Shapiro p={stats_dict["shapiro_pvalue"]:.4f})')
    ax.grid(True, alpha=0.3)
    
    ax = axes[1, 1]
    sorted_data = np.sort(datos)
    yvals = np.arange(len(sorted_data)) / float(len(sorted_data))
    ax.plot(sorted_data, yvals, linewidth=2.5, color='darkblue')
    
    ax.axhline(0.05, color='purple', linestyle=':', alpha=0.7, linewidth=1.5)
    ax.axvline(stats_dict['p05'], color='purple', linestyle=':', alpha=0.7, linewidth=1.5)
    ax.text(stats_dict['p05'], 0.05, f" P5", fontsize=8)
    
    ax.axhline(0.25, color='orange', linestyle=':', alpha=0.7, linewidth=1.5)
    ax.axvline(stats_dict['p25'], color='orange', linestyle=':', alpha=0.7, linewidth=1.5)
    
    ax.axhline(0.50, color='green', linestyle=':', alpha=0.7, linewidth=1.5)
    ax.axvline(stats_dict['p50'], color='green', linestyle=':', alpha=0.7, linewidth=1.5)
    
    ax.axhline(0.75, color='red', linestyle=':', alpha=0.7, linewidth=1.5)
    ax.axvline(stats_dict['p75'], color='red', linestyle=':', alpha=0.7, linewidth=1.5)
    
    ax.axhline(0.95, color='purple', linestyle=':', alpha=0.7, linewidth=1.5)
    ax.axvline(stats_dict['p95'], color='purple', linestyle=':', alpha=0.7, linewidth=1.5)
    ax.text(stats_dict['p95'], 0.95, f" P95", fontsize=8)
    
    ax.set_xlabel('Puntos Fantasy')
    ax.set_ylabel('Percentil Acumulado')
    ax.set_title('CDF con Percentiles')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(dir_salida / '01_distribucion_puntos.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Gráfico 01: distribucion_puntos.png")

def plot_top_correlaciones(corr_df, dir_salida, top_n=20):
    """Top correlaciones Spearman vs Pearson"""
    if len(corr_df) == 0:
        print("⚠️  Sin correlaciones para graficar")
        return
    
    top = corr_df.head(min(top_n, len(corr_df)))
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    x = np.arange(len(top))
    width = 0.35
    
    colors_spearman = ['red' if r < 0 else 'green' for r in top['spearman_r']]
    ax.barh(x - width/2, top['spearman_r'], width, label='Spearman', color=colors_spearman, alpha=0.8)
    colors_pearson = ['darkred' if r < 0 else 'darkgreen' for r in top['pearson_r']]
    ax.barh(x + width/2, top['pearson_r'], width, label='Pearson', color=colors_pearson, alpha=0.6)
    
    ax.set_yticks(x)
    ax.set_yticklabels(top['feature'], fontsize=9)
    ax.set_xlabel('Correlación', fontsize=11, fontweight='bold')
    ax.set_title(f'Top {len(top)} Features: Spearman vs Pearson', fontsize=12, fontweight='bold')
    ax.axvline(0, color='black', linestyle='-', linewidth=0.8)
    ax.grid(axis='x', alpha=0.3)
    ax.legend(loc='lower right')
    ax.set_xlim(-1, 1)
    
    plt.tight_layout()
    plt.savefig(dir_salida / '02_top_correlaciones.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Gráfico 02: top_correlaciones.png")

def plot_scatter_top_features(df, corr_df, dir_salida):
    """Scatter plots con línea de regresión"""
    if len(corr_df) < 3:
        print("⚠️  Menos de 3 features para scatter plot")
        return
    
    top_features = corr_df.head(3)['feature'].tolist()
    
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    
    for idx, feat in enumerate(top_features):
        df_plot = df[[feat, COLUMNA_OBJETIVO]].copy()
        df_plot[feat] = pd.to_numeric(df_plot[feat], errors='coerce')
        df_plot[COLUMNA_OBJETIVO] = pd.to_numeric(df_plot[COLUMNA_OBJETIVO], errors='coerce')
        df_plot = df_plot.dropna()
        
        ax = axes[idx]
        ax.scatter(df_plot[feat], df_plot[COLUMNA_OBJETIVO], alpha=0.5, s=50, edgecolors='k', linewidth=0.5)
        
        if len(df_plot) > 2:
            z = np.polyfit(df_plot[feat], df_plot[COLUMNA_OBJETIVO], 1)
            p = np.poly1d(z)
            x_line = np.linspace(df_plot[feat].min(), df_plot[feat].max(), 100)
            ax.plot(x_line, p(x_line), "r--", linewidth=2.5, label=f'y={z[0]:.3f}x+{z[1]:.3f}')
        
        row = corr_df[corr_df['feature'] == feat].iloc[0]
        ax.set_xlabel(feat[:25], fontsize=10, fontweight='bold')
        ax.set_ylabel('Puntos Fantasy', fontsize=10, fontweight='bold')
        ax.set_title(f'ρ={row["spearman_r"]:.3f} | r={row["pearson_r"]:.3f}', fontsize=11, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    
    plt.suptitle('Top 3 Features: Scatter + Regresión Lineal', fontsize=13, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(dir_salida / '03_scatter_top3.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Gráfico 03: scatter_top3.png")

def plot_matriz_correlaciones(df, features, dir_salida):
    """Matriz de correlaciones Spearman"""
    top_features = features[:10]
    df_plot = df[top_features + [COLUMNA_OBJETIVO]].copy()
    
    for col in df_plot.columns:
        df_plot[col] = pd.to_numeric(df_plot[col], errors='coerce')
    df_plot = df_plot.dropna()
    
    if len(df_plot) < 5:
        print("⚠️  Datos insuficientes para heatmap")
        return
    
    corr_matrix = df_plot.corr(method='spearman')
    
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(corr_matrix, annot=True, cmap='RdBu_r', center=0, 
                square=True, fmt='.2f', cbar_kws={'label': 'Correlación Spearman'},
                ax=ax, linewidths=0.5, vmin=-1, vmax=1)
    ax.set_title('Matriz de Correlaciones Spearman (Top 10 + Objetivo)', fontsize=12, fontweight='bold')
    plt.tight_layout()
    plt.savefig(dir_salida / '04_matriz_correlaciones.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✓ Gráfico 04: matriz_correlaciones.png")

# ============================================================================
# REPORTE
# ============================================================================

def generar_reporte_texto(corr_df, stats_dict, features, posicion, dir_salida):
    """Genera reporte estadístico"""
    
    reporte = f"""
{'='*80}
ANÁLISIS PRE-ENTRENAMIENTO - {POSICIONES_MAP[posicion]} ({posicion})
{'='*80}

POSICIÓN: {POSICIONES_MAP[posicion]}
REGISTROS VÁLIDOS: {stats_dict.get('n', 0):,}
FEATURES ANALIZADAS: {len(features)}
FEATURES GENERADOS DINÁMICAMENTE (EWMA, Rolling, Lag, Per 90)

{'='*80}
1. ANÁLISIS DESCRIPTIVO - PUNTOS FANTASY
{'='*80}

TENDENCIA CENTRAL:
  Media (µ):            {stats_dict['media']:.4f} puntos
  Mediana:              {stats_dict['mediana']:.4f} puntos
  Moda:                 {stats_dict['moda']:.4f} puntos (si disponible)

DISPERSIÓN:
  Desv. Típica (σ):     {stats_dict['std']:.4f} puntos
  Varianza (σ²):        {stats_dict['var']:.4f}
  Rango:                {stats_dict['rango']:.4f} ({stats_dict['min']:.2f} - {stats_dict['max']:.2f})
  IQR (Q3-Q1):          {stats_dict['iqr']:.4f} puntos
  MAD (Mean Abs Dev):   {stats_dict['mad']:.4f} puntos
  Coef. Variación (CV): {stats_dict['cv']:.2f}%

PERCENTILES:
  P5 (5%):              {stats_dict['p05']:.4f} puntos
  Q1 (25%):             {stats_dict['p25']:.4f} puntos  
  Q2 (50%, Mediana):    {stats_dict['p50']:.4f} puntos
  Q3 (75%):             {stats_dict['p75']:.4f} puntos
  P95 (95%):            {stats_dict['p95']:.4f} puntos
  IC 95%:               [{stats_dict['ci_95'][0]:.4f}, {stats_dict['ci_95'][1]:.4f}]

FORMA DE DISTRIBUCIÓN:
  Asimetría (Skewness):     {stats_dict['skew']:.4f}
  Curtosis (Kurtosis):      {stats_dict['kurtosis']:.4f}
  SEM (Std Error Mean):     {stats_dict['sem']:.6f}

PRUEBAS DE NORMALIDAD:
  Kolmogorov-Smirnov:   D={stats_dict['ks_statistic']:.6f}, p-value={stats_dict['ks_pvalue']:.6f}
  Shapiro-Wilk:         W={stats_dict['shapiro_statistic']:.6f}, p-value={stats_dict['shapiro_pvalue']:.6f}

{'='*80}
2. ANÁLISIS DE CORRELACIONES (MÚLTIPLES MÉTODOS)
{'='*80}

Métodos empleados:
  • Pearson: Correlación lineal paramétrica (asume normalidad)
  • Spearman: Correlación de rangos no-paramétrica (robusta a outliers)
  • Kendall Tau: Correlación ordinal (más conservadora)

Features generados dinámicamente:
  • EWMA (Exponential Weighted Moving Average): Span 3, 5, 7
  • Rolling: Windows 3, 5, 7
  • Lag: Desfases 1, 2
  • Per 90: Normalización a 90 minutos
  • TODOS con .shift() para evitar Data Leakage

"""
    
    if len(corr_df) > 0:
        reporte += f"{'FEATURE':<35} {'SPEARMAN':>10} {'PEARSON':>10} {'R² SPEAR':>10} {'P-VAL':>12} {'SIG.':>5}\n"
        reporte += f"{'-'*82}\n"
        for idx, row in corr_df.head(30).iterrows():
            sig = "✓" if row['spearman_p'] < 0.05 else " "
            reporte += f"{row['feature']:<35} {row['spearman_r']:>10.4f} {row['pearson_r']:>10.4f} {row['r2_spearman']:>10.4f} {row['spearman_p']:>12.2e} {sig:>5}\n"
    else:
        reporte += "Sin correlaciones significativas encontradas.\n"
    
    reporte += f"""

{'='*80}
FIN DEL ANÁLISIS
{'='*80}

Generado: Enero 2026
Análisis: Pre-entrenamiento ML con features dinámicos
Pipeline: Carga → Generación (EWMA, Rolling, Lag) → Correlaciones
"""
    
    with open(dir_salida / 'reporte_analisis.txt', 'w', encoding='utf-8') as f:
        f.write(reporte)
    
    print(f"✓ Reporte guardado: reporte_analisis.txt")
    return reporte

# ============================================================================
# MAIN
# ============================================================================

def analizar_posicion(posicion):
    """Análisis completo"""
    
    dir_pos = DIR_ANALISIS_BASE / posicion
    dir_pos.mkdir(parents=True, exist_ok=True)
    
    df, features = cargar_datos_posicion(posicion)
    if df.empty or len(features) == 0:
        print("❌ No hay datos o features para analizar")
        return

    # Filtrar puntosFantasy entre -15 y 30
    df = df[(df[COLUMNA_OBJETIVO] >= -15) & (df[COLUMNA_OBJETIVO] <= 30)].copy()
    print(f"✓ Filtrado puntosFantasy entre -15 y 30: {len(df):,} registros")

    print("\n📊 Calculando estadísticas avanzadas...")
    datos = df[COLUMNA_OBJETIVO]
    stats_dict = estadisticas_objetivo(datos)
    
    print("📈 Calculando correlaciones (Pearson, Spearman, Kendall)...")
    corr_df = calcular_correlaciones(df, features)
    
    # Guardar CSV con todas las correlaciones
    if len(corr_df) > 0:
        corr_export = corr_df[['feature', 'n', 'spearman_r', 'spearman_p', 'r2_spearman',
                               'pearson_r', 'pearson_p', 'r2_pearson', 
                               'kendall_tau', 'kendall_p', 'significant_spearman']].copy()
        corr_export = corr_export.sort_values('spearman_r', key=abs, ascending=False)
        corr_export.to_csv(dir_pos / 'correlaciones_spearman.csv', index=False)
        print(f"✓ CSV correlaciones guardado ({len(corr_export)} features)")
    
    print("\n🎨 Generando visualizaciones...")
    plot_distribucion_objetivo(datos, stats_dict, dir_pos)
    plot_top_correlaciones(corr_df, dir_pos)
    plot_scatter_top_features(df, corr_df, dir_pos)
    plot_matriz_correlaciones(df, features, dir_pos)
    
    print("\n📄 Generando reporte estadístico...")
    reporte = generar_reporte_texto(corr_df, stats_dict, features, posicion, dir_pos)
    print(reporte)
    
    print(f"\n✅ ANÁLISIS COMPLETADO")
    print(f"📁 {dir_pos.absolute()}\n")

# ============================================================================
# EJECUCIÓN
# ============================================================================

if __name__ == "__main__":
    print(f"""
╔{'='*78}╗
║ ANÁLISIS PRE-ENTRENAMIENTO v5.0 - FEATURES GENERADOS DINÁMICAMENTE          ║
║ EWMA • Rolling • Lag • Per 90 • Múltiples Correlaciones • Sin Data Leakage   ║
╚{'='*78}╝
    """)
    
    while True:
        print("Opciones:")
        print("  PT - Porteros     DF - Defensas     MC - Mediocentros     DT - Delanteros")
        print("  X  - Salir\n")
        
        posicion = input("Elige posición (PT/DF/MC/DT/X): ").strip().upper()
        
        if posicion == 'X':
            print("✅ Hasta luego!")
            break
        
        if posicion in POSICIONES_MAP:
            analizar_posicion(posicion)
        else:
            print("❌ Posición no válida\n")
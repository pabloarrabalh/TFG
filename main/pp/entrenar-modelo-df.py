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

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ===========================
# CONFIGURACIÓN
# ===========================
DIRECTORIO_SALIDA = Path("csv/csvGenerados/entrenamiento/defensa")
DIRECTORIO_IMAGENES = DIRECTORIO_SALIDA / "imagenes"
DIRECTORIO_MODELOS = DIRECTORIO_SALIDA / "modelos"

for d in [DIRECTORIO_SALIDA, DIRECTORIO_IMAGENES, DIRECTORIO_MODELOS]:
    d.mkdir(parents=True, exist_ok=True)

ARCHIVO_CSV = "csv/csvGenerados/players_with_features_MINIMO.csv"
TAM_VENTANA = 5
TAM_VENTANA_RECIENTE = 3  # NUEVO: Forma muy reciente
COLUMNA_OBJETIVO = "puntosFantasy"

# ===========================
# FUNCIONES UTILIDAD
# ===========================
def entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru):
    """Entrena modelo y calcula MAE, RMSE, R² y Spearman"""
    modelo.fit(X_ent, y_ent)
    pred = modelo.predict(X_pru)
    
    spearman_corr, spearman_pval = spearmanr(y_pru, pred)
    
    return {
        "mae": mean_absolute_error(y_pru, pred),
        "rmse": root_mean_squared_error(y_pru, pred),
        "r2": r2_score(y_pru, pred),
        "spearman": spearman_corr,
        "modelo": modelo,
        "predicciones": pred,
    }

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
        print(f"    ⚠️ Error extrayendo importancias: {e}")
        return None

def visualizar_feature_importance(feature_importance, titulo, nombre_archivo, top_n=20):
    """Crea visualización de feature importance"""
    if feature_importance is None or len(feature_importance) == 0:
        return
    
    df_top = feature_importance.head(top_n)
    
    fig, ax = plt.subplots(figsize=(12, max(8, top_n * 0.4)))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(df_top)))
    
    bars = ax.barh(range(len(df_top)), df_top['importance'].values, color=colors)
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
# ANÁLISIS DISTRIBUCIÓN
# ===========================
def analizar_distribucion_puntajes(df):
    """Crea visualizaciones de distribución de puntosFantasy"""
    if "puntosFantasy" not in df.columns:
        print("❌ No existe columna 'puntosFantasy'")
        return
    
    print("\n" + "="*80)
    print("ANÁLISIS DISTRIBUCIÓN PUNTOS FANTASY (DEFENSAS)")
    print("="*80)
    
    pf = df["puntosFantasy"].dropna()
    
    pf_mean = pf.mean()
    pf_std = pf.std()
    pf_min = pf.min()
    pf_max = pf.max()
    pf_p25 = pf.quantile(0.25)
    pf_p50 = pf.quantile(0.50)
    pf_p75 = pf.quantile(0.75)
    pf_skew = pf.skew()
    pf_kurt = pf.kurtosis()
    
    print(f"\n📊 ESTADÍSTICAS DESCRIPTIVAS:")
    print(f"  Media: {pf_mean:.3f}")
    print(f"  Desv.Est: {pf_std:.3f}")
    print(f"  Mínimo: {pf_min:.3f} | Máximo: {pf_max:.3f}")
    print(f"  Percentiles (25/50/75): {pf_p25:.3f} / {pf_p50:.3f} / {pf_p75:.3f}")
    print(f"  IQR: {pf_p75 - pf_p25:.3f}")
    print(f"  Skewness: {pf_skew:.3f}")
    print(f"  Kurtosis: {pf_kurt:.3f}")
    print(f"  N datos: {len(pf)}\n")
    
    # Crear figura con 2x2 subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Análisis Distribución puntosFantasy (Defensas)", fontsize=16, fontweight='bold')
    
    ax1 = axes[0, 0]
    ax1.hist(pf, bins=40, density=True, alpha=0.7, color='steelblue', edgecolor='black')
    ax1.axvline(pf_mean, color='red', linestyle='--', linewidth=2, label=f'Media: {pf_mean:.2f}')
    ax1.axvline(pf_p50, color='orange', linestyle=':', linewidth=2, label=f'Mediana: {pf_p50:.2f}')
    ax1.set_xlabel('puntosFantasy', fontsize=11)
    ax1.set_ylabel('Densidad', fontsize=11)
    ax1.set_title('Histograma + Densidad', fontsize=12, fontweight='bold')
    ax1.legend()
    ax1.grid(alpha=0.3)
    
    ax2 = axes[0, 1]
    bp = ax2.boxplot(pf, vert=True, patch_artist=True, widths=0.5)
    bp['boxes'][0].set_facecolor('lightblue')
    ax2.set_ylabel('puntosFantasy', fontsize=11)
    ax2.set_title('Box Plot', fontsize=12, fontweight='bold')
    ax2.grid(alpha=0.3, axis='y')
    
    ax3 = axes[1, 0]
    from scipy import stats
    stats.probplot(pf, dist="norm", plot=ax3)
    ax3.set_title('Q-Q Plot (Normalidad)', fontsize=12, fontweight='bold')
    ax3.grid(alpha=0.3)
    
    ax4 = axes[1, 1]
    parts = ax4.violinplot([pf], positions=[0], widths=0.7, showmeans=True, showmedians=True)
    ax4.scatter(np.random.normal(0, 0.04, size=len(pf)), pf, alpha=0.3, s=20, color='navy')
    ax4.set_ylabel('puntosFantasy', fontsize=11)
    ax4.set_title('Violin Plot + Datos', fontsize=12, fontweight='bold')
    ax4.set_xticks([])
    ax4.grid(alpha=0.3, axis='y')
    
    plt.tight_layout()
    dist_path = DIRECTORIO_IMAGENES / "distribucion_puntosFantasy.png"
    plt.savefig(dist_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Gráfico distribución guardado: {dist_path}\n")
    
    return {
        "mean": pf_mean,
        "std": pf_std,
        "min": pf_min,
        "max": pf_max,
        "p25": pf_p25,
        "p50": pf_p50,
        "p75": pf_p75,
        "count": len(pf)
    }

# ===========================
# CARGA Y PREPARACIÓN
# ===========================
def cargar_datos():
    print(f"📂 Cargando: {ARCHIVO_CSV}")
    df = pd.read_csv(ARCHIVO_CSV)
    
    print(f"ℹ️  Total registros: {len(df)}, Columnas: {len(df.columns)}")
    
    df_defensas = df[df["posicion"].str.upper() == "DF"].copy()
    
    if df_defensas.shape[0] == 0:
        print("⚠️  No se encontraron defensas con 'DF'. Intentando 'DEF'...")
        df_defensas = df[df["posicion"].str.upper() == "DEF"].copy()
    
    print(f"✅ {df_defensas.shape[0]} defensas cargadas\n")
    return df_defensas

def diagnosticar_y_limpiar(df):
    print("=" * 80)
    print("DIAGNÓSTICO Y LIMPIEZA DE DATOS")
    print("=" * 80)
    
    filas_inicio = len(df)
    
    print("\n1️⃣ Ordenando por jugador + jornada...")
    if 'jornada' in df.columns:
        df = df.sort_values(['player', 'temporada', 'jornada']).reset_index(drop=True)
        print("   ✓ Datos ordenados temporalmente")
    else:
        df = df.sort_values('player').reset_index(drop=True)
        print("   ✓ Datos ordenados por jugador")
    
    print("\n2️⃣ Eliminando registros con <10 minutos...")
    muy_poco_antes = (df['Min_partido'] < 10).sum()
    df = df[df['Min_partido'] >= 10].copy()
    print(f"   ✓ Eliminados {muy_poco_antes} registros")
    
    print("\n3️⃣ Filtrando jugadores con <5 partidos...")
    jugs_validos = df.groupby('player').size() >= 5
    jugs_validos = jugs_validos[jugs_validos].index
    antes_jugs = len(df)
    df = df[df['player'].isin(jugs_validos)]
    print(f"   ✓ Eliminados {antes_jugs - len(df)} registros")
    
    print("\n4️⃣ Eliminando outliers extremos en puntosFantasy (>30)...")
    outliers_pf = (df['puntosFantasy'] > 30).sum()
    df = df[df['puntosFantasy'] <= 30].copy()
    print(f"   ✓ Eliminados {outliers_pf} registros")
    
    print(f"\nTotal: {filas_inicio} → {len(df)} filas ({100*len(df)/filas_inicio:.1f}%)\n")
    return df

def preparar_basicos(df):
    print("=" * 80)
    print("PREPARACIÓN BÁSICA")
    print("=" * 80)
    
    # Eliminar features de ataque (no relevantes para defensas)
    a_eliminar = [
        "posicion", "Equipo_propio", "Equipo_rival",
        "TiroFallado_partido", "TiroPuerta_partido",
        "Regates", "RegatesCompletados", "RegatesFallidos",
        "Conducciones", "DistanciaConduccion", "MetrosAvanzadosConduccion",
        "ConduccionesProgresivas", "DuelosAereosGanadosPct",
        "jornada", "jornada_anterior", "Date", "home", "away",
        "PSxG", "Goles_en_contra", "Porcentaje_paradas",
        "Asist_partido", "xAG", "xG_partido", "Tiros", "target_pf_next",
        # NUEVAS: Eliminar stats de ataque del equipo propio
        "gf", "pts",  # Goals for, Team points (NO relevantes)
    ]
    a_eliminar = [c for c in a_eliminar if c in df.columns]
    df = df.drop(columns=a_eliminar, errors="ignore")
    
    if "racha5partidos" in df.columns:
        datos = df["racha5partidos"].apply(convertir_racha_a_numerico)
        df["racha_victorias"] = datos.apply(lambda x: x[0])
        df["racha_ratio_victorias"] = datos.apply(lambda x: x[3])
    
    if "racha5partidos_rival" in df.columns:
        datos_rival = df["racha5partidos_rival"].apply(convertir_racha_a_numerico)
        df["racha_rival_victorias"] = datos_rival.apply(lambda x: x[0])
        df["racha_rival_ratio_victorias"] = datos_rival.apply(lambda x: x[3])
    
    print("✓ Limpieza completada\n")
    return df

def crear_features_defensivas_core(df):
    print("=" * 80)
    print("FEATURES DEFENSIVAS CORE (⭐⭐⭐ PRIORIDAD)")
    print("=" * 80)
    
    df["Min_partido_safe"] = df["Min_partido"].replace(0, np.nan)
    
    # TACKLES
    if "Entradas" in df.columns:
        df["tackles_roll3"] = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["tackles_roll5"] = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["tackles_ewma3"] = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
        ).fillna(0)
        
        df["tackles_ewma5"] = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        
        df["tackles_lag1"] = df.groupby("player")["Entradas"].shift(1).fillna(0)
        
        per_90 = (df["Entradas"] / (df["Min_partido_safe"] / 90)).fillna(0)
        p99 = per_90.quantile(0.99)
        per_90_clipped = per_90.clip(upper=p99)
        df["tackles_per90_temp"] = per_90_clipped
        
        df["tackles_per90_roll3"] = df.groupby("player")["tackles_per90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["tackles_per90_roll5"] = df.groupby("player")["tackles_per90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df = df.drop(columns=["tackles_per90_temp"])
        print("✓ Tackles (roll3/5, ewma3/5, lag1, per90)")
    
    # DUELS + WIN RATE
    if "DuelosGanados" in df.columns and "Duelos" in df.columns:
        df["duels_roll5"] = df.groupby("player")["Duelos"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        duels_pct = (df["DuelosGanados"] / (df["Duelos"] + 1)).fillna(0.5)
        df["duels_pct_temp"] = duels_pct
        
        df["duels_won_pct_roll5"] = df.groupby("player")["duels_pct_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0.5)
        
        df["duels_won_pct_ewma5"] = df.groupby("player")["duels_pct_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0.5)
        
        df["duels_won_pct_lag1"] = df.groupby("player")["duels_pct_temp"].shift(1).fillna(0.5)
        
        df = df.drop(columns=["duels_pct_temp"])
        print("✓ Duels (roll5, win_pct_roll5, win_pct_ewma5, lag1)")
    
    # BLOCKS
    if "Bloqueos" in df.columns:
        df["blocks_roll3"] = df.groupby("player")["Bloqueos"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["blocks_roll5"] = df.groupby("player")["Bloqueos"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["blocks_ewma3"] = df.groupby("player")["Bloqueos"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
        ).fillna(0)
        
        df["blocks_ewma5"] = df.groupby("player")["Bloqueos"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        
        df["blocks_lag1"] = df.groupby("player")["Bloqueos"].shift(1).fillna(0)
        
        per_90 = (df["Bloqueos"] / (df["Min_partido_safe"] / 90)).fillna(0)
        p99 = per_90.quantile(0.99)
        per_90_clipped = per_90.clip(upper=p99)
        df["blocks_per90_temp"] = per_90_clipped
        
        df["blocks_per90_roll3"] = df.groupby("player")["blocks_per90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["blocks_per90_roll5"] = df.groupby("player")["blocks_per90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df = df.drop(columns=["blocks_per90_temp"])
        print("✓ Blocks (roll3/5, ewma3/5, lag1, per90)")
    
    # CLEARANCES
    if "Despejes" in df.columns:
        df["clearances_roll3"] = df.groupby("player")["Despejes"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["clearances_roll5"] = df.groupby("player")["Despejes"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["clearances_ewma3"] = df.groupby("player")["Despejes"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
        ).fillna(0)
        
        df["clearances_ewma5"] = df.groupby("player")["Despejes"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        
        df["clearances_lag1"] = df.groupby("player")["Despejes"].shift(1).fillna(0)
        
        per_90 = (df["Despejes"] / (df["Min_partido_safe"] / 90)).fillna(0)
        p99 = per_90.quantile(0.99)
        per_90_clipped = per_90.clip(upper=p99)
        df["clearances_per90_temp"] = per_90_clipped
        
        df["clearances_per90_roll3"] = df.groupby("player")["clearances_per90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["clearances_per90_roll5"] = df.groupby("player")["clearances_per90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df = df.drop(columns=["clearances_per90_temp"])
        print("✓ Clearances (roll3/5, ewma3/5, lag1, per90)")
    
    # AERIAL DUELS
    if "DuelosAereosGanados" in df.columns and "DuelosAereosPerdidos" in df.columns:
        aerial_total = df["DuelosAereosGanados"] + df["DuelosAereosPerdidos"] + 1
        aerial_pct = (df["DuelosAereosGanados"] / aerial_total).fillna(0.5)
        df["aerial_pct_temp"] = aerial_pct
        
        df["aerial_won_pct_roll5"] = df.groupby("player")["aerial_pct_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0.5)
        
        df["aerial_won_pct_ewma5"] = df.groupby("player")["aerial_pct_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0.5)
        
        df["aerial_duels_temp"] = aerial_total
        df["aerial_duels_roll5"] = df.groupby("player")["aerial_duels_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["aerial_won_pct_lag1"] = df.groupby("player")["aerial_pct_temp"].shift(1).fillna(0.5)
        
        df = df.drop(columns=["aerial_pct_temp", "aerial_duels_temp"])
        print("✓ Aerial Duels (won_pct_roll5, won_pct_ewma5, duels_roll5, lag1)")
    
    # COMPOSITE DEFENSIVE ACTIONS
    if all(c in df.columns for c in ["Entradas", "Bloqueos", "Despejes"]):
        df["def_actions_temp"] = df["Entradas"] + df["Bloqueos"] + df["Despejes"]
        
        df["def_actions_roll3"] = df.groupby("player")["def_actions_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["def_actions_roll5"] = df.groupby("player")["def_actions_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["def_actions_ewma3"] = df.groupby("player")["def_actions_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
        ).fillna(0)
        
        df["def_actions_ewma5"] = df.groupby("player")["def_actions_temp"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        
        per_90 = (df["def_actions_temp"] / (df["Min_partido_safe"] / 90)).fillna(0)
        p99 = per_90.quantile(0.99)
        per_90_clipped = per_90.clip(upper=p99)
        df["def_actions_per90_temp"] = per_90_clipped
        
        df["def_actions_per90_roll3"] = df.groupby("player")["def_actions_per90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["def_actions_per90_roll5"] = df.groupby("player")["def_actions_per90_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df = df.drop(columns=["def_actions_temp", "def_actions_per90_temp"])
        print("✓ Defensive Actions (roll3/5, ewma3/5, per90)")
    
    print()
    return df

def crear_features_pf_form(df):
    print("=" * 80)
    print("FANTASY POINTS FORM + FORMA RECIENTE (⭐⭐⭐ PRIORIDAD)")
    print("=" * 80)
    
    if COLUMNA_OBJETIVO in df.columns:
        # FORMA RECIENTE (NUEVA: más importante)
        df["pf_roll3"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["pf_ewma3"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA_RECIENTE, adjust=False).mean()
        ).fillna(0)
        
        # FORMA STANDARD
        df["pf_roll5"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["pf_roll10"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(10, min_periods=1).mean()
        ).fillna(0)
        
        df["pf_ewma5"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        
        # VOLATILIDAD
        df["pf_std3"] = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).std()
        ).fillna(0)
        
        pf_mean3 = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(1)
        df["pf_volatility3"] = (df["pf_std3"] / (pf_mean3 + 1e-6)).fillna(0)
        
        # LAGS
        df["pf_lag1"] = df.groupby("player")[COLUMNA_OBJETIVO].shift(1).fillna(0)
        df["pf_lag2"] = df.groupby("player")[COLUMNA_OBJETIVO].shift(2).fillna(0)
        df["pf_lag3"] = df.groupby("player")[COLUMNA_OBJETIVO].shift(3).fillna(0)
        
        # MOMENTUM RECIENTE
        pf_roll3 = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        pf_roll3_prev = df.groupby("player")[COLUMNA_OBJETIVO].transform(
            lambda x: x.shift(4).rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        df["pf_momentum3"] = pf_roll3 - pf_roll3_prev
        
        print("✓ PF Form (roll3/5/10, ewma3/5, std3, volatility3, lag1-3, momentum3)")
    
    print()
    return df

def crear_features_disponibilidad(df):
    print("=" * 80)
    print("DISPONIBILIDAD Y CONTEXTO (⭐⭐)")
    print("=" * 80)
    
    df["minutes_pct_temp"] = (df["Min_partido"] / 90).fillna(0)
    
    df["minutes_pct_roll3"] = df.groupby("player")["minutes_pct_temp"].transform(
        lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
    ).fillna(0)
    
    df["minutes_pct_roll5"] = df.groupby("player")["minutes_pct_temp"].transform(
        lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
    ).fillna(0)
    
    df["minutes_pct_ewma5"] = df.groupby("player")["minutes_pct_temp"].transform(
        lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
    ).fillna(0)
    
    df["min_pct_lag1"] = df.groupby("player")["minutes_pct_temp"].shift(1).fillna(0)
    
    df = df.drop(columns=["minutes_pct_temp"])
    
    if "Titular" in df.columns:
        df["starter_pct_roll5"] = df.groupby("player")["Titular"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["starter_pct_ewma5"] = df.groupby("player")["Titular"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        
        df["starter_lag1"] = df.groupby("player")["Titular"].shift(1).fillna(0)
        
        print("✓ Minutes & Starter (pct_roll3/5, pct_ewma5, lag1)")
    else:
        print("✓ Minutes (pct_roll3/5, pct_ewma5, lag1)")
    
    print()
    return df

def crear_features_contexto_prepart(df):
    print("=" * 80)
    print("CONTEXTO PRE-PARTIDO (⭐⭐)")
    print("=" * 80)
    
    df["is_home"] = (df["local"] == 1).astype(int) if "local" in df.columns else 0
    
    if "p_home" in df.columns:
        df["p_home_win"] = df["p_home"]
        df["p_draw_prob"] = df["p_draw"] if "p_draw" in df.columns else 0.3
        df["p_away_win"] = df["p_away"] if "p_away" in df.columns else 0.2
        print("✓ Match probabilities")
    
    print()
    return df

def crear_features_rival_defense(df):
    """NUEVA: Features defensivas del rival (lo que atacan contra nosotros)"""
    print("=" * 80)
    print("FEATURES RIVAL - DEFENSA (⭐⭐⭐ CRÍTICO PARA DEFENSAS)")
    print("=" * 80)
    
    # SOLO lo que el rival dispara (ataque)
    if "shots_rival_partido" in df.columns:
        df["opp_shots_roll3"] = df.groupby("player")["shots_rival_partido"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["opp_shots_roll5"] = df.groupby("player")["shots_rival_partido"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["opp_shots_ewma5"] = df.groupby("player")["shots_rival_partido"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        
        df["opp_shots_lag1"] = df.groupby("player")["shots_rival_partido"].shift(1).fillna(0)
        print("✓ Opponent shots (roll3/5, ewma5, lag1)")
    
    if "shots_on_target_rival_partido" in df.columns:
        df["opp_shots_on_target_roll5"] = df.groupby("player")["shots_on_target_rival_partido"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["opp_shots_on_target_ewma5"] = df.groupby("player")["shots_on_target_rival_partido"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        print("✓ Opponent shots on target (roll5, ewma5)")
    
    # DEFENSA del rival (solo si disponen nuestros defensores)
    if all(c in df.columns for c in ["gc"]):  # gc = goals concedidos (defensiva rival)
        df["opp_gc_roll5"] = df.groupby("player")["gc"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df["opp_gc_ewma5"] = df.groupby("player")["gc"].transform(
            lambda x: x.shift().ewm(span=TAM_VENTANA, adjust=False).mean()
        ).fillna(0)
        print("✓ Opponent goals conceded (roll5, ewma5)")
    
    if "racha_rival_ratio_victorias" in df.columns:
        df["opp_form_roll5"] = df.groupby("player")["racha_rival_ratio_victorias"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0.5)
        print("✓ Opponent form")
    
    print()
    return df

def crear_features_eficiencia_defensiva(df):
    """NUEVA: Eficiencia defensiva mejorada"""
    print("=" * 80)
    print("EFICIENCIA DEFENSIVA AVANZADA (⭐⭐)")
    print("=" * 80)
    
    # Ratio acciones defensivas
    if all(c in df.columns for c in ["Entradas", "Bloqueos"]):
        ratio_temp = (df["Entradas"] / (df["Bloqueos"] + 1)).fillna(0)
        df["tackles_blocks_ratio_temp"] = ratio_temp
        
        df["tackles_blocks_ratio_roll5"] = df.groupby("player")["tackles_blocks_ratio_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df = df.drop(columns=["tackles_blocks_ratio_temp"])
        print("✓ Tackles to blocks ratio")
    
    # Tasa de éxito defensivo
    if all(c in df.columns for c in ["Entradas", "DuelosGanados", "Bloqueos", "Duelos", "Despejes"]):
        def_success = ((df["Entradas"] + df["DuelosGanados"] + df["Bloqueos"]) / 
                      (df["Duelos"] + df["Bloqueos"] + df["Despejes"] + 1))
        df["def_success_temp"] = def_success
        
        df["def_success_rate_roll3"] = df.groupby("player")["def_success_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        ).fillna(0)
        
        df["def_success_rate_roll5"] = df.groupby("player")["def_success_temp"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA, min_periods=1).mean()
        ).fillna(0)
        
        df = df.drop(columns=["def_success_temp"])
        print("✓ Defensive success rate (roll3/5)")
    
    print()
    return df

def crear_features_momentum(df):
    print("=" * 80)
    print("MOMENTUM Y TENDENCIA (⭐)")
    print("=" * 80)
    
    if "Entradas" in df.columns:
        tackles_roll3 = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        )
        tackles_roll3_prev = df.groupby("player")["Entradas"].transform(
            lambda x: x.shift(4).rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        )
        df["tackles_momentum3"] = (tackles_roll3 - tackles_roll3_prev).fillna(0)
        print("✓ Tackles momentum (3-day)")
    
    if "Bloqueos" in df.columns:
        blocks_roll3 = df.groupby("player")["Bloqueos"].transform(
            lambda x: x.shift().rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        )
        blocks_roll3_prev = df.groupby("player")["Bloqueos"].transform(
            lambda x: x.shift(4).rolling(TAM_VENTANA_RECIENTE, min_periods=1).mean()
        )
        df["blocks_momentum3"] = (blocks_roll3 - blocks_roll3_prev).fillna(0)
        print("✓ Blocks momentum (3-day)")
    
    print()
    return df

def definir_variables_finales(df):
    print("=" * 80)
    print("DEFINICIÓN VARIABLES FINALES")
    print("=" * 80)
    
    variables = [
        # ⭐⭐⭐ PRIORIDAD MÁXIMA - FORMA RECIENTE
        "pf_roll3", "pf_ewma3", "pf_lag1", "pf_volatility3", "pf_momentum3",
        "tackles_roll3", "tackles_ewma3", "tackles_per90_roll3",
        "blocks_roll3", "blocks_ewma3", "blocks_per90_roll3",
        "clearances_roll3", "clearances_ewma3", "clearances_per90_roll3",
        "def_actions_roll3", "def_actions_ewma3", "def_actions_per90_roll3",
        
        # ⭐⭐⭐ OPONENTE (ATAQUE RIVAL)
        "opp_shots_roll3", "opp_shots_roll5", "opp_shots_ewma5", "opp_shots_lag1",
        "opp_shots_on_target_roll5", "opp_shots_on_target_ewma5",
        "opp_gc_roll5", "opp_gc_ewma5",
        
        # ⭐⭐ IMPORTANTE - FORMA ESTÁNDAR
        "pf_roll5", "pf_roll10", "pf_ewma5",
        "tackles_roll5", "tackles_ewma5", "tackles_per90_roll5", "tackles_lag1",
        "blocks_roll5", "blocks_ewma5", "blocks_per90_roll5", "blocks_lag1",
        "clearances_roll5", "clearances_ewma5", "clearances_per90_roll5", "clearances_lag1",
        "def_actions_roll5", "def_actions_ewma5", "def_actions_per90_roll5",
        
        # ⭐⭐ DISPONIBILIDAD
        "minutes_pct_roll3", "minutes_pct_roll5", "minutes_pct_ewma5", "min_pct_lag1",
        "starter_pct_roll5", "starter_pct_ewma5", "starter_lag1",
        
        # ⭐⭐ CONTEXTO
        "is_home", "p_home_win", "p_draw_prob", "p_away_win",
        
        # ⭐ EFICIENCIA
        "tackles_blocks_ratio_roll5", "def_success_rate_roll3", "def_success_rate_roll5",
        "tackles_momentum3", "blocks_momentum3",
        "opp_form_roll5",
        
        # ⭐ COMPLEMENTARIO
        "pf_lag2", "pf_lag3",
        "duels_roll5", "duels_won_pct_roll5", "duels_won_pct_ewma5", "duels_won_pct_lag1",
        "aerial_duels_roll5", "aerial_won_pct_roll5", "aerial_won_pct_ewma5", "aerial_won_pct_lag1",
    ]
    
    variables = [v for v in variables if v in df.columns]
    print(f"✅ {len(variables)} variables finales seleccionadas\n")
    return variables

def preparar_datos(df, variables_finales):
    print("=" * 80)
    print("PREPARACIÓN DATOS FINALES")
    print("=" * 80)
    
    df_modelo = df.copy()
    
    variables_numericas = df_modelo[[c for c in variables_finales if c in df_modelo.columns]].select_dtypes(include=[np.number]).columns
    for col in variables_numericas:
        if df_modelo[col].isnull().sum() > 0:
            df_modelo[col] = df_modelo[col].fillna(df_modelo[col].median())
    
    cols_seleccionar = [c for c in variables_finales if c in df_modelo.columns] + [COLUMNA_OBJETIVO]
    df_modelo = df_modelo[cols_seleccionar].dropna()
    
    print(f"Filas finales: {len(df_modelo)}")
    print(f"Variables finales: {len([v for v in variables_finales if v in df_modelo.columns])}\n")
    
    X = df_modelo[[v for v in variables_finales if v in df_modelo.columns]]
    y = df_modelo[COLUMNA_OBJETIVO]
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
    grid_xgb = crear_malla_parametros({
        "max_depth": [2, 3],
        "n_estimators": [300, 500],
        "learning_rate": [0.01, 0.02],
        "subsample": [0.7, 0.9],
        "colsample_bytree": [0.7],
        "reg_lambda": [1.0, 2.0],
    })
    
    grid_rf = crear_malla_parametros({
        "n_estimators": [300, 500],
        "max_depth": [10, 12],
        "min_samples_leaf": [5],
        "max_features": [0.5, 0.7],
    })
    
    grid_elastic = crear_malla_parametros({
        "alpha": [0.005, 0.01],
        "l1_ratio": [0.3, 0.5, 0.7],
    })
    
    grid_ridge = crear_malla_parametros({
        "alpha": [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    })
    
    return grid_rf, grid_xgb, grid_elastic, grid_ridge

def entrenar_modelos(X, y, folds, grid_rf, grid_xgb, grid_elastic, grid_ridge):
    print("=" * 80)
    print("ENTRENAMIENTO DE MODELOS (5 FOLDS)")
    print("=" * 80)
    
    resultados = []
    importancias_globales = {
        "rf": [],
        "xgb": [],
        "elastic": [],
        "ridge": []
    }
    
    for info_fold in folds:
        fold = info_fold["fold"]
        X_ent, X_pru = X.iloc[info_fold["idx_ent"]], X.iloc[info_fold["idx_pru"]]
        y_ent, y_pru = y.iloc[info_fold["idx_ent"]], y.iloc[info_fold["idx_pru"]]
        
        print(f"\n{'='*80}")
        print(f"FOLD {fold} / 5 | Train: {len(X_ent)} | Test: {len(X_pru)}")
        print(f"{'='*80}")
        
        # RANDOM FOREST
        print("\n🔵 RANDOM FOREST")
        mejor_rf = None
        mejor_mae_rf = float("inf")
        mejor_modelo_rf = None
        
        for i, cfg in enumerate(grid_rf, 1):
            modelo = RandomForestRegressor(**cfg, random_state=42, n_jobs=-1)
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru)
            res = {"fold": fold, "tipo": "bosque", "mae": m["mae"], "rmse": m["rmse"], "r2": m["r2"], "spearman": m["spearman"]}
            resultados.append(res)
            
            if m["mae"] < mejor_mae_rf:
                mejor_mae_rf = m["mae"]
                mejor_rf = res
                mejor_modelo_rf = modelo
            
            print(f"  [{i}/{len(grid_rf)}] MAE: {m['mae']:.4f} | Spearman: {m['spearman']:.4f}")
        
        if mejor_rf and mejor_modelo_rf:
            print(f"  ✅ Mejor: MAE {mejor_rf['mae']:.4f} | Spearman {mejor_rf['spearman']:.4f}")
            imp_rf = extraer_feature_importance(mejor_modelo_rf, X_ent, X.columns)
            if imp_rf is not None:
                importancias_globales["rf"].append(imp_rf)
        
        # XGBOOST
        print("\n🟢 XGBOOST")
        mejor_xgb = None
        mejor_mae_xgb = float("inf")
        mejor_modelo_xgb = None
        
        for i, cfg in enumerate(grid_xgb, 1):
            modelo = XGBRegressor(**cfg, objective="reg:squarederror", random_state=42, n_jobs=-1, verbosity=0)
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru)
            res = {"fold": fold, "tipo": "xgb", "mae": m["mae"], "rmse": m["rmse"], "r2": m["r2"], "spearman": m["spearman"]}
            resultados.append(res)
            
            if m["mae"] < mejor_mae_xgb:
                mejor_mae_xgb = m["mae"]
                mejor_xgb = res
                mejor_modelo_xgb = modelo
            
            print(f"  [{i}/{len(grid_xgb)}] MAE: {m['mae']:.4f} | Spearman: {m['spearman']:.4f}")
        
        if mejor_xgb and mejor_modelo_xgb:
            print(f"  ✅ Mejor: MAE {mejor_xgb['mae']:.4f} | Spearman {mejor_xgb['spearman']:.4f}")
            imp_xgb = extraer_feature_importance(mejor_modelo_xgb, X_ent, X.columns)
            if imp_xgb is not None:
                importancias_globales["xgb"].append(imp_xgb)
        
        # ELASTICNET
        print("\n🟡 ELASTICNET")
        mejor_elastic = None
        mejor_mae_elastic = float("inf")
        mejor_modelo_elastic = None
        
        for i, cfg in enumerate(grid_elastic, 1):
            modelo = Pipeline([
                ("escalador", StandardScaler()),
                ("regresor", ElasticNet(alpha=cfg["alpha"], l1_ratio=cfg["l1_ratio"],
                                       random_state=42, max_iter=10000))
            ])
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru)
            res = {"fold": fold, "tipo": "elastic", "mae": m["mae"], "rmse": m["rmse"], "r2": m["r2"], "spearman": m["spearman"]}
            resultados.append(res)
            
            if m["mae"] < mejor_mae_elastic:
                mejor_mae_elastic = m["mae"]
                mejor_elastic = res
                mejor_modelo_elastic = modelo
            
            print(f"  [{i}/{len(grid_elastic)}] MAE: {m['mae']:.4f} | Spearman: {m['spearman']:.4f}")
        
        if mejor_elastic and mejor_modelo_elastic:
            print(f"  ✅ Mejor: MAE {mejor_elastic['mae']:.4f} | Spearman {mejor_elastic['spearman']:.4f}")
            imp_elastic = extraer_feature_importance(mejor_modelo_elastic, X_ent, X.columns)
            if imp_elastic is not None:
                importancias_globales["elastic"].append(imp_elastic)
        
        # RIDGE
        print("\n🟠 RIDGE")
        mejor_ridge = None
        mejor_mae_ridge = float("inf")
        mejor_modelo_ridge = None
        
        for i, cfg in enumerate(grid_ridge, 1):
            modelo = Pipeline([
                ("escalador", StandardScaler()),
                ("regresor", Ridge(alpha=cfg["alpha"], random_state=42))
            ])
            m = entrenar_y_evaluar(modelo, X_ent, X_pru, y_ent, y_pru)
            res = {"fold": fold, "tipo": "ridge", "mae": m["mae"], "rmse": m["rmse"], "r2": m["r2"], "spearman": m["spearman"]}
            resultados.append(res)
            
            if m["mae"] < mejor_mae_ridge:
                mejor_mae_ridge = m["mae"]
                mejor_ridge = res
                mejor_modelo_ridge = modelo
            
            print(f"  [{i}/{len(grid_ridge)}] α={cfg['alpha']} → MAE: {m['mae']:.4f} | Spearman: {m['spearman']:.4f}")
        
        if mejor_ridge and mejor_modelo_ridge:
            print(f"  ✅ Mejor: MAE {mejor_ridge['mae']:.4f} | Spearman {mejor_ridge['spearman']:.4f}")
            imp_ridge = extraer_feature_importance(mejor_modelo_ridge, X_ent, X.columns)
            if imp_ridge is not None:
                importancias_globales["ridge"].append(imp_ridge)
    
    return resultados, importancias_globales

def procesar_importancias_globales(importancias_globales, X):
    """Promedia importancias entre folds"""
    print("\n" + "=" * 80)
    print("PROCESANDO FEATURE IMPORTANCE GLOBAL")
    print("=" * 80 + "\n")
    
    importancias_promedio = {}
    
    for modelo_tipo, importancias_por_fold in importancias_globales.items():
        if len(importancias_por_fold) == 0:
            print(f"⚠️  {modelo_tipo.upper()}: No hay importancias extraídas")
            continue
        
        df_todas = pd.concat(importancias_por_fold, ignore_index=True)
        df_promedio = df_todas.groupby('feature')['importance'].mean().reset_index()
        df_promedio = df_promedio.sort_values('importance', ascending=False)
        
        importancias_promedio[modelo_tipo] = df_promedio
        
        ruta_csv = DIRECTORIO_SALIDA / f"feature_importance_{modelo_tipo}.csv"
        df_promedio.to_csv(ruta_csv, index=False)
        print(f"✅ {modelo_tipo.upper()}: Guardado en {ruta_csv}")
        
        print(f"\n🏆 TOP 10 FEATURES - {modelo_tipo.upper()}:")
        for idx, row in df_promedio.head(10).iterrows():
            print(f"   {row['feature']:.<40} {row['importance']:.6f}")
        
        visualizar_feature_importance(
            df_promedio,
            f"Feature Importance - {modelo_tipo.upper()} (PROMEDIO 5 FOLDS)",
            f"feature_importance_{modelo_tipo}_promedio.png",
            top_n=20
        )
    
    return importancias_promedio

def seleccionar_mejores_modelos(resultados):
    mejor_mae = min(resultados, key=lambda x: x["mae"])
    mejor_spearman = max(resultados, key=lambda x: x["spearman"])
    
    print("\n" + "=" * 80)
    print("MEJORES MODELOS GLOBALES")
    print("=" * 80 + "\n")
    
    print(f"🥇 MEJOR MAE (Fold {mejor_mae['fold']}, {mejor_mae['tipo'].upper()}):")
    print(f"   MAE: {mejor_mae['mae']:.4f} | Spearman: {mejor_mae['spearman']:.4f} | R²: {mejor_mae['r2']:.4f}\n")
    
    print(f"🏅 MEJOR SPEARMAN (Fold {mejor_spearman['fold']}, {mejor_spearman['tipo'].upper()}):")
    print(f"   Spearman: {mejor_spearman['spearman']:.4f} | MAE: {mejor_spearman['mae']:.4f} | R²: {mejor_spearman['r2']:.4f}\n")
    
    return mejor_mae, mejor_spearman

def guardar_resultados_csv(resultados):
    df_res = pd.DataFrame(resultados)
    ruta = DIRECTORIO_SALIDA / "resultados_entrenamiento.csv"
    df_res.to_csv(ruta, index=False)
    print(f"✅ Resultados guardados: {ruta}\n")
    return df_res

def generar_resumen_final(df_res):
    print("=" * 80)
    print("RESUMEN FINAL DE RESULTADOS")
    print("=" * 80 + "\n")
    
    resumen_tipo = df_res.groupby("tipo").agg({
        "mae": ["mean", "std", "min", "max"],
        "spearman": ["mean", "max"],
        "r2": ["mean", "max"]
    }).round(4)
    
    print("📊 RESUMEN POR TIPO DE MODELO:")
    print(resumen_tipo)
    
    print("\n📈 RESUMEN POR FOLD:")
    resumen_fold = df_res.groupby("fold")[["mae", "spearman", "r2"]].mean().round(4)
    print(resumen_fold)
    
    mejor_mae = df_res.loc[df_res["mae"].idxmin()]
    print(f"\n🥇 MEJOR CONFIGURACIÓN (MAE):")
    print(f"   Fold: {mejor_mae['fold']}")
    print(f"   Modelo: {mejor_mae['tipo'].upper()}")
    print(f"   MAE: {mejor_mae['mae']:.4f}")
    print(f"   Spearman: {mejor_mae['spearman']:.4f}")
    print(f"   R²: {mejor_mae['r2']:.4f}")
    
    mejor_spearman = df_res.loc[df_res["spearman"].idxmax()]
    print(f"\n🏅 MEJOR CONFIGURACIÓN (Spearman):")
    print(f"   Fold: {mejor_spearman['fold']}")
    print(f"   Modelo: {mejor_spearman['tipo'].upper()}")
    print(f"   Spearman: {mejor_spearman['spearman']:.4f}")
    print(f"   MAE: {mejor_spearman['mae']:.4f}")
    print(f"   R²: {mejor_spearman['r2']:.4f}\n")

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🎯 ENTRENAMIENTO DEFENSAS - V5 CON FEATURE ENGINEERING MEJORADO")
    print("=" * 80 + "\n")
    print("✨ CAMBIOS V5:")
    print("   ✓ Eliminadas stats de ataque del equipo propio (gf, pts)")
    print("   ✓ Añadida forma RECIENTE (últimas 3 jornadas)")
    print("   ✓ Enfoque en DEFENSA del rival (shots, xG) no ataque")
    print("   ✓ Mejorada eficiencia defensiva (roll3/5)")
    print("   ✓ Momentum defensivo reciente (3-day windows)\n")
    
    # Cargar y analizar
    df = cargar_datos()
    analizar_distribucion_puntajes(df)
    
    # Procesamiento con feature engineering mejorado
    df = diagnosticar_y_limpiar(df)
    df = preparar_basicos(df)
    df = crear_features_defensivas_core(df)
    df = crear_features_pf_form(df)
    df = crear_features_disponibilidad(df)
    df = crear_features_contexto_prepart(df)
    df = crear_features_rival_defense(df)  # NUEVA
    df = crear_features_eficiencia_defensiva(df)  # MEJORADA
    df = crear_features_momentum(df)
    
    # Preparar datos
    variables_finales = definir_variables_finales(df)
    X, y, df_modelo = preparar_datos(df, variables_finales)
    
    if X.shape[0] == 0:
        print("❌ ERROR: Sin datos después de preparación")
        exit(1)
    
    # Entrenar
    folds = generar_splits(X)
    grid_rf, grid_xgb, grid_elastic, grid_ridge = crear_grids()
    
    print(f"\n📊 GRIDS DE HIPERPARÁMETROS:")
    print(f"  Random Forest: {len(grid_rf)} configuraciones")
    print(f"  XGBoost: {len(grid_xgb)} configuraciones")
    print(f"  ElasticNet: {len(grid_elastic)} configuraciones")
    print(f"  Ridge: {len(grid_ridge)} configuraciones\n")
    
    resultados, importancias_globales = entrenar_modelos(X, y, folds, grid_rf, grid_xgb, grid_elastic, grid_ridge)
    
    # Procesar importancias
    importancias_promedio = procesar_importancias_globales(importancias_globales, X)
    
    # Guardar y resumir
    df_res = guardar_resultados_csv(resultados)
    mejor_mae, mejor_spearman = seleccionar_mejores_modelos(resultados)
    generar_resumen_final(df_res)
    
    print("\n" + "=" * 80)
    print("✅ ENTRENAMIENTO COMPLETADO - V5 CON FEATURE ENGINEERING DEFENSIVO")
    print("=" * 80 + "\n")
    print("📌 CAMBIOS CLAVE IMPLEMENTADOS:")
    print("   ✓ Forma reciente (últimas 3 jornadas) con EWMA3")
    print("   ✓ Features rival defensivos (shots, on-target, goals conceded)")
    print("   ✓ Eliminadas stats ofensivas del propio equipo")
    print("   ✓ Eficiencia defensiva reciente (roll3, success_rate)")
    print("   ✓ Momentum con ventanas más cortas (3-day vs 5-day)")
    print("   ✓ Prioridad: DISPONIBILIDAD > FORMA RECIENTE > DEFENSA RIVAL\n")
